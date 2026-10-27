"""A TLB with LRU replacement, an MMU that uses it, and hit-rate experiments.

Fill in the class methods and functions in order. A page table here is a dict
{vpn: frame}. The MMU holds one page table per process: {asid: page_table}.
"""

from collections import OrderedDict


class PageFault(Exception):
    """Raised when the page table has no mapping for a page."""


class TLB:
    """A small cache of (asid, vpn) -> frame with least-recently-used eviction."""

    def __init__(self, capacity):
        """Create an empty TLB that holds at most `capacity` entries.

        Keep `self.hits` and `self.misses` as counters that start at 0.
        """
        raise NotImplementedError("TLB.__init__")

    def lookup(self, asid, vpn):
        """Return the cached frame for (asid, vpn), or None on a miss.

        A hit counts in `self.hits` and makes the entry the most recently used.
        A miss counts in `self.misses`.
        """
        raise NotImplementedError("TLB.lookup")

    def insert(self, asid, vpn, frame):
        """Cache a translation. If the TLB is full, evict the least recently used entry.

        Inserting a key that is already present replaces its frame and makes it
        the most recently used. It never evicts another entry.
        """
        raise NotImplementedError("TLB.insert")

    def flush(self, asid=None):
        """Drop every entry. With `asid` given, drop only that process's entries."""
        raise NotImplementedError("TLB.flush")

    def hit_rate(self):
        """hits / (hits + misses), or 0.0 before any lookup."""
        raise NotImplementedError("TLB.hit_rate")

    def __len__(self):
        """Number of entries currently cached."""
        raise NotImplementedError("TLB.__len__")


class MMU:
    """Translates addresses: TLB first, page-table walk on a miss."""

    def __init__(self, tlb, page_tables, page_size=4096, use_asids=True, asid=0):
        """Remember the arguments. `asid` is the process running at the start.

        Keep `self.current` (the running asid) and `self.walks` (page-table
        walks so far, starting at 0).
        """
        raise NotImplementedError("MMU.__init__")

    def switch(self, asid):
        """Context switch to process `asid`.

        Without ASIDs (`use_asids` False), the TLB cannot tell processes apart,
        so switching to a different process flushes the whole TLB.
        """
        raise NotImplementedError("MMU.switch")

    def translate(self, vaddr):
        """Return the physical address for `vaddr` in the running process.

        Look in the TLB first. On a miss, walk page_tables[current], raise
        PageFault if the page is not there, and cache the result. Without
        ASIDs, tag every entry with 0; with ASIDs, tag it with the running asid.
        """
        raise NotImplementedError("MMU.translate")


def array_walk(base, count, elem_size):
    """Addresses of `count` consecutive elements starting at `base`.

    Example: array_walk(0x1000, 3, 4) == [0x1000, 0x1004, 0x1008]
    """
    raise NotImplementedError("array_walk")


def simulate_walk(addresses, capacity, page_size=4096):
    """Run addresses through a fresh TLB of `capacity` entries; return (hits, misses).

    Map every page the addresses touch (page n to frame n) in a single page
    table for asid 0, and use an MMU.
    """
    raise NotImplementedError("simulate_walk")


def sequential_hit_rate(page_size, elem_size):
    """TLB hit rate for a long cold walk that touches every `elem_size` bytes.

    Assume elem_size divides page_size. Each page costs one miss.
    Example: sequential_hit_rate(4096, 4) == 1 - 4 / 4096
    """
    raise NotImplementedError("sequential_hit_rate")


def effective_access_time(hit_rate, tlb_ns, mem_ns, levels=1):
    """Average nanoseconds per memory access, given a TLB hit rate.

    A hit costs tlb_ns + mem_ns. A miss costs tlb_ns, then `levels` memory
    accesses to walk the page table, then mem_ns for the data itself.
    """
    raise NotImplementedError("effective_access_time")


if __name__ == "__main__":
    # 4096 ints of 4 bytes = 16 KiB = 4 pages of 4 KiB.
    addrs = array_walk(0, 4096, 4)
    hits, misses = simulate_walk(addrs, capacity=16)
    print(f"walk of {len(addrs)} ints: {hits} hits, {misses} misses, rate {hits / len(addrs):.4f}")
    print("formula:", sequential_hit_rate(4096, 4))

    tables = {1: {0: 10}, 2: {0: 20}}
    for use_asids in (True, False):
        tlb = TLB(8)
        mmu = MMU(tlb, tables, 4096, use_asids=use_asids, asid=1)
        for step in range(6):
            mmu.switch(1 if step % 2 == 0 else 2)
            mmu.translate(0x10)
        print(f"use_asids={use_asids}: hits={tlb.hits} misses={tlb.misses}")

    print("EAT, 99% hits, 4 levels:", effective_access_time(0.99, 1, 100, levels=4), "ns")
