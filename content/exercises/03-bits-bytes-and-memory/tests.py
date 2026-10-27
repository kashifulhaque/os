"""Checks for the bits, bytes, and memory exercise."""

from oscheck import check, equal, fail, has


def expect_error(kind, action, what):
    try:
        action()
    except kind:
        return
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"{what}: raised {type(exc).__name__}, expected {kind.__name__}")
    fail(f"{what}: expected {kind.__name__}, but nothing was raised")


@check("to_base writes numbers in binary, decimal, and hex")
def test_to_base(sub):
    to_base = has(sub, "to_base")
    equal(to_base(0, 2), "0", label="to_base(0, 2)")
    equal(to_base(10, 2), "1010", label="to_base(10, 2)")  # 8 + 2
    equal(to_base(255, 2), "11111111", label="to_base(255, 2)")
    equal(to_base(255, 16), "ff", label="to_base(255, 16)")
    equal(to_base(4096, 16), "1000", label="to_base(4096, 16)")
    equal(to_base(3735928559, 16), "deadbeef", label="to_base(3735928559, 16)")
    equal(to_base(123, 10), "123", label="to_base(123, 10)")
    expect_error(ValueError, lambda: to_base(-1, 2), "to_base(-1, 2)")
    expect_error(ValueError, lambda: to_base(5, 1), "to_base(5, 1)")
    expect_error(ValueError, lambda: to_base(5, 17), "to_base(5, 17)")


@check("from_base reads digit strings and rejects bad ones")
def test_from_base(sub):
    from_base = has(sub, "from_base")
    equal(from_base("1010", 2), 10, label="from_base('1010', 2)")
    equal(from_base("ff", 16), 255, label="from_base('ff', 16)")
    equal(from_base("FF", 16), 255, label="from_base('FF', 16)")
    equal(from_base("deadbeef", 16), 3735928559, label="from_base('deadbeef', 16)")
    equal(from_base("0", 2), 0, label="from_base('0', 2)")
    expect_error(ValueError, lambda: from_base("102", 2), "from_base('102', 2): digit 2 is not binary")
    expect_error(ValueError, lambda: from_base("xyz", 16), "from_base('xyz', 16)")
    expect_error(ValueError, lambda: from_base("", 10), "from_base('', 10)")


@check("get_bits extracts a field of bits")
def test_get_bits(sub):
    get_bits = has(sub, "get_bits")
    # 0b110100 shifted right 2 is 0b1101; the low 3 bits of that are 0b101.
    equal(get_bits(0b110100, 2, 3), 0b101, label="get_bits(0b110100, 2, 3)")
    equal(get_bits(0xABCD, 0, 8), 0xCD, label="get_bits(0xABCD, 0, 8)")
    equal(get_bits(0xABCD, 8, 8), 0xAB, label="get_bits(0xABCD, 8, 8)")
    equal(get_bits(0xABCD, 4, 4), 0xC, label="get_bits(0xABCD, 4, 4)")
    equal(get_bits(0b1000, 3, 1), 1, label="get_bits(0b1000, 3, 1)")
    equal(get_bits(0xFFFF, 0, 0), 0, label="get_bits(0xFFFF, 0, 0)")


@check("set_bit sets and clears single bits without touching the rest")
def test_set_bit(sub):
    set_bit = has(sub, "set_bit")
    equal(set_bit(0b0000, 2), 0b0100, label="set_bit(0b0000, 2)")
    equal(set_bit(0b0100, 2), 0b0100, label="setting an already-set bit")
    equal(set_bit(0b0110, 1, on=False), 0b0100, label="set_bit(0b0110, 1, on=False)")
    equal(set_bit(0b0100, 0, on=False), 0b0100, label="clearing an already-clear bit")
    equal(set_bit(0, 31), 0x80000000, label="set_bit(0, 31)")
    equal(set_bit(0xFF, 7, on=False), 0x7F, label="set_bit(0xFF, 7, on=False)")


@check("to_unsigned wraps numbers into a fixed width")
def test_to_unsigned(sub):
    to_unsigned = has(sub, "to_unsigned")
    equal(to_unsigned(5, 8), 5, label="to_unsigned(5, 8)")
    equal(to_unsigned(-1, 8), 255, label="to_unsigned(-1, 8)")
    equal(to_unsigned(256, 8), 0, label="to_unsigned(256, 8)")
    equal(to_unsigned(-128, 8), 128, label="to_unsigned(-128, 8)")
    equal(to_unsigned(-1, 32), 0xFFFFFFFF, label="to_unsigned(-1, 32)")
    equal(to_unsigned(300, 8), 44, label="to_unsigned(300, 8)")  # 300 - 256


@check("to_signed reads two's complement patterns")
def test_to_signed(sub):
    to_signed = has(sub, "to_signed")
    equal(to_signed(0x00, 8), 0, label="to_signed(0x00, 8)")
    equal(to_signed(0x7F, 8), 127, label="to_signed(0x7F, 8)")
    equal(to_signed(0x80, 8), -128, label="to_signed(0x80, 8)")
    equal(to_signed(0xFF, 8), -1, label="to_signed(0xFF, 8)")
    equal(to_signed(0xFFFE, 16), -2, label="to_signed(0xFFFE, 16)")
    equal(to_signed(0x80000000, 32), -2147483648, label="to_signed(0x80000000, 32)")
    expect_error(ValueError, lambda: to_signed(256, 8), "to_signed(256, 8)")
    expect_error(ValueError, lambda: to_signed(-1, 8), "to_signed(-1, 8)")


@check("pack_uint produces little- and big-endian bytes")
def test_pack(sub):
    pack_uint = has(sub, "pack_uint")
    equal(pack_uint(0x12345678, 4, "little"), b"\x78\x56\x34\x12", label="pack_uint(0x12345678, 4, 'little')")
    equal(pack_uint(0x12345678, 4, "big"), b"\x12\x34\x56\x78", label="pack_uint(0x12345678, 4, 'big')")
    equal(pack_uint(1, 2, "little"), b"\x01\x00", label="pack_uint(1, 2, 'little')")
    equal(pack_uint(1, 2, "big"), b"\x00\x01", label="pack_uint(1, 2, 'big')")
    equal(pack_uint(0, 3, "big"), b"\x00\x00\x00", label="pack_uint(0, 3, 'big')")
    got = pack_uint(258, 2, "big")
    if not isinstance(got, bytes):
        fail(f"pack_uint should return bytes, got {type(got).__name__}")
    expect_error(ValueError, lambda: pack_uint(256, 1, "little"), "pack_uint(256, 1, ...) is too big")
    expect_error(ValueError, lambda: pack_uint(-1, 4, "little"), "pack_uint(-1, 4, ...)")
    expect_error(ValueError, lambda: pack_uint(1, 4, "middle"), "pack_uint(1, 4, 'middle')")


@check("unpack_uint reverses pack_uint")
def test_unpack(sub):
    unpack_uint = has(sub, "unpack_uint")
    pack_uint = has(sub, "pack_uint")
    equal(unpack_uint(b"\x78\x56\x34\x12", "little"), 0x12345678, label="unpack_uint little")
    equal(unpack_uint(b"\x12\x34\x56\x78", "big"), 0x12345678, label="unpack_uint big")
    equal(unpack_uint(b"\x00\x01", "big"), 1, label="unpack_uint(b'\\x00\\x01', 'big')")
    equal(unpack_uint(b"\x00\x01", "little"), 256, label="unpack_uint(b'\\x00\\x01', 'little')")
    equal(unpack_uint(b"", "little"), 0, label="unpack_uint(b'', 'little')")
    for order in ("little", "big"):
        for value in (0, 1, 255, 256, 65535, 0xDEADBEEF):
            equal(unpack_uint(pack_uint(value, 4, order), order), value, label=f"round trip of {value} ({order})")


@check("write_word and read_word use a bytearray as memory")
def test_memory(sub):
    write_word = has(sub, "write_word")
    read_word = has(sub, "read_word")
    mem = bytearray(8)
    write_word(mem, 2, 0x12345678, 4, "little")
    equal(bytes(mem), b"\x00\x00\x78\x56\x34\x12\x00\x00", label="memory after write_word")
    equal(read_word(mem, 2, 4, "little"), 0x12345678, label="read_word little")
    equal(read_word(mem, 2, 4, "big"), 0x78563412, label="the same bytes read as big-endian")
    equal(read_word(mem, 3, 1, "little"), 0x56, label="read_word of one byte at address 3")
    equal(len(mem), 8, label="len(mem) must not change")
    expect_error(IndexError, lambda: write_word(mem, 6, 1, 4, "little"), "write_word past the end of memory")
    expect_error(IndexError, lambda: read_word(mem, 5, 4, "little"), "read_word past the end of memory")
    expect_error(IndexError, lambda: read_word(mem, -1, 2, "little"), "read_word at address -1")
    equal(bytes(mem), b"\x00\x00\x78\x56\x34\x12\x00\x00", label="a failed write must not change memory")


@check("format_bytes shows bytes as hex")
def test_format(sub):
    format_bytes = has(sub, "format_bytes")
    equal(format_bytes(b"\xde\xad\xbe\xef"), "de ad be ef", label="format_bytes(deadbeef)")
    equal(format_bytes(b"\x00\x0a\x10"), "00 0a 10", label="two digits for small bytes")
    equal(format_bytes(b""), "", label="format_bytes(b'')")
    equal(format_bytes(bytearray(b"A")), "41", label="format_bytes(bytearray(b'A'))")
