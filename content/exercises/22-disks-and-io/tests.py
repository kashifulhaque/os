"""Checks for the disks and I/O exercise."""

import random

from oscheck import almost, check, equal, fail, has

# Textbook queue: head at 53 on a disk with tracks 0..199.
QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]


@check("rotational_latency_ms is half a rotation: 7200 RPM gives 4.1667 ms")
def test_rotation(sub):
    f = has(sub, "rotational_latency_ms")
    # 60000 / 7200 = 8.3333 ms per rotation; half is 4.1667 ms.
    almost(f(7200), 4.16667, 1e-4, label="rotational_latency_ms(7200)")
    # 60000 / 15000 = 4 ms per rotation; half is 2 ms.
    almost(f(15000), 2.0, 1e-9, label="rotational_latency_ms(15000)")
    # 60000 / 5400 = 11.1111 ms; half is 5.5556 ms.
    almost(f(5400), 5.55556, 1e-4, label="rotational_latency_ms(5400)")


@check("transfer_time_ms divides bytes by bytes per millisecond")
def test_transfer(sub):
    f = has(sub, "transfer_time_ms")
    # 100 MB/s = 100,000 bytes per ms, so 1,000,000 bytes take 10 ms.
    almost(f(1_000_000, 100), 10.0, 1e-9, label="1 MB at 100 MB/s")
    # 4096 / 125,000 = 0.032768 ms.
    almost(f(4096, 125), 0.032768, 1e-9, label="4096 bytes at 125 MB/s")


@check("access_time_ms adds seek, rotational latency, and transfer")
def test_access(sub):
    f = has(sub, "access_time_ms")
    # 4 + 4.16667 + 0.032768 = 8.199435
    almost(f(4.0, 7200, 4096, 125), 8.199435, 1e-4, label="random 4 KiB read")
    # Sequential: no seek, no rotation worth counting; here 0 + 2 + 10 = 12 ms.
    almost(f(0.0, 15000, 1_000_000, 100), 12.0, 1e-9, label="1 MB at 15000 RPM, no seek")


@check("io_rate_mb_s shows why random 4 KiB reads crawl and sequential reads fly")
def test_rate(sub):
    rate = has(sub, "io_rate_mb_s")
    access = has(sub, "access_time_ms")
    almost(rate(1_000_000, 10), 100.0, 1e-9, label="io_rate_mb_s(1 MB, 10 ms)")
    # 4096 bytes in 8.199435 ms = 0.4995 MB/s.
    random_rate = rate(4096, access(4.0, 7200, 4096, 125))
    almost(random_rate, 0.49955, 1e-3, label="random 4 KiB rate")
    # One 100 MB transfer after one seek + rotation: 100e6 / (125e6/1000) = 800 ms, +8.1667 ms.
    seq = rate(100_000_000, access(4.0, 7200, 100_000_000, 125))
    almost(seq, 123.7, 0.1, label="sequential 100 MB rate")


@check("fcfs keeps arrival order and total_movement adds up head travel (640 tracks)")
def test_fcfs(sub):
    fcfs = has(sub, "fcfs")
    total = has(sub, "total_movement")
    order = fcfs(53, QUEUE)
    equal(order, QUEUE, label="fcfs order")
    # 45 + 85 + 146 + 85 + 108 + 110 + 59 + 2 = 640
    equal(total(53, order), 640, label="total_movement for FCFS")
    equal(total(10, []), 0, label="total_movement of an empty path")
    if QUEUE != [98, 183, 37, 122, 14, 124, 65, 67]:
        fail("fcfs must not modify the list it is given")


@check("sstf picks the nearest track (236 tracks), breaks ties low, serves duplicates once")
def test_sstf(sub):
    sstf = has(sub, "sstf")
    total = has(sub, "total_movement")
    order = sstf(53, QUEUE)
    equal(order, [65, 67, 37, 14, 98, 122, 124, 183], label="sstf order")
    # 12 + 2 + 30 + 23 + 84 + 24 + 2 + 59 = 236
    equal(total(53, order), 236, label="total_movement for SSTF")
    # 40 and 60 are both 10 from 50: 40 wins. Then from 40: 60 (20) vs 30 (10) -> 30.
    equal(sstf(50, [60, 40, 30]), [40, 30, 60], label="sstf(50, [60, 40, 30])")
    equal(sstf(10, [10, 10, 12]), [10, 10, 12], label="sstf with duplicates")


@check("scan going up sweeps to the edge, then back down (331 tracks on the textbook queue)")
def test_scan_up(sub):
    scan = has(sub, "scan")
    total = has(sub, "total_movement")
    path = scan(53, QUEUE, "up", 199)
    equal(path, [65, 67, 98, 122, 124, 183, 199, 37, 14], label="scan up path")
    # 53 -> 199 is 146, then 199 -> 14 is 185: 331.
    equal(total(53, path), 331, label="total_movement for SCAN up")


@check("scan going down mirrors it, and skips the edge when nothing lies behind the head")
def test_scan_down(sub):
    scan = has(sub, "scan")
    total = has(sub, "total_movement")
    path = scan(53, QUEUE, "down", 199)
    equal(path, [37, 14, 0, 65, 67, 98, 122, 124, 183], label="scan down path")
    # 53 -> 0 is 53, then 0 -> 183 is 183: 236.
    equal(total(53, path), 236, label="total_movement for SCAN down")
    # Nothing is below 20, so going up never reaches the edge.
    equal(scan(20, [30, 25], "up", 99), [25, 30], label="no requests behind the head")
    # A request at the head's own track is served first; the head already at the edge adds no extra stop.
    equal(scan(50, [50, 99, 10], "up", 99), [50, 99, 10], label="head at start, last request is the edge")
    try:
        scan(50, [1], "sideways", 99)
    except ValueError:
        pass
    else:
        fail("scan should raise ValueError for a direction other than 'up' or 'down'")


@check("c_look sweeps up, jumps to the lowest request, and sweeps up again (322 tracks)")
def test_clook(sub):
    c_look = has(sub, "c_look")
    total = has(sub, "total_movement")
    path = c_look(53, QUEUE)
    equal(path, [65, 67, 98, 122, 124, 183, 14, 37], label="c_look path")
    # 53 -> 183 is 130, jump to 14 is 169, then 14 -> 37 is 23: 322.
    equal(total(53, path), 322, label="total_movement for C-LOOK")
    equal(c_look(50, [50, 10]), [50, 10], label="request at the start track")


@check("every scheduler serves every request exactly once on random queues")
def test_property(sub):
    fcfs, sstf = has(sub, "fcfs"), has(sub, "sstf")
    scan, c_look = has(sub, "scan"), has(sub, "c_look")
    rng = random.Random(0)
    for trial in range(40):
        start = rng.randrange(100)
        reqs = [rng.randrange(100) for _ in range(rng.randrange(0, 12))]
        paths = {
            "fcfs": fcfs(start, reqs),
            "sstf": sstf(start, reqs),
            "c_look": c_look(start, reqs),
            "scan up": scan(start, reqs, "up", 99),
            "scan down": scan(start, reqs, "down", 99),
        }
        for name, path in paths.items():
            rest = list(path)
            for r in reqs:
                if r not in rest:
                    fail(f"{name} dropped request {r} (start={start}, requests={reqs}, path={path})")
                rest.remove(r)
            allowed = [[]]
            if name == "scan up":
                allowed.append([99])
            if name == "scan down":
                allowed.append([0])
            if rest not in allowed:
                fail(f"{name} visited extra tracks {rest} (start={start}, requests={reqs}, path={path})")
