---
title: Bits, bytes, and memory
slug: 03-bits-bytes-and-memory
part: "Part 0 — Getting started"
summary: Read and write numbers in binary and hex, pick bits apart with masks and shifts, and see how negative numbers and byte order live in memory.
minutes: 55
gpu: false
objectives:
  - Convert between decimal, binary, and hexadecimal by hand and in code.
  - Extract and change fields of bits with masks and shifts.
  - Read a bit pattern as an unsigned or a two's complement number.
  - Lay a multi-byte number out in memory in little-endian and big-endian order.
prereqs:
  - 02-how-a-computer-runs-a-program
exercise: 03-bits-bytes-and-memory
---

# Bits, bytes, and memory

Everything inside a computer is a number, and every number is stored as a row of switches that are either off or on. A letter, a photo, a program, and the address of a box in memory are all rows of switches. To read what the machine holds, you need to know how those rows map to numbers, and how to pick them apart.

This matters for operating systems more than for most software. A virtual address is a number that the hardware splits into fields. A file system packs a record into exactly 64 bytes. A page table entry uses one bit to say "this page is present" and another to say "this page may be written". A kernel that cannot handle bits cannot do its job.

You learn the arithmetic of bits, then build the tools the rest of the course uses.

## What you already know

- A byte, in Python, is a whole number from 0 to 255, and a `bytearray` is a run of them you can change.
- Integer division `//` and remainder `%` split a number into a quotient and what is left over.
- A CPU keeps values in a few registers and reads or writes memory by address.
- A slice such as `data[2:6]` copies a range of a list or of bytes.

## Bits and bytes

A *bit* is one switch. It holds 0 or 1. The word comes from "binary digit".

A single bit says little. Eight bits together are a *byte*, and a byte can hold 256 different patterns, from `00000000` to `11111111`. A byte is the smallest unit that memory hands out: every address names one byte. 
| Bits | Patterns | Largest unsigned value |
|---|---|---|
| 1 | 2 | 1 |
| 8 | 256 | 255 |
| 16 | 65,536 | 65,535 |
| 32 | 4,294,967,296 | 4,294,967,295 |
| 64 | about 1.8 × 10^19 | 18,446,744,073,709,551,615 |

Each extra bit doubles the count, so $n$ bits give $2^n$ patterns. That is why a 32-bit address can name 4,294,967,296 bytes, which is 4 GiB.

## Binary: counting with two digits

You count in *base 10*. You have ten digits, 0 through 9, and each position is worth ten times the one to its right. The number 345 means 3 hundreds, 4 tens, and 5 ones:

$$
345 = 3 \cdot 10^2 + 4 \cdot 10^1 + 5 \cdot 10^0
$$

*Binary*, or base 2, works the same way with two digits. Each position is worth twice the one to its right: 1, 2, 4, 8, 16, and so on. To read `1010`, add up the positions that hold a 1.

```text
position value:   8    4    2    1
bits:             1    0    1    0
                  |         |
                  8    +    2    = 10
```

So `1010` in binary is 10. Going the other way, to write 10 in binary, divide by 2 over and over and collect the remainders. This is the same method you use in the exercise.

```text
10 / 2 = 5   remainder 0   <- lowest bit
 5 / 2 = 2   remainder 1
 2 / 2 = 1   remainder 0
 1 / 2 = 0   remainder 1   <- highest bit

Read the remainders from the bottom up: 1010
```

The remainder `n % 2` is the lowest bit, and `n // 2` throws that bit away and moves everything down one place. Repeat until the number reaches 0. The bits come out lowest first, so reverse them at the end.

Reading a string of digits in any base works in the other direction. Start with a total of 0. For each digit from left to right, multiply the total by the base and add the digit. For `1010` in base 2: 0 becomes 1, then 2, then 5, then 10.

## Hexadecimal: binary in shorthand

Long rows of bits are hard to read. `1101111010101101` is a lot to take in. *Hexadecimal*, or hex, is a shorthand. It is base 16. It needs sixteen digits, so it uses `0` to `9` and then `a` to `f` for the values 10 to 15.

One hex digit matches exactly four bits. So you convert by cutting the bits into groups of four:

```text
binary:   1101  1110  1010  1101
hex:        d     e     a     d      ->  0xdead
```

Programmers write `0x` before a hex number, so `0xdead` is hex. A byte is two hex digits: `0x00` to `0xff`. That is why dumps of memory show pairs of hex digits, and why `255`, `0xff`, and `11111111` are the same number in three clothes.

| Hex | Binary | Hex | Binary |
|---|---|---|---|
| 0 | 0000 | 8 | 1000 |
| 1 | 0001 | 9 | 1001 |
| 2 | 0010 | a | 1010 |
| 3 | 0011 | b | 1011 |
| 4 | 0100 | c | 1100 |
| 5 | 0101 | d | 1101 |
| 6 | 0110 | e | 1110 |
| 7 | 0111 | f | 1111 |

> [!KEY]
> Binary is what the machine stores. Hex is how people read it. One hex digit is four bits, so two hex digits are one byte.

## Masks and shifts

Kernels often need some bits of a number and not the rest. Two tools do it: *bitwise operators* and *shifts*.

The bitwise operators work on every bit position at once:

| Operator | Name | Rule | Example |
|---|---|---|---|
| `a & b` | AND | 1 where both bits are 1 | `0b1100 & 0b1010 == 0b1000` |
| `a \| b` | OR | 1 where either bit is 1 | `0b1100 \| 0b1010 == 0b1110` |
| `a ^ b` | XOR | 1 where the bits differ | `0b1100 ^ 0b1010 == 0b0110` |
| `~a` | NOT | flips every bit | `~0b0101 == -6` in Python |
| `a << n` | left shift | moves bits up `n` places | `0b0011 << 2 == 0b1100` |
| `a >> n` | right shift | moves bits down `n` places | `0b1100 >> 2 == 0b0011` |

A left shift by $n$ multiplies by $2^n$. A right shift by $n$ divides by $2^n$ and drops the remainder.

A *mask* is a number whose 1 bits mark the positions you care about. ANDing with a mask keeps those bits and clears the rest. A mask of $k$ ones is `(1 << k) - 1`. For example, `(1 << 3) - 1` is `0b111`.

Put the two together and you can pull a *field* out of a number. Say you want 3 bits starting at bit 2 of `0b110100`, which is 52. Bit 0 is the lowest.

```text
value          =  1 1 0 1 0 0      (52)
shift right 2  =      1 1 0 1      (13)   the field is now at the bottom
mask 0b111     =  0 0 0 1 0 1      keep the low 3 bits
result         =  0b101  = 5
```

In Python: `(52 >> 2) & 0b111` is 5. This one expression is how a CPU splits an address into a page number and an offset in lesson 14.

To set a single bit, OR with a number that has only that bit on: `value | (1 << i)`. To clear it, AND with the opposite: `value & ~(1 << i)`. Setting bit 2 of `0b0000` gives `0b0100`. Clearing bit 1 of `0b0110` gives `0b0100`.

> [!TIP]
> Number bits from 0 at the right. Bit 0 is the least significant bit, and bit 7 of a byte is the most significant. Every mask formula in this course uses that convention.

## Fixed width and wraparound

A Python int can be as big as you like. A register or a memory cell cannot. It has a fixed *width*, such as 8, 16, 32, or 64 bits. A value that does not fit is cut to its low bits. This is *wraparound*, and it works like an odometer that rolls from 999 back to 000.

For 8 bits, wraparound is "remainder after dividing by 256". So 255 + 1 becomes 0, and 300 becomes `300 % 256 = 44`. In Python, `n % (1 << bits)` does this, and it also works for negative numbers: `-1 % 256` is 255.

## Negative numbers: two's complement

Bits do not come with a minus sign. Computers store negative numbers by agreeing on a meaning for some patterns. The scheme that every modern CPU uses is *two's complement*.

In $b$ bits, the patterns from 0 up to $2^{b-1} - 1$ mean themselves. The patterns from $2^{b-1}$ up to $2^b - 1$ mean the same number minus $2^b$. In practice, the top bit works as a sign bit: it is 1 for a negative number.

For 8 bits:

| Bit pattern | Hex | Unsigned | Two's complement |
|---|---|---|---|
| `00000000` | `0x00` | 0 | 0 |
| `00000001` | `0x01` | 1 | 1 |
| `01111111` | `0x7f` | 127 | 127 |
| `10000000` | `0x80` | 128 | -128 |
| `11111110` | `0xfe` | 254 | -2 |
| `11111111` | `0xff` | 255 | -1 |

The range of 8-bit two's complement is -128 to 127. For $b$ bits it is $-2^{b-1}$ to $2^{b-1}-1$.

To write a negative number such as -5 in 8 bits, take 5, flip all the bits, and add 1:

```text
 5          = 00000101
flip bits   = 11111010
add 1       = 11111011   = 0xfb = 251 as unsigned
```

Check: 251 − 256 = −5. The pattern `0xfb` is the same bits, read with a different rule. That is the key point. The bits do not know if they are signed. The program decides.

Why this scheme? The adder circuit works unchanged for signed and unsigned numbers. Add `-5` and `7`: `0xfb + 0x07 = 0x102`, which wraps to 8 bits as `0x02`, and 2 is the right answer.

To convert in code, with `bits` the width: reading a pattern as signed means subtracting `1 << bits` when bit `bits - 1` is set. Writing a signed number as a pattern means `n % (1 << bits)`.

Overflow follows. In 8 bits, 127 + 1 is `0x80`, which reads as -128. A signed number that grows past its top wraps to the bottom. Real bugs come from this. The year-2038 problem is one: 32-bit Unix time stamps count seconds in a signed 32-bit number.

## Bytes in memory

Memory is an array of bytes, and an address is an index into the array. `mem[0x1000]` is the byte at address 4096.

A value wider than a byte, such as a 32-bit number, takes several consecutive bytes. The question is which order. Take `0x12345678`. Its four bytes are `12`, `34`, `56`, and `78`, where `12` is the *most significant* byte and `78` the *least significant*. There are two conventions.

- **Big-endian** stores the most significant byte first, at the lowest address. It reads like the number does on paper.
- **Little-endian** stores the least significant byte first.

```text
value 0x12345678 stored at address 100

address:        100   101   102   103
big-endian:      12    34    56    78
little-endian:   78    56    34    12
```

Which one does your computer use? Intel and AMD x86-64 chips are little-endian. ARM chips can do either, and nearly every system that runs on them, including Linux, macOS, Android, and iOS, runs them little-endian. Network protocols use big-endian, which is called *network byte order*.

Order matters whenever bytes travel between machines or between a file and a program. If you write a 4-byte number in little-endian and a reader assumes big-endian, `0x12345678` becomes `0x78563412`. The bytes are intact. They are read in the wrong order.

To pack a value, find byte number $i$ counting from the least significant end with `(value >> (8 * i)) & 0xFF`. For `0x12345678`, byte 0 is `0x78`, byte 1 is `0x56`, byte 2 is `0x34`, and byte 3 is `0x12`. That list, in that order, is the little-endian layout. Reverse it for big-endian. To unpack, add `byte << (8 * i)` for each byte in the little-endian order.

## Try it on your own machine

1. Run `python3 -c "import sys; print(sys.byteorder)"`. Look for `little` on a typical laptop. On Linux, `lscpu | grep 'Byte Order'` says the same.
2. Run `python3 -c "print(hex(255), bin(255), int('ff', 16), int('1010', 2))"`. Look for `0xff 0b11111111 255 10`. Python's built-in converters do what your functions do.
3. Run `python3 -c "print((0x12345678).to_bytes(4, 'little').hex(), (0x12345678).to_bytes(4, 'big').hex())"`. Look for `78563412` and `12345678`: the same number in the two byte orders.
4. Run `printf 'AB\n' | xxd` on Linux or macOS. Look for the hex bytes `41 42 0a`, which are the letters A and B and a newline. `xxd` is a tool that shows a file's bytes in hex.

## Build it step by step

Open the starter. It has ten functions. Fill them in the order below, and click Check after each one.

1. **`to_base(n, base)`.** It takes a non-negative int and a base from 2 to 16 and returns a lowercase string. Divide repeatedly, collect `n % base` as a digit looked up in `"0123456789abcdef"`, and reverse at the end. Handle `n == 0`, which must give `"0"`. Raise `ValueError` for a bad base or a negative number. The common mistake is forgetting to reverse, which gives the digits backwards.
2. **`from_base(text, base)`.** It reads digits left to right with `total = total * base + digit`. Accept upper and lower case. Raise `ValueError` for an empty string and for a digit too large for the base, such as `2` in base 2. Do not trust `"0123456789abcdef".find(ch)` alone, because a digit like `f` is found even when the base is 10.
3. **`get_bits(value, low, count)`.** Shift right by `low`, then AND with `(1 << count) - 1`. Test it on the worked example: `get_bits(0b110100, 2, 3)` is 5.
4. **`set_bit(value, index, on=True)`.** Return a changed copy of the number with the bit set or cleared. Use `|` with `1 << index` to set, and `&` with `~(1 << index)` to clear. The mistake is using `^`, which flips the bit instead of setting it.
5. **`to_unsigned(n, bits)`.** Wrap into `0 .. 2**bits - 1`. One expression with `%` does it.
6. **`to_signed(value, bits)`.** Read a pattern as two's complement. Raise `ValueError` if it does not fit in `bits` bits. If the top bit is set, subtract `1 << bits`. Check against the table: `to_signed(0x80, 8)` is -128.
7. **`pack_uint(value, size, byteorder)`.** Return `bytes`. Build the byte list lowest first with shifts and masks, reverse it for `"big"`. Raise `ValueError` for a value that does not fit in `size` bytes (including a negative one) and for a byte order that is neither `"little"` nor `"big"`. Do not call `int.to_bytes`: the point is to build it yourself.
8. **`unpack_uint(data, byteorder)`.** The reverse. Put the bytes in little-endian order, then add `byte << (8 * i)` for each. An empty input gives 0.
9. **`write_word(mem, addr, value, size, byteorder)` and `read_word(mem, addr, size, byteorder)`.** They store and load through a `bytearray`. Check `0 <= addr` and `addr + size <= len(mem)` and raise `IndexError` first. A slice assignment such as `mem[6:10] = ...` on an 8-byte memory would quietly grow the array, which no real memory does.
10. **`format_bytes(data)`.** Return `"de ad be ef"` style text: two lowercase hex digits per byte, separated by single spaces. Reuse `to_base` and pad with `rjust(2, "0")`.

## Where this breaks

- **Python hides the width.** Your functions take `bits` as a parameter because Python ints have none. In C, an `int` is 32 bits and silently wraps. Signed overflow in C is actually undefined behaviour, so the compiler may assume it never happens. Your Python models cannot show that danger.
- **A "KB" is ambiguous.** 1 KB is 1,000 bytes to a disk maker, and 1 KiB is 1,024 bytes. This course uses KiB, MiB, and GiB for powers of 1,024.
- **Byte order is a convention, not a law.** A file format, a network protocol, and a CPU each choose one. Mixing them is a bug that produces plausible-looking wrong numbers. File formats and network protocols fix an order so that any machine can read them.

## Further reading

- [Operating Systems: Three Easy Pieces, Chapter 13: The Abstraction: Address Spaces](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf) shows memory as an array of bytes with addresses, the picture this lesson builds on.
- [Python documentation: bitwise operations](https://docs.python.org/3/library/stdtypes.html#bitwise-operations-on-integer-types) lists the operators on ints and their precedence.
- [Two's complement on Wikipedia](https://en.wikipedia.org/wiki/Two%27s_complement) gives the full theory, with more worked conversions.
- [Endianness on Wikipedia](https://en.wikipedia.org/wiki/Endianness) covers the history of the two orders and the hardware that uses each.
- [Python documentation: int.to_bytes](https://docs.python.org/3/library/stdtypes.html#int.to_bytes) is the built-in version of your packing function.

## The exercise

You write the number tools every later lesson uses: `to_base` and `from_base` for number bases, `get_bits` and `set_bit` for fields and flags, `to_unsigned` and `to_signed` for two's complement, `pack_uint` and `unpack_uint` for byte order, `write_word` and `read_word` to store numbers in a `bytearray` memory, and `format_bytes` for a readable hex dump.

The ten checks follow that order. They compare your answers with hand-computed ones, such as `to_base(255, 16) == "ff"`, `get_bits(0b110100, 2, 3) == 5`, `to_signed(0x80, 8) == -128`, and `pack_uint(0x12345678, 4, "little") == b"\x78\x56\x34\x12"`. They also check the error cases, a round trip through `pack_uint` and `unpack_uint`, and that a failed `write_word` leaves memory unchanged. Click Run to print a small tour of your functions.
