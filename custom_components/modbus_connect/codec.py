"""Symmetric codec between Modbus registers/bits and Python values.

Pure functions, no Home Assistant imports. ``decode`` and ``encode`` are exact
inverses for every construct that supports writing; constructs that cannot be
written (``flags``) raise :class:`NotWritableError` from ``encode``.

Decode pipeline for word tables (each step only if configured):

    words -> swap -> assemble (type / string / sum_scale) -> mask
          -> map | flags | (multiplier -> offset)

``encode`` runs the same pipeline backwards.
"""

from __future__ import annotations

import math
import struct

from .models import (
    BIT_TABLES,
    FLOAT_TYPES,
    SIGNED_TYPES,
    TYPE_STRING,
    TYPE_WIDTH,
    EntityDef,
)


class CodecError(Exception):
    """Value cannot be converted."""


class NotWritableError(CodecError):
    """The entity's configuration does not support writing."""


_FLOAT_FMT = {"float32": ">f", "float64": ">d"}


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

    num: float | int
    if defn.sum_scale is not None:
        num = _int_if_whole(sum(w * s for w, s in zip(words, defn.sum_scale, strict=True)))
    elif defn.type in FLOAT_TYPES:
        num = struct.unpack(_FLOAT_FMT[defn.type], _words_to_bytes(words))[0]
        if math.isnan(num) or math.isinf(num):
            return None
    else:
        num = int.from_bytes(_words_to_bytes(words), "big", signed=defn.type in SIGNED_TYPES)

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
        reverse = {v: k for k, v in defn.value_map.items()}
        if len(reverse) != len(defn.value_map):
            raise NotWritableError(f"{defn.key}: map values are not unique, cannot write")
        if value not in reverse:
            raise CodecError(f"{defn.key}: {value!r} is not a mapped value")
        num = reverse[value]
    elif defn.type == TYPE_STRING:
        data = str(value).encode("ascii")
        if len(data) > defn.count * 2:
            raise CodecError(
                f"{defn.key}: string longer than {defn.count * 2} characters"
            )
        words = _bytes_to_words(data.ljust(defn.count * 2, b"\x00"))
        return _swap_words(words, defn.swap)
    else:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CodecError(f"{defn.key}: expected a number, got {value!r}")
        num = value
        if defn.offset is not None:
            num = num - defn.offset
        if defn.multiplier is not None:
            if defn.multiplier == 0:
                raise CodecError(f"{defn.key}: multiplier 0 cannot be inverted")
            num = num / defn.multiplier

    if defn.type in FLOAT_TYPES:
        words = _bytes_to_words(struct.pack(_FLOAT_FMT[defn.type], float(num)))
        return _swap_words(words, defn.swap)

    int_num = round(num)
    if abs(num - int_num) > 1e-6:
        raise CodecError(f"{defn.key}: {value!r} does not map to a whole register value")

    if defn.sum_scale is not None:
        return _swap_words(_encode_sum_scale(defn, int_num), defn.swap)

    if defn.mask is not None:
        return [_encode_masked(defn, int_num, current_raw)]

    width = TYPE_WIDTH[defn.type]
    bits = width * 16
    if defn.type in SIGNED_TYPES:
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    else:
        lo, hi = 0, (1 << bits) - 1
    if not lo <= int_num <= hi:
        raise CodecError(f"{defn.key}: {int_num} out of range for {defn.type}")
    words = _bytes_to_words((int_num & ((1 << bits) - 1)).to_bytes(width * 2, "big"))
    return _swap_words(words, defn.swap)


def _encode_sum_scale(defn: EntityDef, num: int) -> list[int]:
    """Decompose ``num`` into words such that sum(word[i] * scale[i]) == num."""
    scales = defn.sum_scale
    assert scales is not None
    if num < 0:
        raise CodecError(f"{defn.key}: negative values not representable with sum_scale")
    int_scales: list[int] = []
    for s in scales:
        if s <= 0 or int(s) != s:
            raise NotWritableError(
                f"{defn.key}: sum_scale write requires positive integer scales"
            )
        int_scales.append(int(s))
    words = [0] * len(int_scales)
    rem = num
    # Fill positions from the largest weight down; min() lets the remainder
    # flow to smaller weights, the final check catches unrepresentable values.
    for i in sorted(range(len(int_scales)), key=lambda i: -int_scales[i]):
        digit = min(rem // int_scales[i], 0xFFFF)
        words[i] = digit
        rem -= digit * int_scales[i]
    if rem != 0:
        raise CodecError(f"{defn.key}: {num} is not representable with sum_scale {scales}")
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
