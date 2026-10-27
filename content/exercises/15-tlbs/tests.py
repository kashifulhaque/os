"""Checks for the TLB exercise."""

from oscheck import almost, check, equal, fail, has


@check("TLB.lookup misses, then hits after insert, and counts both")
def test_lookup(sub):
    TLB = has(sub, "TLB")
    tlb = TLB(4)
    equal(tlb.lookup(1, 5), None, label="lookup in an empty TLB")
    tlb.insert(1, 5, 42)
    equal(tlb.lookup(1, 5), 42, label="lookup after insert")
    equal((tlb.hits, tlb.misses), (1, 1), label="(hits, misses)")
    equal(tlb.hit_rate(), 0.5, label="hit_rate after 1 hit and 1 miss")
    equal(len(tlb), 1, label="len(tlb)")
    equal(TLB(4).hit_rate(), 0.0, label="hit_rate before any lookup")


@check("TLB evicts the least recently used entry when full")
def test_lru(sub):
    TLB = has(sub, "TLB")
    tlb = TLB(2)
    tlb.insert(0, 1, 10)
    tlb.insert(0, 2, 20)
    tlb.insert(0, 3, 30)   # evicts vpn 1, the oldest
    equal(len(tlb), 2, label="len after overfilling a 2-entry TLB")
    equal(tlb.lookup(0, 1), None, label="vpn 1 should be evicted")
    equal(tlb.lookup(0, 2), 20, label="vpn 2 should survive")
    equal(tlb.lookup(0, 3), 30, label="vpn 3 should survive")


@check("a TLB hit refreshes recency, so the other entry is evicted")
def test_lru_refresh(sub):
    TLB = has(sub, "TLB")
    tlb = TLB(2)
    tlb.insert(0, 1, 10)
    tlb.insert(0, 2, 20)
    equal(tlb.lookup(0, 1), 10, label="touch vpn 1")   # order is now 2 (oldest), 1
    tlb.insert(0, 3, 30)                               # must evict vpn 2
    equal(tlb.lookup(0, 2), None, label="vpn 2 should be evicted, not vpn 1")
    equal(tlb.lookup(0, 1), 10, label="vpn 1 should survive")


@check("re-inserting a cached page updates it without evicting anything")
def test_reinsert(sub):
    TLB = has(sub, "TLB")
    tlb = TLB(2)
    tlb.insert(0, 1, 10)
    tlb.insert(0, 2, 20)
    tlb.insert(0, 1, 11)   # update, vpn 1 is now most recent
    equal(len(tlb), 2, label="len after re-insert")
    equal(tlb.lookup(0, 1), 11, label="updated frame")
    equal(tlb.lookup(0, 2), 20, label="the other entry must stay")
    tlb.insert(0, 3, 30)   # the TLB is full again, so one entry goes
    equal(len(tlb), 2, label="len after one more insert")


@check("TLB entries are tagged by ASID, and flush can target one ASID")
def test_asid_flush(sub):
    TLB = has(sub, "TLB")
    tlb = TLB(8)
    tlb.insert(1, 0, 100)
    tlb.insert(2, 0, 200)
    equal(tlb.lookup(1, 0), 100, label="asid 1, vpn 0")
    equal(tlb.lookup(2, 0), 200, label="asid 2, vpn 0")
    tlb.flush(1)
    equal(len(tlb), 1, label="len after flush(1)")
    equal(tlb.lookup(1, 0), None, label="asid 1 flushed")
    equal(tlb.lookup(2, 0), 200, label="asid 2 untouched")
    tlb.flush()
    equal(len(tlb), 0, label="len after flush()")


@check("MMU.translate uses the TLB and walks the page table only on a miss")
def test_mmu(sub):
    TLB, MMU, PageFault = has(sub, "TLB"), has(sub, "MMU"), has(sub, "PageFault")
    tlb = TLB(4)
    mmu = MMU(tlb, {0: {0: 7, 1: 3}}, 4096)
    # vpn 0, offset 0x10, frame 7: 7 * 4096 + 0x10 = 0x7010.
    equal(mmu.translate(0x10), 0x7010, label="first translate (miss)")
    equal(mmu.translate(0x20), 0x7020, label="second translate, same page (hit)")
    # vpn 1, offset 0xABC, frame 3: 3 * 4096 + 0xABC = 0x3ABC.
    equal(mmu.translate(0x1ABC), 0x3ABC, label="third translate, new page (miss)")
    equal((tlb.hits, tlb.misses), (1, 2), label="(hits, misses)")
    equal(mmu.walks, 2, label="page-table walks")
    try:
        mmu.translate(0x5000)
    except PageFault:
        pass
    else:
        fail("translate of an unmapped page should raise PageFault")
    equal(len(tlb), 2, label="a PageFault must not add a TLB entry")


@check("with ASIDs a context switch keeps entries; without them it flushes")
def test_asid_vs_flush(sub):
    TLB, MMU = has(sub, "TLB"), has(sub, "MMU")
    tables = {1: {0: 10}, 2: {0: 20}}
    order = [1, 2, 1, 2, 1, 2]

    def run(use_asids):
        tlb = TLB(8)
        mmu = MMU(tlb, tables, 4096, use_asids=use_asids, asid=1)
        addrs = []
        for asid in order:
            mmu.switch(asid)
            addrs.append(mmu.translate(0x10))
        return addrs, tlb.hits, tlb.misses

    # Both processes read vpn 0 at offset 0x10: frame 10 -> 0xA010, frame 20 -> 0x14010.
    want = [0xA010, 0x14010] * 3
    addrs, hits, misses = run(True)
    equal(addrs, want, label="physical addresses with ASIDs")
    # First access of each process misses; the other four hit.
    equal((hits, misses), (4, 2), label="(hits, misses) with ASIDs")
    addrs, hits, misses = run(False)
    equal(addrs, want, label="physical addresses without ASIDs (must still be correct)")
    # Every switch flushes, so every access misses.
    equal((hits, misses), (0, 6), label="(hits, misses) without ASIDs")


@check("array_walk and simulate_walk reproduce a sequential walk")
def test_walk(sub):
    array_walk, simulate_walk = has(sub, "array_walk"), has(sub, "simulate_walk")
    equal(array_walk(0x1000, 3, 4), [0x1000, 0x1004, 0x1008], label="array_walk(0x1000, 3, 4)")
    equal(array_walk(0, 0, 8), [], label="array_walk with count 0")
    # 4096 ints * 4 bytes = 16384 bytes = 4 pages: 4 cold misses, 4092 hits.
    equal(simulate_walk(array_walk(0, 4096, 4), 16, 4096), (4092, 4), label="4096 ints of 4 bytes")
    # 16-byte structs: 4096 / 16 = 256 per page; 1024 structs = 4 pages -> 4 misses, 1020 hits.
    equal(simulate_walk(array_walk(0, 1024, 16), 16, 4096), (1020, 4), label="1024 structs of 16 bytes")
    # Even a 1-entry TLB gets the same result on a sequential walk.
    equal(simulate_walk(array_walk(0, 4096, 4), 1, 4096), (4092, 4), label="1-entry TLB")


@check("a loop over capacity + 1 pages thrashes an LRU TLB; capacity pages fit")
def test_thrash(sub):
    simulate_walk = has(sub, "simulate_walk")
    pages = [p * 4096 for p in range(5)]
    # 5 pages cycled 3 times through a 4-entry LRU TLB: the page needed next is always the one just evicted.
    equal(simulate_walk(pages * 3, 4, 4096), (0, 15), label="5 pages, 4 entries")
    # With 5 entries: 5 cold misses, then 10 hits.
    equal(simulate_walk(pages * 3, 5, 4096), (10, 5), label="5 pages, 5 entries")
    # Stride of one page (column walk): every access is a new page, no hits.
    equal(simulate_walk([i * 4096 for i in range(100)], 16, 4096), (0, 100), label="page-sized stride")


@check("sequential_hit_rate and effective_access_time match the formulas")
def test_formulas(sub):
    sequential_hit_rate = has(sub, "sequential_hit_rate")
    effective_access_time = has(sub, "effective_access_time")
    almost(sequential_hit_rate(4096, 4), 1 - 4 / 4096, 1e-12, label="4-byte ints")      # 0.99902...
    almost(sequential_hit_rate(4096, 16), 255 / 256, 1e-12, label="16-byte structs")    # 0.99609...
    almost(sequential_hit_rate(4096, 4096), 0.0, 1e-12, label="page-sized elements")
    almost(sequential_hit_rate(4096, 8192), 0.0, 1e-12, label="elements larger than a page")
    # 99% hits, 1 ns TLB, 100 ns memory, 4-level walk:
    # hit 101, miss 1 + 400 + 100 = 501; 0.99 * 101 + 0.01 * 501 = 99.99 + 5.01 = 105.0.
    almost(effective_access_time(0.99, 1, 100, levels=4), 105.0, 1e-9, label="EAT 99%, 4 levels")
    # Default levels=1: hit 101, miss 201; 0.5 * 101 + 0.5 * 201 = 151.
    almost(effective_access_time(0.5, 1, 100), 151.0, 1e-9, label="EAT 50%, 1 level")
    almost(effective_access_time(1.0, 1, 100, levels=4), 101.0, 1e-9, label="EAT 100%")
