"""Tests for the symmetric codec."""

import math
from datetime import time

import pytest

from custom_components.modbus_connect.codec import (
    CodecError,
    NotWritableError,
    decode,
    encode,
)
from custom_components.modbus_connect.models import EntityDef


def e(**kwargs) -> EntityDef:
    kwargs.setdefault("key", "test")
    kwargs.setdefault("platform", "sensor")
    return EntityDef(**kwargs)


# --- plain integer types ---------------------------------------------------


def test_uint16_roundtrip():
    defn = e(type="uint16")
    assert decode(defn, [1234]) == 1234
    assert encode(defn, 1234) == [1234]


def test_int16_negative_roundtrip():
    defn = e(type="int16")
    assert decode(defn, [0xFFFE]) == -2
    assert encode(defn, -2) == [0xFFFE]


def test_uint32_roundtrip():
    defn = e(type="uint32", count=2)
    assert decode(defn, [0x0001, 0x86A0]) == 100000
    assert encode(defn, 100000) == [0x0001, 0x86A0]


def test_int32_roundtrip():
    defn = e(type="int32", count=2)
    words = encode(defn, -123456)
    assert decode(defn, words) == -123456


def test_uint64_roundtrip():
    defn = e(type="uint64", count=4)
    value = 2**48 + 5
    words = encode(defn, value)
    assert len(words) == 4
    assert decode(defn, words) == value


def test_uint16_out_of_range():
    with pytest.raises(CodecError):
        encode(e(type="uint16"), 70000)
    with pytest.raises(CodecError):
        encode(e(type="uint16"), -1)


# --- floats ------------------------------------------------------------------


def test_float32_roundtrip():
    defn = e(type="float32", count=2)
    words = encode(defn, 21.5)
    assert decode(defn, words) == pytest.approx(21.5)


def test_float64_roundtrip():
    defn = e(type="float64", count=4)
    words = encode(defn, math.pi)
    assert decode(defn, words) == pytest.approx(math.pi)


def test_float_nan_decodes_to_none():
    defn = e(type="float32", count=2)
    assert decode(defn, [0x7FC0, 0x0000]) is None


# --- strings -----------------------------------------------------------------


def test_string_roundtrip_with_padding():
    defn = e(type="string", count=4)
    words = encode(defn, "Hi!")
    assert len(words) == 4
    assert decode(defn, words) == "Hi!"


def test_string_too_long():
    with pytest.raises(CodecError):
        encode(e(type="string", count=1), "toolong")


def test_string_stops_at_nul():
    defn = e(type="string", count=2)
    # "AB", NUL, junk
    assert decode(defn, [0x4142, 0x0043]) == "AB"


def test_string_byte_swap():
    # byte-swapped strings (e.g. SolaX serial numbers) decode with swap: byte
    defn = e(type="string", count=2, swap="byte")
    assert decode(defn, [0x4E53, 0x3234]) == "SN42"  # stored "NS24" -> "SN42"
    assert decode(defn, encode(defn, "SN42")) == "SN42"  # symmetric


# --- time -------------------------------------------------------------------


def test_time_roundtrip():
    # one register, high byte = hour, low byte = minute (SolaX GEN4: hour*256 + minute)
    defn = e(type="time", platform="time")
    assert decode(defn, [3102]) == time(12, 30)  # 12*256 + 30
    assert encode(defn, time(12, 30)) == [3102]
    assert decode(defn, [5947]) == time(23, 59)
    assert decode(defn, [0]) == time(0, 0)


def test_time_invalid_is_none():
    defn = e(type="time", platform="time")
    assert decode(defn, [(25 << 8)]) is None  # hour 25 out of range
    assert decode(defn, [61]) is None  # minute 61 out of range


def test_time_byte_swap():
    # devices packing minute-high / hour-low select swap: byte
    defn = e(type="time", platform="time", swap="byte")
    assert decode(defn, [(30 << 8) | 12]) == time(12, 30)
    assert decode(defn, encode(defn, time(12, 30))) == time(12, 30)  # symmetric


def test_time_requires_time_value():
    with pytest.raises(CodecError):
        encode(e(type="time", platform="time"), "12:30")


# --- swaps -------------------------------------------------------------------


@pytest.mark.parametrize("swap", ["byte", "word", "word_byte"])
def test_swap_roundtrip(swap):
    defn = e(type="uint32", count=2, swap=swap)
    words = encode(defn, 0x12345678)
    assert decode(defn, words) == 0x12345678


def test_word_swap_layout():
    defn = e(type="uint32", count=2, swap="word")
    # little-endian word order: low word first on the wire
    assert decode(defn, [0x5678, 0x1234]) == 0x12345678
    assert encode(defn, 0x12345678) == [0x5678, 0x1234]


def test_byte_swap_layout():
    defn = e(type="uint16", swap="byte")
    assert decode(defn, [0x3412]) == 0x1234
    assert encode(defn, 0x1234) == [0x3412]


# --- multiplier / offset -------------------------------------------------------


def test_multiplier_and_offset_roundtrip():
    defn = e(type="int16", multiplier=0.1, offset=-40)
    assert decode(defn, [500]) == 10  # 500*0.1 - 40
    assert encode(defn, 10) == [500]


def test_multiplier_float_result():
    defn = e(type="uint16", multiplier=0.1)
    assert decode(defn, [215]) == pytest.approx(21.5)
    assert encode(defn, 21.5) == [215]


def test_encode_rejects_non_integer_register_value():
    defn = e(type="uint16", multiplier=0.1)
    with pytest.raises(CodecError):
        encode(defn, 21.55)  # 215.5 registers — not representable


# --- sum_scale -----------------------------------------------------------------


def test_sum_scale_decode():
    defn = e(type="uint16", count=3, sum_scale=(1, 10000, 100000000))
    assert decode(defn, [6789, 12345, 2]) == 6789 + 12345 * 10000 + 2 * 100000000


def test_sum_scale_roundtrip():
    defn = e(type="uint16", count=3, sum_scale=(1, 10000, 100000000))
    value = 323456789
    words = encode(defn, value)
    assert decode(defn, words) == value
    assert all(0 <= w <= 0xFFFF for w in words)


def test_sum_scale_with_multiplier():
    defn = e(type="uint16", count=2, sum_scale=(1, 10000), multiplier=0.1)
    assert decode(defn, [5, 3]) == pytest.approx(3000.5)
    assert encode(defn, 3000.5) == [5, 3]


def test_sum_scale_unrepresentable():
    defn = e(type="uint16", count=2, sum_scale=(3, 7))
    with pytest.raises(CodecError):
        encode(defn, 5)


def test_sum_scale_negative_rejected():
    defn = e(type="uint16", count=2, sum_scale=(1, 10000))
    with pytest.raises(CodecError):
        encode(defn, -1)


# --- small types (bit / uint8 / int8 / float16) --------------------------------


def test_bit_reads_lsb_and_roundtrips():
    defn = e(type="bit")
    assert decode(defn, [0b0101]) == 1
    assert decode(defn, [0b0100]) == 0
    assert encode(defn, 1) == [1]
    assert encode(defn, 0) == [0]
    with pytest.raises(CodecError):
        encode(defn, 2)


def test_uint8_reads_low_byte_and_roundtrips():
    defn = e(type="uint8")
    assert decode(defn, [0x1234]) == 0x34
    assert encode(defn, 0xAB) == [0x00AB]
    with pytest.raises(CodecError):
        encode(defn, 256)


def test_int8_sign_extends():
    defn = e(type="int8")
    assert decode(defn, [0x00FB]) == -5
    assert encode(defn, -5) == [0x00FB]
    with pytest.raises(CodecError):
        encode(defn, 128)


def test_float16_roundtrip_and_nan():
    defn = e(type="float16")
    words = encode(defn, 1.5)
    assert words == [0x3E00]
    assert decode(defn, words) == pytest.approx(1.5)
    assert decode(defn, [0x7E00]) is None  # NaN
    with pytest.raises(CodecError):
        encode(defn, 1e6)  # not representable in half precision


# --- sum_scale over typed elements ----------------------------------------------


def test_sum_scale_uint8_packs_two_per_register():
    defn = e(type="uint8", count=1, sum_scale=(1, 100))
    assert decode(defn, [0x0305]) == 5 + 3 * 100
    assert encode(defn, 305) == [0x0305]


def test_sum_scale_uint8_across_registers():
    # 3 byte elements -> 1.5 registers, stored in 2
    defn = e(type="uint8", count=2, sum_scale=(1, 100, 10000))
    words = encode(defn, 987)
    assert words == [0x0957, 0x0000]  # 87 low byte, 9 high byte, 0 pad
    assert decode(defn, words) == 987


def test_sum_scale_bits():
    defn = e(type="bit", count=1, sum_scale=(1, 2, 4, 8))
    assert decode(defn, [0b1010]) == 10
    assert encode(defn, 10) == [0b1010]


def test_sum_scale_signed_elements_decode_only():
    defn = e(type="int16", count=2, sum_scale=(1, 10))
    assert decode(defn, [0xFFFE, 2]) == -2 + 2 * 10
    with pytest.raises(NotWritableError):
        encode(defn, 18)


def test_sum_scale_uint32_elements():
    defn = e(type="uint32", count=4, sum_scale=(1, 1000000))
    words = encode(defn, 2_100_000)
    assert words == [0x0001, 0x86A0, 0x0000, 0x0002]
    assert decode(defn, words) == 2_100_000


def test_sum_scale_float_elements_decode_only():
    defn = e(type="float32", count=4, sum_scale=(1, 10))
    one_and_two = encode(e(type="float32", count=2), 1.0) + encode(
        e(type="float32", count=2), 2.0
    )
    assert decode(defn, one_and_two) == 21  # 1.0 + 2.0*10
    with pytest.raises(NotWritableError):
        encode(defn, 21)


def test_sum_scale_uint8_with_byte_swap():
    # device packs the first element into the high byte: swap flips it back
    defn = e(type="uint8", count=1, sum_scale=(1, 100), swap="byte")
    assert decode(defn, [0x0503]) == 5 + 3 * 100
    assert encode(defn, 305) == [0x0503]


# --- mask ----------------------------------------------------------------------


def test_mask_decode():
    defn = e(type="uint16", mask=0x00F0)
    assert decode(defn, [0x0A5F]) == 0x5


def test_mask_write_requires_read_modify_write():
    defn = e(type="uint16", mask=0x00F0)
    with pytest.raises(NotWritableError):
        encode(defn, 3, current_raw=0x0A5F)


def test_mask_write_merges_bits():
    defn = e(type="uint16", mask=0x00F0, read_modify_write=True, platform="number")
    assert encode(defn, 0x3, current_raw=0x0A5F) == [0x0A3F]


def test_mask_write_value_too_big():
    defn = e(type="uint16", mask=0x00F0, read_modify_write=True)
    with pytest.raises(CodecError):
        encode(defn, 0x1F, current_raw=0)


def test_mask_write_requires_current_value():
    defn = e(type="uint16", mask=0x00F0, read_modify_write=True)
    with pytest.raises(CodecError):
        encode(defn, 1, current_raw=None)


# --- map / flags -----------------------------------------------------------------


def test_map_decode_and_reverse():
    defn = e(type="uint16", value_map={0: "Off", 1: "Auto", 2: "Party"})
    assert decode(defn, [1]) == "Auto"
    assert encode(defn, "Party") == [2]


def test_map_unknown_value_decodes_to_none():
    defn = e(type="uint16", value_map={0: "Off"})
    assert decode(defn, [9]) is None


def test_map_unknown_option_rejected_on_write():
    defn = e(type="uint16", value_map={0: "Off"})
    with pytest.raises(CodecError):
        encode(defn, "On")


def test_map_with_mask():
    defn = e(
        type="uint16",
        mask=0x0F00,
        value_map={1: "A", 2: "B"},
        read_modify_write=True,
    )
    assert decode(defn, [0x0200]) == "B"
    assert encode(defn, "A", current_raw=0x0234) == [0x0134]


def test_flags_decode_and_not_writable():
    defn = e(type="uint16", flags={0: "Pump", 2: "Mill", 5: "Fan"})
    assert decode(defn, [0b100101]) == "Pump, Mill, Fan"
    assert decode(defn, [0b000100]) == "Mill"
    assert decode(defn, [0]) == ""
    with pytest.raises(NotWritableError):
        encode(defn, "Pump")


# --- bit tables -------------------------------------------------------------------


def test_coil_decode_encode():
    defn = e(table="coil", type="bool", platform="switch")
    assert decode(defn, [True]) is True
    assert decode(defn, [0]) is False
    assert encode(defn, 1) is True
    assert encode(defn, False) is False
