"""Checks for the heap-allocation exercise."""

import itertools

from oscheck import almost, check, equal, fail, has


def _raises(exc, fn, *args):
    try:
        got = fn(*args)
    except exc:
        return
    fail(f"expected {exc.__name__}, but the call returned {got!r}")


def _fragmented(sub, policy):
    """Arena of 256 bytes with three free holes of payload 48, 24, and 128.

    Layout (offset, payload, free): (0,48,F) (56,8,A) (72,24,F) (104,8,A) (120,128,F).
    """
    heap = has(sub, "Allocator")(256, policy)
    a = heap.malloc(48)
    heap.malloc(8)
    b = heap.malloc(24)
    heap.malloc(8)
    heap.free(a)
    heap.free(b)
    return heap


@check("round_up rounds to a multiple of 8")
def test_round_up(sub):
    round_up = has(sub, "round_up")
    for n, want in [(1, 8), (8, 8), (9, 16), (10, 16), (16, 16), (17, 24), (100, 104)]:
        equal(round_up(n), want, label=f"round_up({n})")
    equal(round_up(10, 4), 12, label="round_up(10, 4)")


@check("find_block implements first fit and best fit")
def test_find_block(sub):
    find_block = has(sub, "find_block")
    blocks = [(0, 40, True), (48, 8, False), (64, 16, True), (88, 100, False), (196, 24, True)]
    equal(find_block(blocks, 16, "first"), 0, label="first fit for 16")
    equal(find_block(blocks, 16, "best"), 2, label="best fit for 16 (the 16-byte hole)")
    equal(find_block(blocks, 20, "first"), 0, label="first fit for 20")
    equal(find_block(blocks, 20, "best"), 4, label="best fit for 20 (the 24-byte hole)")
    equal(find_block(blocks, 41, "first"), None, label="nothing fits 41 (the 100-byte block is allocated)")
    equal(find_block(blocks, 41, "best"), None, label="best fit, nothing fits")
    ties = [(0, 24, True), (32, 8, False), (48, 24, True)]
    equal(find_block(ties, 8, "best"), 0, label="best fit tie goes to the lowest address")
    equal(find_block(blocks, 8), 0, label="default policy is first fit")
    _raises(ValueError, find_block, blocks, 8, "worst")


@check("coalesce merges runs of adjacent free blocks and reclaims headers")
def test_coalesce(sub):
    coalesce = has(sub, "coalesce")
    # Two free blocks: 16 + 8 (header) + 16 = 40.
    equal(coalesce([(0, 16, True), (24, 16, True)]), [(0, 40, True)], label="two free blocks")
    # Three in a row: 8 + 8 + 8 = 24, then 24 + 8 + 8 = 40.
    equal(coalesce([(0, 8, True), (16, 8, True), (32, 8, True)]), [(0, 40, True)], label="three free blocks")
    blocks = [(0, 16, True), (24, 16, True), (48, 16, False), (72, 8, True), (88, 8, True)]
    equal(coalesce(blocks), [(0, 40, True), (48, 16, False), (72, 24, True)], label="mixed list")
    allocated = [(0, 16, False), (24, 16, False)]
    equal(coalesce(allocated), allocated, label="allocated blocks never merge")
    equal(coalesce([]), [], label="empty list")


@check("a new Allocator is one free block, with all its metrics")
def test_fresh(sub):
    heap = has(sub, "Allocator")(128)
    # One block: 128 bytes minus an 8-byte header leaves 120 payload bytes.
    equal(heap.blocks(), [(0, 120, True)], label="blocks() of a fresh 128-byte arena")
    equal(heap.free_bytes(), 120, label="free_bytes")
    equal(heap.largest_free(), 120, label="largest_free")
    almost(heap.fragmentation(), 0.0, 1e-12, label="fragmentation")
    Allocator = has(sub, "Allocator")
    _raises(ValueError, Allocator, 100)       # not a multiple of 8
    _raises(ValueError, Allocator, 8)         # too small
    _raises(ValueError, Allocator, 64, "worst")


@check("malloc splits a block, rounds sizes up, and gives away a whole block when the leftover is tiny")
def test_malloc_split(sub):
    heap = has(sub, "Allocator")(128)
    # Block (0, 120): need 16, leftover 104 >= 16 -> (0, 16, used) + (24, 120 - 16 - 8 = 96, free).
    equal(heap.malloc(16), 8, label="first malloc(16) returns offset 0 + header 8")
    equal(heap.blocks(), [(0, 16, False), (24, 96, True)], label="blocks after malloc(16)")
    # malloc(10) rounds to 16; the free block starts at 24, payload at 32.
    equal(heap.malloc(10), 32, label="malloc(10) rounds up to 16")
    equal(heap.blocks(), [(0, 16, False), (24, 16, False), (48, 72, True)], label="blocks after malloc(10)")
    _no_split(sub)


def _no_split(sub):
    Allocator = has(sub, "Allocator")
    heap = Allocator(64)
    # Block (0, 56). malloc(48): leftover 8 < HEADER + ALIGN = 16, so no split.
    equal(heap.malloc(48), 8, label="malloc(48) in a 64-byte arena")
    equal(heap.blocks(), [(0, 56, False)], label="blocks after an unsplittable malloc")
    heap = Allocator(64)
    equal(heap.malloc(56), 8, label="exact fit")
    equal(heap.blocks(), [(0, 56, False)], label="blocks after an exact fit")
    equal(heap.free_bytes(), 0, label="free_bytes when full")
    almost(heap.fragmentation(), 0.0, 1e-12, label="fragmentation when full")


@check("malloc raises MemoryError when nothing fits, and ValueError for a bad size")
def test_errors(sub):
    Allocator = has(sub, "Allocator")
    heap = Allocator(64)
    _raises(ValueError, heap.malloc, 0)
    _raises(ValueError, heap.malloc, -4)
    _raises(MemoryError, heap.malloc, 1000)
    _raises(MemoryError, heap.malloc, 57)   # rounds to 64 > 56
    heap.malloc(56)
    _raises(MemoryError, heap.malloc, 8)    # arena is full
    equal(heap.blocks(), [(0, 56, False)], label="a failed malloc must not change the blocks")


@check("free coalesces neighbours, in any order, back to one block")
def test_free_coalesce(sub):
    Allocator = has(sub, "Allocator")
    heap = Allocator(128)
    a, b, c = heap.malloc(16), heap.malloc(16), heap.malloc(16)
    equal((a, b, c), (8, 32, 56), label="three payload addresses")
    heap.free(b)
    equal(heap.blocks(), [(0, 16, False), (24, 16, True), (48, 16, False), (72, 48, True)], label="after free(b): no neighbour is free")
    heap.free(a)   # merges with b: 16 + 8 + 16 = 40
    equal(heap.blocks(), [(0, 40, True), (48, 16, False), (72, 48, True)], label="after free(a): merges with b")
    heap.free(c)   # merges the left 40 block, c, and the tail: 40 + 8 + 16 + 8 + 48 = 120
    equal(heap.blocks(), [(0, 120, True)], label="after free(c): one block again")
    for order in itertools.permutations(range(3)):
        heap = Allocator(128)
        ptrs = [heap.malloc(16) for _ in range(3)]
        for i in order:
            heap.free(ptrs[i])
        equal(heap.blocks(), [(0, 120, True)], label=f"freeing in order {order}")
    # Freed space is reusable at the same address.
    equal(heap.malloc(16), 8, label="malloc after everything is freed")


@check("free detects double frees and addresses malloc never returned")
def test_free_errors(sub):
    Allocator, DoubleFree = has(sub, "Allocator"), has(sub, "DoubleFree")
    InvalidFree = has(sub, "InvalidFree")
    heap = Allocator(128)
    a, b = heap.malloc(16), heap.malloc(16)
    heap.free(a)
    _raises(DoubleFree, heap.free, a)           # a's block is still a separate free block
    heap.free(b)                                # everything merges into (0, 120, free)
    _raises(DoubleFree, heap.free, b)           # b now lies inside the merged free block
    _raises(DoubleFree, heap.free, a)
    heap = Allocator(128)
    p = heap.malloc(32)
    _raises(InvalidFree, heap.free, p + 1)      # inside an allocated payload
    _raises(InvalidFree, heap.free, 0)          # the header, not the payload
    _raises(InvalidFree, heap.free, 5000)       # outside the arena
    _raises(InvalidFree, heap.free, -8)
    equal(heap.blocks(), [(0, 32, False), (40, 80, True)], label="failed frees must not change the blocks")
    heap.free(p)
    equal(heap.blocks(), [(0, 120, True)], label="a valid free still works afterwards")


@check("first fit and best fit pick different holes")
def test_policies(sub):
    # Holes (offset, payload): (0, 48), (72, 24), (120, 128).
    first = _fragmented(sub, "first")
    best = _fragmented(sub, "best")
    holes = [(0, 48, True), (72, 24, True), (120, 128, True)]
    equal([b for b in first.blocks() if b[2]], holes, label="free holes, first fit arena")
    equal([b for b in best.blocks() if b[2]], holes, label="free holes, best fit arena")
    # First fit takes the 48-byte hole at offset 0 and splits it: leftover 48 - 16 - 8 = 24.
    equal(first.malloc(16), 8, label="first fit malloc(16)")
    equal(first.blocks()[:2], [(0, 16, False), (24, 24, True)], label="first fit splits the first hole")
    # Best fit takes the 24-byte hole at offset 72; leftover 8 < 16, so no split.
    equal(best.malloc(16), 80, label="best fit malloc(16)")
    equal(best.blocks()[2], (72, 24, False), label="best fit uses the whole 24-byte hole")


@check("external fragmentation is 1 - largest_free / free_bytes")
def test_fragmentation(sub):
    heap = _fragmented(sub, "first")
    # Free payloads 48 + 24 + 128 = 200; the largest is 128; 1 - 128 / 200 = 0.36.
    equal(heap.free_bytes(), 200, label="free_bytes")
    equal(heap.largest_free(), 128, label="largest_free")
    almost(heap.fragmentation(), 0.36, 1e-12, label="fragmentation")
    # 200 bytes are free in total, but no single hole holds 150.
    try:
        heap.malloc(150)
    except MemoryError:
        pass
    else:
        fail("malloc(150) should fail: free_bytes is 200 but the largest hole is 128")
    # A second arena: allocate two blocks of 16, free the first.
    heap2 = has(sub, "Allocator")(128)
    p = heap2.malloc(16)
    heap2.malloc(16)
    heap2.free(p)
    # Free blocks: (0, 16) and (48, 72): 1 - 72 / 88.
    almost(heap2.fragmentation(), 1 - 72 / 88, 1e-12, label="fragmentation with holes of 16 and 72")
