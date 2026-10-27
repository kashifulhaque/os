"""Bits, bytes, and memory: number bases, masks, two's complement, and byte order."""

DIGITS = "0123456789abcdef"


def to_base(n, base):
    """Write a non-negative int as a lowercase string in base 2 to 16.

    to_base(255, 2) -> "11111111"; to_base(255, 16) -> "ff"; to_base(0, 10) -> "0"
    Raise ValueError for a negative n or a base outside 2..16.
    """
    raise NotImplementedError


def from_base(text, base):
    """Read a string of digits in base 2 to 16 as an int. Upper or lower case.

    from_base("ff", 16) -> 255; from_base("1010", 2) -> 10
    Raise ValueError for an empty string, a bad digit, or a bad base.
    """
    raise NotImplementedError


def get_bits(value, low, count):
    """Return `count` bits of value starting at bit `low` (bit 0 is the least significant).

    get_bits(0b110100, 2, 3) -> 0b101 == 5
    """
    raise NotImplementedError


def set_bit(value, index, on=True):
    """Return value with bit `index` set to 1 (on=True) or cleared to 0 (on=False).

    set_bit(0b0000, 2) -> 0b0100; set_bit(0b0110, 1, on=False) -> 0b0100
    """
    raise NotImplementedError


def to_unsigned(n, bits):
    """Wrap any int into the range 0 .. 2**bits - 1.

    to_unsigned(-1, 8) -> 255; to_unsigned(256, 8) -> 0
    """
    raise NotImplementedError


def to_signed(value, bits):
    """Read a bits-wide pattern (0 .. 2**bits - 1) as a two's complement number.

    to_signed(0xFF, 8) -> -1; to_signed(0x7F, 8) -> 127; to_signed(0x80, 8) -> -128
    Raise ValueError if value does not fit in `bits` bits.
    """
    raise NotImplementedError


def _check_order(byteorder):
    if byteorder not in ("little", "big"):
        raise ValueError(f"byteorder must be 'little' or 'big', got {byteorder!r}")


def pack_uint(value, size, byteorder):
    """Turn an unsigned int into `size` bytes, without int.to_bytes.

    pack_uint(0x12345678, 4, "little") -> b"\\x78\\x56\\x34\\x12"
    pack_uint(0x12345678, 4, "big")    -> b"\\x12\\x34\\x56\\x78"
    Raise ValueError if value is negative or too big for `size` bytes, or if
    byteorder is not "little" or "big".
    """
    raise NotImplementedError


def unpack_uint(data, byteorder):
    """Turn bytes into an unsigned int, without int.from_bytes.

    unpack_uint(b"\\x78\\x56\\x34\\x12", "little") -> 0x12345678
    """
    raise NotImplementedError


def write_word(mem, addr, value, size, byteorder):
    """Store value as `size` bytes in the bytearray mem, starting at addr.

    Raise IndexError if the bytes would not all fit inside mem.
    """
    raise NotImplementedError


def read_word(mem, addr, size, byteorder):
    """Load `size` bytes from mem starting at addr and return them as an unsigned int.

    Raise IndexError if the bytes are not all inside mem.
    """
    raise NotImplementedError


def format_bytes(data):
    """Show bytes as two lowercase hex digits each, separated by spaces.

    format_bytes(b"\\xde\\xad\\xbe\\xef") -> "de ad be ef"; format_bytes(b"") -> ""
    """
    raise NotImplementedError


if __name__ == "__main__":
    print("255 in binary and hex :", to_base(255, 2), to_base(255, 16))
    print("'1a' in hex           :", from_base("1a", 16))
    print("bits 2..4 of 0b110100 :", bin(get_bits(0b110100, 2, 3)))
    print("0xFF as signed 8-bit  :", to_signed(0xFF, 8))
    print("-5 as unsigned 8-bit  :", to_unsigned(-5, 8))
    mem = bytearray(8)
    write_word(mem, 2, 0x12345678, 4, "little")
    print("memory                :", format_bytes(mem))
    print("read back as big      :", hex(read_word(mem, 2, 4, "big")))
