"""A free-list allocator over a fixed arena.

The arena is `size` bytes at integer offsets 0..size-1. Every block is a
HEADER-byte header followed by its payload. A block is the tuple
(offset, payload_size, is_free). Blocks tile the arena exactly, so
sum(HEADER + payload_size) == size. `malloc` returns offset + HEADER, the
address of the first payload byte.

Example: Allocator(128) starts as one free block (0, 120, True). malloc(16)
splits it into (0, 16, False) and (24, 96, True), and returns 8.
"""

HEADER = 8  # bytes of bookkeeping in front of every block
ALIGN = 8   # payload sizes are rounded up to a multiple of this


class DoubleFree(Exception):
    """free() was given an address that already lies in free space."""


class InvalidFree(Exception):
    """free() was given an address that malloc never returned."""


def round_up(n, align=ALIGN):
    """Round n up to the next multiple of align.

    Example: round_up(10) == 16, round_up(16) == 16
    """
    raise NotImplementedError("round_up")


def find_block(blocks, need, policy="first"):
    """Return the index of the free block to use for `need` payload bytes, or None.

    Only free blocks with payload >= need qualify. "first" takes the first
    that qualifies. "best" takes the smallest that qualifies, and the lowest
    address if several tie. Any other policy raises ValueError.
    """
    raise NotImplementedError("find_block")


def coalesce(blocks):
    """Merge every run of adjacent free blocks. Returns a new list of tuples.

    Two adjacent free blocks (o1, s1, True) and (o2, s2, True) become
    (o1, s1 + HEADER + s2, True), because the second header is reclaimed.
    """
    raise NotImplementedError("coalesce")


class Allocator:
    """malloc and free over a fixed arena."""

    def __init__(self, size, policy="first"):
        """Start with the whole arena as one free block.

        Raise ValueError for an unknown policy, or a size that is not a
        multiple of ALIGN or is smaller than HEADER + ALIGN.
        """
        raise NotImplementedError("Allocator.__init__")

    def malloc(self, n):
        """Allocate n bytes and return the payload address.

        Round n up with round_up. Raise ValueError if n <= 0 and MemoryError
        if no free block fits. Split the chosen block when the leftover would
        be at least HEADER + ALIGN bytes; otherwise hand out the whole block.
        """
        raise NotImplementedError("Allocator.malloc")

    def free(self, addr):
        """Release the block whose payload starts at `addr`, then coalesce.

        Raise DoubleFree if addr lies inside the payload of a free block.
        Raise InvalidFree for any other address that is not the start of an
        allocated block's payload.
        """
        raise NotImplementedError("Allocator.free")

    def blocks(self):
        """A copy of the block list, in address order."""
        raise NotImplementedError("Allocator.blocks")

    def free_bytes(self):
        """Total payload bytes in free blocks."""
        raise NotImplementedError("Allocator.free_bytes")

    def largest_free(self):
        """Payload size of the biggest free block, or 0 if there is none."""
        raise NotImplementedError("Allocator.largest_free")

    def fragmentation(self):
        """External fragmentation: 1 - largest_free / free_bytes, or 0.0 with no free bytes."""
        raise NotImplementedError("Allocator.fragmentation")


if __name__ == "__main__":
    for policy in ("first", "best"):
        heap = Allocator(256, policy)
        a = heap.malloc(48)
        heap.malloc(8)
        b = heap.malloc(24)
        heap.malloc(8)
        heap.free(a)
        heap.free(b)
        print(f"{policy} fit: free holes", [blk for blk in heap.blocks() if blk[2]])
        print(f"  fragmentation before: {heap.fragmentation():.3f}")
        p = heap.malloc(16)
        print(f"  malloc(16) -> {p}; fragmentation after {heap.fragmentation():.3f}")
        try:
            heap.malloc(150)
        except MemoryError as exc:
            print("  malloc(150) failed:", exc)
