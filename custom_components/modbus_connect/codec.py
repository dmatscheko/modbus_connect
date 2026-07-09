"""Symmetric codec between Modbus registers/bits and Python values.

Pure functions, no Home Assistant imports. ``decode`` and ``encode`` are exact
inverses for every construct that supports writing; constructs that cannot be
written (``flags``) raise :class:`NotWritableError` from ``encode``.

Decode pipeline for word tables (each step only if configured):

    words -> swap -> assemble (type / string / sum_scale over typed elements)
          -> mask -> map | flags | (multiplier -> offset)

``encode`` runs the same pipeline backwards.
"""

from __future__ import annotations

import math
import struct
from datetime import time as dt_time

from .models import (
    BIT_TABLES,
    FLOAT_TYPES,
    SIGNED_TYPES,
    TYPE_BITS,
    TYPE_STRING,
    TYPE_TIME,
    TYPE_WIDTH,
    UNSIGNED_INT_TYPES,
    EntityDef,
)


class CodecError(Exception):
    """Value cannot be converted."""


class NotWritableError(CodecError):
    """The entity's configuration does not support writing."""


_FLOAT_FMT = {"float16": ">e", "float32": ">f", "float64": ">d"}


def _swap_words(words: list[int], mode: str | None) -> list[int]:
    if not mode:
        return list(words)
    out = list(words)
    if mode in ("word", "word_byte"):
        out.reverse()
    if mode in ("byte", "word_byte"):
        out = [((w & 0xFF) << 8) | ((w >> 8) & 0xFF) for w in out]
    return out


def _words_to_bytes(words: list[int]) -> bytes:
    return b"".join((w & 0xFFFF).to_bytes(2, "big") for w in words)


def _bytes_to_words(data: bytes) -> list[int]:
    return [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]


def _mask_shift(mask: int) -> int:
    """Number of trailing zero bits of the mask."""
    return (mask & -mask).bit_length() - 1


def _int_if_whole(num: float | int) -> float | int:
    if isinstance(num, float) and num.is_integer() and abs(num) < 2**53:
        return int(num)
    return num


def _element_values(defn: EntityDef, words: list[int], n: int) -> list[float | int] | None:
    """The first ``n`` values of the entity's type from the (swapped) words.

    Sub-word elements (``bit``, ``uint8``, ``int8``) are taken from each
    register least-significant-first; wider elements consume whole big-endian
    registers. Returns ``None`` when a float element is NaN or infinite.
    """
    bits = TYPE_BITS[defn.type]
    if bits < 16:
        per_word = 16 // bits
        top = 1 << bits
        chunks: list[float | int] = [
            (words[i // per_word] >> (bits * (i % per_word))) & (top - 1) for i in range(n)
        ]
        if defn.type in SIGNED_TYPES:
            chunks = [v - top if v >= top // 2 else v for v in chunks]
        return chunks
    step = bits // 16
    out: list[float | int] = []
    for i in range(n):
        data = _words_to_bytes(words[i * step : (i + 1) * step])
        if defn.type in FLOAT_TYPES:
            value: float = struct.unpack(_FLOAT_FMT[defn.type], data)[0]
            if math.isnan(value) or math.isinf(value):
                return None
            out.append(value)
        else:
            out.append(int.from_bytes(data, "big", signed=defn.type in SIGNED_TYPES))
    return out


def decode(defn: EntityDef, raw: list[int] | list[bool] | bool) -> object:
    """Convert raw register words / coil bits into the entity's value.

    Returns ``None`` for values that cannot be interpreted (NaN floats,
    integers missing from ``map``); the entity then shows as unavailable.
    """
    if defn.table in BIT_TABLES:
        bit = raw[0] if isinstance(raw, (list, tuple)) else raw
        return bool(bit)

    words = _swap_words(list(raw), defn.swap)  # type: ignore[arg-type]

    if defn.type == TYPE_STRING:
        text = _words_to_bytes(words).decode("ascii", errors="replace")
        return text.split("\x00", 1)[0].strip()

    if defn.type == TYPE_TIME:
        if defn.count == 2:  # separate registers: first = hour, second = minute
            hour, minute = words[0], words[1]
        else:  # packed into one register: high byte = hour, low byte = minute
            hour, minute = (words[0] >> 8) & 0xFF, words[0] & 0xFF
        if hour < 24 and minute < 60:
            return dt_time(hour, minute)
        if not defn.rectify_time:
            return None
        # Out of range with rectify_time: 24:00 (or beyond) is end-of-day -> 23:59;
        # a stray minute overflow keeps the hour.
        return dt_time(23, 59) if hour >= 24 else dt_time(hour, 59)

    num: float | int
    if defn.sum_scale is not None:
        elements = _element_values(defn, words, len(defn.sum_scale))
        if elements is None:
            return None
        num = _int_if_whole(
            sum(e * s for e, s in zip(elements, defn.sum_scale, strict=True))
        )
    else:
        single = _element_values(defn, words, 1)
        if single is None:
            return None
        num = single[0]

    if defn.mask is not None:
        num = (int(num) & defn.mask) >> _mask_shift(defn.mask)

    if defn.value_map is not None:
        return defn.value_map.get(int(num))

    if defn.flags is not None:
        names = [name for bit, name in sorted(defn.flags.items()) if (int(num) >> bit) & 1]
        return ", ".join(names)

    if defn.multiplier is not None:
        num = num * defn.multiplier
    if defn.offset is not None:
        num = num + defn.offset
    if isinstance(num, float):
        num = round(num, 10)  # drop binary artifacts of decimal multipliers (0.1 etc.)
    return _int_if_whole(num)


def encode(
    defn: EntityDef, value: object, current_raw: int | None = None
) -> list[int] | bool:
    """Convert a value into register words (word tables) or a bool (coil).

    ``current_raw`` is the current raw register content, required only for
    masked writes (``read_modify_write``).
    """
    if defn.table in BIT_TABLES:
        return bool(value)

    if defn.flags is not None:
        raise NotWritableError(f"{defn.key}: flags entities are read-only")

    num: float | int
    if defn.value_map is not None:
        num = _unmap(defn, value)
    elif defn.type == TYPE_STRING:
        return _encode_string(defn, value)
    elif defn.type == TYPE_TIME:
        return _encode_time(defn, value)
    else:
        num = _invert_conversions(defn, value)

    return _pack_number(defn, num, value, current_raw)


def _encode_time(defn: EntityDef, value: object) -> list[int]:
    """Pack a time-of-day into registers.

    Two-register form (``count == 2``): hour in the first register, minute in the
    second. Single-register form: high byte hour, low byte minute.
    """
    if not isinstance(value, dt_time):
        raise CodecError(f"{defn.key}: expected a time, got {value!r}")
    if defn.count == 2:
        return _swap_words([value.hour, value.minute], defn.swap)
    return _swap_words([(value.hour << 8) | value.minute], defn.swap)


def _unmap(defn: EntityDef, value: object) -> int:
    """Reverse a ``map``: label -> register value."""
    assert defn.value_map is not None
    reverse = {v: k for k, v in defn.value_map.items()}
    if len(reverse) != len(defn.value_map):
        raise NotWritableError(f"{defn.key}: map values are not unique, cannot write")
    if value not in reverse:
        raise CodecError(f"{defn.key}: {value!r} is not a mapped value")
    return reverse[value]


def _encode_string(defn: EntityDef, value: object) -> list[int]:
    try:
        data = str(value).encode("ascii")
    except UnicodeEncodeError as err:
        raise CodecError(f"{defn.key}: {value!r} contains non-ASCII characters") from err
    if len(data) > defn.count * 2:
        raise CodecError(
            f"{defn.key}: string longer than {defn.count * 2} characters"
        )
    words = _bytes_to_words(data.ljust(defn.count * 2, b"\x00"))
    return _swap_words(words, defn.swap)


def _invert_conversions(defn: EntityDef, value: object) -> float | int:
    """Run multiplier/offset backwards: displayed value -> raw number."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CodecError(f"{defn.key}: expected a number, got {value!r}")
    num: float | int = value
    if defn.offset is not None:
        num = num - defn.offset
    if defn.multiplier is not None:
        if defn.multiplier == 0:
            raise CodecError(f"{defn.key}: multiplier 0 cannot be inverted")
        num = num / defn.multiplier
    return num


def _pack_number(
    defn: EntityDef, num: float | int, value: object, current_raw: int | None
) -> list[int]:
    """Pack the raw number into register words (float / sum_scale / mask / int)."""
    if defn.sum_scale is not None:
        return _swap_words(_encode_sum_scale(defn, num, value), defn.swap)

    if defn.type in FLOAT_TYPES:
        try:
            packed = struct.pack(_FLOAT_FMT[defn.type], float(num))
        except (OverflowError, struct.error) as err:
            raise CodecError(
                f"{defn.key}: {value!r} out of range for {defn.type}"
            ) from err
        return _swap_words(_bytes_to_words(packed), defn.swap)

    int_num = _whole_number(defn, num, value)

    if defn.mask is not None:
        # The mask is defined against the decoded (swap-applied) word; swap the
        # raw register into that domain, merge, and swap back for the wire.
        if current_raw is not None:
            current_raw = _swap_words([current_raw], defn.swap)[0]
        return _swap_words([_encode_masked(defn, int_num, current_raw)], defn.swap)

    bits = TYPE_BITS[defn.type]
    if defn.type in SIGNED_TYPES:
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    else:
        lo, hi = 0, (1 << bits) - 1
    if not lo <= int_num <= hi:
        raise CodecError(f"{defn.key}: {int_num} out of range for {defn.type}")
    width = TYPE_WIDTH[defn.type]
    words = _bytes_to_words((int_num & ((1 << bits) - 1)).to_bytes(width * 2, "big"))
    return _swap_words(words, defn.swap)


def _whole_number(defn: EntityDef, num: float | int, value: object) -> int:
    if isinstance(num, float) and not math.isfinite(num):
        raise CodecError(f"{defn.key}: {value!r} is not a finite number")
    int_num = round(num)
    if abs(num - int_num) > 1e-6:
        raise CodecError(f"{defn.key}: {value!r} does not map to a whole register value")
    return int_num


def _encode_sum_scale(defn: EntityDef, num: float | int, value: object) -> list[int]:
    """Decompose ``num`` into elements with sum(element[i] * scale[i]) == num."""
    scales = defn.sum_scale
    assert scales is not None
    if defn.type not in UNSIGNED_INT_TYPES:
        raise NotWritableError(
            f"{defn.key}: sum_scale writes require an unsigned integer type"
        )
    int_scales: list[int] = []
    for s in scales:
        if s <= 0 or int(s) != s:
            raise NotWritableError(
                f"{defn.key}: sum_scale write requires positive integer scales"
            )
        int_scales.append(int(s))
    int_num = _whole_number(defn, num, value)
    if int_num < 0:
        raise CodecError(f"{defn.key}: negative values not representable with sum_scale")
    cap = (1 << TYPE_BITS[defn.type]) - 1
    digits = [0] * len(int_scales)
    rem = int_num
    # Fill positions from the largest weight down; min() lets the remainder
    # flow to smaller weights, the final check catches unrepresentable values.
    for i in sorted(range(len(int_scales)), key=lambda i: -int_scales[i]):
        digit = min(rem // int_scales[i], cap)
        digits[i] = digit
        rem -= digit * int_scales[i]
    if rem != 0:
        raise CodecError(
            f"{defn.key}: {int_num} is not representable with sum_scale {scales}"
        )
    return _pack_elements(defn, digits)


def _pack_elements(defn: EntityDef, digits: list[int]) -> list[int]:
    """Place element values into registers (the inverse of ``_element_values``)."""
    bits = TYPE_BITS[defn.type]
    words = [0] * defn.count
    if bits < 16:
        per_word = 16 // bits
        for i, digit in enumerate(digits):
            words[i // per_word] |= digit << (bits * (i % per_word))
        return words
    step = bits // 16
    for i, digit in enumerate(digits):
        words[i * step : (i + 1) * step] = _bytes_to_words(digit.to_bytes(step * 2, "big"))
    return words


def _encode_masked(defn: EntityDef, num: int, current_raw: int | None) -> int:
    if not defn.read_modify_write:
        raise NotWritableError(
            f"{defn.key}: masked write requires 'read_modify_write: true'"
        )
    if defn.count != 1:
        raise CodecError(f"{defn.key}: masked writes only supported for a single register")
    if current_raw is None:
        raise CodecError(f"{defn.key}: current register value required for masked write")
    assert defn.mask is not None
    shift = _mask_shift(defn.mask)
    if (num << shift) & ~defn.mask:
        raise CodecError(f"{defn.key}: {num} does not fit into mask {defn.mask:#x}")
    return ((current_raw & 0xFFFF) & ~defn.mask) | ((num << shift) & defn.mask)
