"""Checks for the address spaces exercise."""

from oscheck import equal, check, fail, has


def faults(sub, func, *args, **kwargs):
    """True if func raises the reader's SegmentationFault; fails on any other exception."""
    SegmentationFault = has(sub, "SegmentationFault")
    try:
        got = func(*args, **kwargs)
    except SegmentationFault:
        return True
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"expected SegmentationFault, got {type(exc).__name__}: {exc}")
    return got  # returned normally: the caller reports the value


def expect_fault(sub, label, func, *args, **kwargs):
    got = faults(sub, func, *args, **kwargs)
    if got is not True:
        fail(f"{label}: expected SegmentationFault, but the call returned {got!r}")


def process_table(sub, code=32768, heap=34816, stack=28672):
    Segment = has(sub, "Segment")
    return {
        0: Segment("code", base=code, size=2048, writable=False),
        1: Segment("heap", base=heap, size=3072),
        3: Segment("stack", base=stack, size=2048, grows_down=True),
    }


@check("split_virtual_address separates the top 2 bits from the low 12")
def test_split(sub):
    split = has(sub, "split_virtual_address")
    equal(split(100), (0, 100), label="split(100)")
    # 4200 = 1 * 4096 + 104.
    equal(split(4200), (1, 104), label="split(4200)")
    # 15360 = 3 * 4096 + 3072.
    equal(split(15360), (3, 3072), label="split(15360)")
    equal(split(16383), (3, 4095), label="split(16383)")
    expect_fault(sub, "split(16384)", split, 16384)
    expect_fault(sub, "split(-1)", split, -1)


@check("translate_base_bounds adds the base to any address below the bounds")
def test_base_bounds(sub):
    t = has(sub, "translate_base_bounds")
    equal(t(128, 16384, 4096), 16512, label="16384 + 128")
    equal(t(3000, 16384, 4096), 19384, label="16384 + 3000")
    equal(t(0, 16384, 4096), 16384, label="first byte")
    equal(t(4095, 16384, 4096), 20479, label="last byte: 16384 + 4095")


@check("translate_base_bounds faults at the bounds and on negative addresses")
def test_base_bounds_fault(sub):
    t = has(sub, "translate_base_bounds")
    expect_fault(sub, "vaddr == bounds", t, 4096, 16384, 4096)
    expect_fault(sub, "vaddr past bounds", t, 4400, 16384, 4096)
    expect_fault(sub, "negative vaddr", t, -1, 16384, 4096)


@check("translate_segmented handles code and heap, the segments that grow up")
def test_seg_up(sub):
    t = has(sub, "translate_segmented")
    table = process_table(sub)
    equal(t(100, table), 32868, label="code: 32768 + 100")
    # 4200 = segment 1, offset 104: 34816 + 104 = 34920.
    equal(t(4200, table), 34920, label="heap: 34816 + 104")
    equal(t(2047, table), 34815, label="last code byte: 32768 + 2047")
    equal(t(4096 + 3071, table), 34816 + 3071, label="last heap byte")


@check("translate_segmented maps the stack downward from its base")
def test_seg_stack(sub):
    t = has(sub, "translate_segmented")
    table = process_table(sub)
    # 15360 = segment 3, offset 3072. back = 4096 - 3072 = 1024.
    # physical = 28672 - 1024 = 27648.
    equal(t(15360, table), 27648, label="vaddr 15360")
    # Top byte: offset 4095, back 1, physical 28671.
    equal(t(16383, table), 28671, label="vaddr 16383, the top byte")
    # Lowest valid byte: size 2048 so back 2048, offset 2048, vaddr 12288 + 2048 = 14336.
    equal(t(14336, table), 28672 - 2048, label="vaddr 14336, the lowest valid byte")
    expect_fault(sub, "one byte below the stack (14335)", t, 14335, table)


@check("translate_segmented faults on unmapped segments, overruns, and writes to code")
def test_seg_faults(sub):
    t = has(sub, "translate_segmented")
    table = process_table(sub)
    expect_fault(sub, "code overrun (offset 2048)", t, 2048, table)
    expect_fault(sub, "gap between code and heap (3000)", t, 3000, table)
    expect_fault(sub, "heap overrun (offset 3072)", t, 4096 + 3072, table)
    expect_fault(sub, "unmapped segment 2", t, 8192 + 5, table)
    expect_fault(sub, "outside the address space", t, 16384, table)
    expect_fault(sub, "write to code", t, 100, table, write=True)
    equal(t(100, table, write=False), 32868, label="read of code is allowed")
    equal(t(4200, table, write=True), 34920, label="write to heap is allowed")


@check("load_byte and store_byte give two processes private memory at the same addresses")
def test_load_store(sub):
    load_byte, store_byte = has(sub, "load_byte"), has(sub, "store_byte")
    mem = bytearray(65536)
    p1 = process_table(sub)                                      # heap at 34816
    p2 = process_table(sub, code=8192, heap=10240, stack=20480)  # heap at 10240
    store_byte(mem, p1, 4200, 11)
    store_byte(mem, p2, 4200, 22)
    equal(mem[34816 + 104], 11, label="process 1's byte in physical memory")
    equal(mem[10240 + 104], 22, label="process 2's byte in physical memory")
    equal(load_byte(mem, p1, 4200), 11, label="process 1 reads its own byte")
    equal(load_byte(mem, p2, 4200), 22, label="process 2 reads its own byte")
    expect_fault(sub, "store into code", store_byte, mem, p1, 100, 1)
    expect_fault(sub, "load from unmapped segment", load_byte, mem, p1, 8200)
    equal(sum(mem), 33, label="a faulting store must not change memory")


@check("relocate moves a segment's bytes and keeps every virtual address working")
def test_relocate(sub):
    relocate = has(sub, "relocate")
    load_byte = has(sub, "load_byte")
    mem = bytearray(65536)
    table = process_table(sub)
    for i in range(3072):
        mem[34816 + i] = (i * 7) % 251
    for i in range(2048):
        mem[26624 + i] = (i * 3 + 1) % 251  # stack bytes live in 26624..28671
    before = {v: load_byte(mem, table, v) for v in (4096, 4200, 7167, 14336, 15360, 16383)}
    moved = dict(table)
    moved[1] = relocate(mem, table[1], 40960)
    moved[3] = relocate(mem, table[3], 50000)
    equal(moved[1].base, 40960, label="heap base after relocate")
    equal(moved[3].base, 50000, label="stack base after relocate")
    equal(moved[1].size, 3072, label="size is unchanged")
    equal(moved[3].grows_down, True, label="grows_down is kept")
    for v, want in before.items():
        equal(load_byte(mem, moved, v), want, label=f"load_byte at {v} after the move")
    # Overlapping move: shift the heap up by 1024 inside the same region.
    heap = moved[1]
    snapshot = bytes(mem[heap.base:heap.base + heap.size])
    shifted = relocate(mem, heap, heap.base + 1024)
    equal(bytes(mem[shifted.base:shifted.base + shifted.size]), snapshot, label="overlapping move")
    for bad_base in (65000, -5):
        try:
            relocate(mem, table[1], bad_base)
        except ValueError:
            continue
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            fail(f"relocate to {bad_base} should raise ValueError, got {type(exc).__name__}")
        fail(f"relocate to {bad_base} does not fit in 65536 bytes and should raise ValueError")
    try:
        relocate(mem, table[3], 1000)  # 1000 - 2048 < 0
    except ValueError:
        return
    fail("relocating the stack so that its low end is below address 0 should raise ValueError")


@check("exactly 7168 virtual addresses are valid, and they map to distinct bytes inside the segments")
def test_property(sub):
    t = has(sub, "translate_segmented")
    SegmentationFault = has(sub, "SegmentationFault")
    table = process_table(sub)
    valid = {}
    for vaddr in range(16384):
        try:
            valid[vaddr] = t(vaddr, table)
        except SegmentationFault:
            pass
    # code 2048 + heap 3072 + stack 2048 = 7168 valid bytes.
    equal(len(valid), 7168, label="number of valid virtual addresses")
    equal(sorted(valid)[:2], [0, 1], label="lowest valid addresses")
    want = set(range(0, 2048)) | set(range(4096, 4096 + 3072)) | set(range(14336, 16384))
    equal(set(valid), want, label="set of valid virtual addresses")
    equal(len(set(valid.values())), 7168, label="distinct physical bytes")
    allowed = set(range(32768, 34816)) | set(range(34816, 37888)) | set(range(26624, 28672))
    bad = [p for p in valid.values() if p not in allowed]
    if bad:
        fail(f"{len(bad)} translations land outside every segment's physical range, first: {bad[0]}")
