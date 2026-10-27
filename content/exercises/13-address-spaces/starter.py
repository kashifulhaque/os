"""Lesson 13: address spaces, base and bounds, and segmentation.

A *virtual address* is the number a program uses. A *physical address* is a
position in the machine's real memory, here a `bytearray`. The hardware
(your functions, in this exercise) turns the first into the second and
refuses addresses the process does not own by raising `SegmentationFault`.

The toy machine has a 14-bit virtual address space: 16 KiB. For segmentation
the top 2 bits of an address choose the segment and the low 12 bits are the
offset inside it, so a segment can be up to 4 KiB (4096 bytes).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

SEG_BITS = 2
OFFSET_BITS = 12
SEG_SIZE = 1 << OFFSET_BITS         # 4096: the largest a segment can be
ADDRESS_SPACE = 1 << (SEG_BITS + OFFSET_BITS)  # 16384 virtual bytes

SEG_CODE = 0   # segment numbers used in the lesson's examples
SEG_HEAP = 1
SEG_STACK = 3  # number 2 is left unmapped


class SegmentationFault(Exception):
    """The process touched an address it may not use."""


@dataclass(frozen=True)
class Segment:
    """One region of an address space and where it lives in physical memory.

    For a segment that grows up, `base` is the physical address of its first
    byte and it covers physical addresses base .. base + size - 1.

    For a segment with `grows_down=True` (the stack), `base` is the physical
    address just PAST its top byte, and it covers base - size .. base - 1.
    The top byte of its virtual range is offset SEG_SIZE - 1.

    `writable=False` makes the segment read-only (code).
    """

    name: str
    base: int
    size: int
    grows_down: bool = False
    writable: bool = True


def split_virtual_address(vaddr: int) -> tuple:
    """Split a 14-bit virtual address into (segment number, offset).

    split_virtual_address(4200) == (1, 104)    # 4200 = 1 * 4096 + 104
    Raise SegmentationFault if vaddr is negative or at least ADDRESS_SPACE.
    """
    raise NotImplementedError


def translate_base_bounds(vaddr: int, base: int, bounds: int) -> int:
    """Base-and-bounds translation: one base register, one bounds register.

    A virtual address is valid when 0 <= vaddr < bounds. Then the physical
    address is base + vaddr. Anything else raises SegmentationFault.

    translate_base_bounds(128, base=16384, bounds=4096) == 16512
    """
    raise NotImplementedError


def translate_segmented(vaddr: int, table: dict, write: bool = False) -> int:
    """Translate through a segment table {segment number: Segment}.

    Raise SegmentationFault when:
      * the address is outside the 14-bit space,
      * the segment number is not in `table`,
      * `write` is True and the segment is not writable,
      * the offset is outside the segment: for a segment that grows up,
        offset >= size; for one that grows down, SEG_SIZE - offset > size.

    Grows up:   physical = base + offset.
    Grows down: physical = base - (SEG_SIZE - offset).

    With heap Segment("heap", base=34816, size=3072) as table[1],
    translate_segmented(4200, table) == 34920.
    """
    raise NotImplementedError


def load_byte(mem: bytearray, table: dict, vaddr: int) -> int:
    """Read the byte at a virtual address, through the segment table.

    Raises SegmentationFault the way translate_segmented does (a read).
    """
    raise NotImplementedError


def store_byte(mem: bytearray, table: dict, vaddr: int, value: int) -> None:
    """Write one byte (0..255) at a virtual address, through the segment table.

    This is a write, so a read-only segment raises SegmentationFault.
    """
    raise NotImplementedError


def relocate(mem: bytearray, segment: Segment, new_base: int) -> Segment:
    """Move a segment's bytes to a new physical place and return the updated Segment.

    Copies the segment's `size` bytes so that, with the returned segment,
    every virtual address reads the same bytes as before. `new_base` has the
    same meaning as `Segment.base`. Raise ValueError (and change nothing) if
    the new physical range does not fit inside mem.
    """
    raise NotImplementedError


if __name__ == "__main__":
    mem = bytearray(64 * 1024)
    table = {
        SEG_CODE: Segment("code", base=32768, size=2048, writable=False),
        SEG_HEAP: Segment("heap", base=34816, size=3072),
        SEG_STACK: Segment("stack", base=28672, size=2048, grows_down=True),
    }
    print("one base and one bounds:", translate_base_bounds(128, 16384, 4096))
    for vaddr in (100, 4200, 15360, 16383):
        seg, offset = split_virtual_address(vaddr)
        print(f"vaddr {vaddr:5d} -> segment {seg}, offset {offset:4d} "
              f"-> physical {translate_segmented(vaddr, table)}")
    store_byte(mem, table, 4200, 42)
    print("mem[34920] after store at 4200:", mem[34920])
    for vaddr, write in ((2048, False), (100, True), (8192, False)):
        try:
            translate_segmented(vaddr, table, write=write)
        except SegmentationFault:
            kind = "write" if write else "read"
            print(f"{kind} at {vaddr}: segmentation fault")
