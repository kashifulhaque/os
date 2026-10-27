"""A free-list allocator over a fixed arena.

Reference solution. The arena is `size` bytes at integer offsets 0..size-1.
Every block is a HEADER-byte header followed by its payload. A block is the
tuple (offset, payload_size, is_free). Blocks tile the arena exactly, so
sum(HEADER + payload_size) == size. `malloc` returns offset + HEADER.
"""

HEADER = 8  # bytes of bookkeeping in front of every block
ALIGN = 8   # payload sizes are rounded up to a multiple of this


class DoubleFree(Exception):
    """free() was given an address that already lies in free space."""


class InvalidFree(Exception):
    """free() was given an address that malloc never returned."""


def round_up(n, align=ALIGN):
    """Round n up to the next multiple of align."""
    return (n + align - 1) // align * align


def find_block(blocks, need, policy="first"):
    """Return the index of the free block to use for `need` payload bytes, or None."""
    if policy not in ("first", "best"):
        raise ValueError(f"unknown policy {policy!r}")
    best = None
    for i, (offset, size, is_free) in enumerate(blocks):
        if not is_free or size < need:
            continue
        if policy == "first":
            return i
        if best is None or size < blocks[best][1]:  # strict <: lowest address wins ties
            best = i
    return best


def coalesce(blocks):
    """Merge every run of adjacent free blocks. Returns a new list of tuples."""
    merged = []
    for block in blocks:
        offset, size, is_free = block
        if merged and is_free and merged[-1][2]:
            last_offset, last_size, _ = merged[-1]
            # The second block's header disappears into the merged payload.
            merged[-1] = (last_offset, last_size + HEADER + size, True)
        else:
            merged.append((offset, size, is_free))
    return merged


class Allocator:
    """malloc and free over a fixed arena."""

    def __init__(self, size, policy="first"):
        if policy not in ("first", "best"):
            raise ValueError(f"unknown policy {policy!r}")
        if size % ALIGN != 0 or size < HEADER + ALIGN:
            raise ValueError(f"arena size must be a multiple of {ALIGN} and at least {HEADER + ALIGN}")
        self.size = size
        self.policy = policy
        self._blocks = [(0, size - HEADER, True)]

    def malloc(self, n):
        """Allocate n bytes and return the payload address."""
        if n <= 0:
            raise ValueError("malloc size must be positive")
        need = round_up(n)
        i = find_block(self._blocks, need, self.policy)
        if i is None:
            raise MemoryError(f"no free block of {need} bytes")
        offset, size, _ = self._blocks[i]
        if size - need >= HEADER + ALIGN:
            # Split: the front becomes the allocation, the rest stays free.
            self._blocks[i] = (offset, need, False)
            rest = (offset + HEADER + need, size - need - HEADER, True)
            self._blocks.insert(i + 1, rest)
        else:
            # Too small a leftover to be a block: hand out the whole thing.
            self._blocks[i] = (offset, size, False)
        return offset + HEADER

    def free(self, addr):
        """Release the block whose payload starts at addr, then coalesce."""
        for i, (offset, size, is_free) in enumerate(self._blocks):
            start = offset + HEADER
            if is_free:
                if start <= addr < start + size:
                    raise DoubleFree(f"address {addr} is already free")
            elif addr == start:
                self._blocks[i] = (offset, size, True)
                self._blocks = coalesce(self._blocks)
                return
        raise InvalidFree(f"address {addr} was not returned by malloc")

    def blocks(self):
        """A copy of the block list, in address order."""
        return list(self._blocks)

    def free_bytes(self):
        """Total payload bytes in free blocks."""
        return sum(size for _, size, is_free in self._blocks if is_free)

    def largest_free(self):
        """Payload size of the biggest free block, or 0 if there is none."""
        return max((size for _, size, is_free in self._blocks if is_free), default=0)

    def fragmentation(self):
        """External fragmentation: 1 - largest_free / free_bytes, or 0.0 with no free bytes."""
        total = self.free_bytes()
        if total == 0:
            return 0.0
        return 1 - self.largest_free() / total


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
