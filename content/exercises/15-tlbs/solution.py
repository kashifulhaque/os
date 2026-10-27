"""A TLB with LRU replacement, an MMU that uses it, and hit-rate experiments.

Reference solution.
"""

from collections import OrderedDict


class PageFault(Exception):
    """Raised when the page table has no mapping for a page."""


class TLB:
    """A small cache of (asid, vpn) -> frame with least-recently-used eviction."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.entries = OrderedDict()  # oldest (least recently used) first
        self.hits = 0
        self.misses = 0

    def lookup(self, asid, vpn):
        """Return the cached frame, or None on a miss. Counts the hit or miss."""
        key = (asid, vpn)
        if key in self.entries:
            self.entries.move_to_end(key)  # now the most recently used
            self.hits += 1
            return self.entries[key]
        self.misses += 1
        return None

    def insert(self, asid, vpn, frame):
        """Cache a translation, evicting the least recently used entry if full."""
        key = (asid, vpn)
        if key in self.entries:
            self.entries.move_to_end(key)
        elif len(self.entries) >= self.capacity:
            self.entries.popitem(last=False)
        self.entries[key] = frame

    def flush(self, asid=None):
        """Drop every entry, or only the entries tagged with `asid`."""
        if asid is None:
            self.entries.clear()
        else:
            for key in [k for k in self.entries if k[0] == asid]:
                del self.entries[key]

    def hit_rate(self):
        """hits / (hits + misses), or 0.0 before any lookup."""
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def __len__(self):
        return len(self.entries)


class MMU:
    """Translates addresses: TLB first, page-table walk on a miss."""

    def __init__(self, tlb, page_tables, page_size=4096, use_asids=True, asid=0):
        self.tlb = tlb
        self.page_tables = page_tables  # {asid: {vpn: frame}}
        self.page_size = page_size
        self.use_asids = use_asids
        self.current = asid
        self.walks = 0

    def switch(self, asid):
        """Context switch to process `asid`. Without ASIDs, flush the TLB."""
        if asid != self.current and not self.use_asids:
            self.tlb.flush()
        self.current = asid

    def translate(self, vaddr):
        """Return the physical address for `vaddr` in the current process."""
        vpn, offset = divmod(vaddr, self.page_size)
        tag = self.current if self.use_asids else 0
        frame = self.tlb.lookup(tag, vpn)
        if frame is None:
            self.walks += 1
            table = self.page_tables[self.current]
            if vpn not in table:
                raise PageFault(f"no mapping for page {vpn}")
            frame = table[vpn]
            self.tlb.insert(tag, vpn, frame)
        return frame * self.page_size + offset


def array_walk(base, count, elem_size):
    """Addresses of `count` consecutive elements starting at `base`."""
    return [base + i * elem_size for i in range(count)]


def simulate_walk(addresses, capacity, page_size=4096):
    """Run addresses through a fresh TLB and return (hits, misses).

    Every page the addresses touch is mapped (page n to frame n).
    """
    table = {a // page_size: a // page_size for a in addresses}
    tlb = TLB(capacity)
    mmu = MMU(tlb, {0: table}, page_size)
    for a in addresses:
        mmu.translate(a)
    return tlb.hits, tlb.misses


def sequential_hit_rate(page_size, elem_size):
    """TLB hit rate for a long cold walk that touches every elem_size bytes.

    Assumes elem_size divides page_size. One miss per page.
    """
    if elem_size >= page_size:
        return 0.0
    return 1 - elem_size / page_size


def effective_access_time(hit_rate, tlb_ns, mem_ns, levels=1):
    """Average nanoseconds per memory access, given a TLB hit rate."""
    hit = tlb_ns + mem_ns
    miss = tlb_ns + levels * mem_ns + mem_ns
    return hit_rate * hit + (1 - hit_rate) * miss


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
