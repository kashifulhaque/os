"""Bits, bytes, and memory: number bases, masks, two's complement, and byte order."""

DIGITS = "0123456789abcdef"


def to_base(n, base):
    """Write a non-negative int as a lowercase string in base 2 to 16.

    to_base(255, 2) -> "11111111"; to_base(255, 16) -> "ff"; to_base(0, 10) -> "0"
    Raise ValueError for a negative n or a base outside 2..16.
    """
    if not 2 <= base <= 16:
        raise ValueError(f"base must be between 2 and 16, got {base}")
    if n < 0:
        raise ValueError(f"n must not be negative, got {n}")
    if n == 0:
        return "0"
    digits = []
    while n > 0:
        digits.append(DIGITS[n % base])  # the lowest digit comes out first
        n //= base
    return "".join(reversed(digits))


def from_base(text, base):
    """Read a string of digits in base 2 to 16 as an int. Upper or lower case.

    from_base("ff", 16) -> 255; from_base("1010", 2) -> 10
    Raise ValueError for an empty string, a bad digit, or a bad base.
    """
    if not 2 <= base <= 16:
        raise ValueError(f"base must be between 2 and 16, got {base}")
    if text == "":
        raise ValueError("empty string")
    total = 0
    for ch in text.lower():
        value = DIGITS.find(ch)
        if value < 0 or value >= base:
            raise ValueError(f"{ch!r} is not a digit in base {base}")
        total = total * base + value
    return total


def get_bits(value, low, count):
    """Return `count` bits of value starting at bit `low` (bit 0 is the least significant).

    get_bits(0b110100, 2, 3) -> 0b101 == 5
    """
    mask = (1 << count) - 1
    return (value >> low) & mask


def set_bit(value, index, on=True):
    """Return value with bit `index` set to 1 (on=True) or cleared to 0 (on=False).

    set_bit(0b0000, 2) -> 0b0100; set_bit(0b0110, 1, on=False) -> 0b0100
    """
    if on:
        return value | (1 << index)
    return value & ~(1 << index)


def to_unsigned(n, bits):
    """Wrap any int into the range 0 .. 2**bits - 1.

    to_unsigned(-1, 8) -> 255; to_unsigned(256, 8) -> 0
    """
    return n % (1 << bits)  # Python's % never returns a negative number


def to_signed(value, bits):
    """Read a bits-wide pattern (0 .. 2**bits - 1) as a two's complement number.

    to_signed(0xFF, 8) -> -1; to_signed(0x7F, 8) -> 127; to_signed(0x80, 8) -> -128
    Raise ValueError if value does not fit in `bits` bits.
    """
    if not 0 <= value < (1 << bits):
        raise ValueError(f"{value} does not fit in {bits} bits")
    if value & (1 << (bits - 1)):  # the top bit is the sign bit
        return value - (1 << bits)
    return value


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
    _check_order(byteorder)
    if not 0 <= value < (1 << (8 * size)):
        raise ValueError(f"{value} does not fit in {size} bytes")
    least_first = [(value >> (8 * i)) & 0xFF for i in range(size)]
    if byteorder == "big":
        least_first.reverse()
    return bytes(least_first)


def unpack_uint(data, byteorder):
    """Turn bytes into an unsigned int, without int.from_bytes.

    unpack_uint(b"\\x78\\x56\\x34\\x12", "little") -> 0x12345678
    """
    _check_order(byteorder)
    ordered = bytes(data) if byteorder == "little" else bytes(data)[::-1]
    total = 0
    for i, byte in enumerate(ordered):
        total |= byte << (8 * i)
    return total


def write_word(mem, addr, value, size, byteorder):
    """Store value as `size` bytes in the bytearray mem, starting at addr.

    Raise IndexError if the bytes would not all fit inside mem.
    """
    if addr < 0 or addr + size > len(mem):
        raise IndexError(f"{size} bytes at address {addr} do not fit in memory of {len(mem)} bytes")
    mem[addr:addr + size] = pack_uint(value, size, byteorder)


def read_word(mem, addr, size, byteorder):
    """Load `size` bytes from mem starting at addr and return them as an unsigned int.

    Raise IndexError if the bytes are not all inside mem.
    """
    if addr < 0 or addr + size > len(mem):
        raise IndexError(f"{size} bytes at address {addr} are not all inside memory of {len(mem)} bytes")
    return unpack_uint(mem[addr:addr + size], byteorder)


def format_bytes(data):
    """Show bytes as two lowercase hex digits each, separated by spaces.

    format_bytes(b"\\xde\\xad\\xbe\\xef") -> "de ad be ef"; format_bytes(b"") -> ""
    """
    return " ".join(to_base(b, 16).rjust(2, "0") for b in data)


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
