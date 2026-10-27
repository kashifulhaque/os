"""Checks for the crash consistency exercise: crash after every possible write."""

from oscheck import check, equal, fail, has

N = 16  # block size


def pad(text):
    return text.encode().ljust(N, b".")


def make_disk(sub, homes=(10, 11, 12, 13)):
    """A disk whose home blocks hold b'old-<addr>...' and whose write counter is zero."""
    disk = has(sub, "Disk")()
    for a in homes:
        disk.write(a, pad(f"old-{a}"))
    disk.writes = 0
    return disk


def new_data(addrs, tag="new"):
    return {a: pad(f"{tag}-{a}") for a in addrs}


def run_with_crash(sub, disk, k, action):
    """Run `action(disk)` with a power cut before write number k+1, then 'reboot'."""
    Crash = has(sub, "Crash")
    disk.writes = 0
    disk.crash_after = k
    try:
        action(disk)
    except Crash:
        pass
    disk.crash_after = None


def homes_state(disk, addrs):
    return [disk.read(a) for a in addrs]


@check("encode_begin, decode_begin, encode_end, and decode_end round-trip and reject other blocks")
def test_codec(sub):
    eb, db = has(sub, "encode_begin"), has(sub, "decode_begin")
    ee, de = has(sub, "encode_end"), has(sub, "decode_end")
    block = eb(7, [10, 12])
    equal(len(block), N, label="TxBegin length")
    equal(block[:5], bytes([ord("B"), 7, 2, 10, 12]), label="TxBegin first bytes")
    equal(db(block), (7, [10, 12]), label="decode_begin of encode_begin(7, [10, 12])")
    equal(db(eb(200, list(range(10, 18)))), (200, list(range(10, 18))), label="eight addresses")
    end = ee(7)
    equal(len(end), N, label="TxEnd length")
    equal(end[:2], bytes([ord("E"), 7]), label="TxEnd first bytes")
    equal(de(end), 7, label="decode_end of encode_end(7)")
    equal(db(bytes(N)), None, label="decode_begin of an all-zero block")
    equal(de(bytes(N)), None, label="decode_end of an all-zero block")
    equal(db(end), None, label="decode_begin of a TxEnd block")
    equal(de(block), None, label="decode_end of a TxBegin block")
    equal(db(pad("old-10")), None, label="decode_begin of ordinary data")


@check("commit writes TxBegin, the data copies, and TxEnd to the journal, touches no home block, and rejects bad input")
def test_commit(sub):
    commit, db, de = has(sub, "commit"), has(sub, "decode_begin"), has(sub, "decode_end")
    disk = make_disk(sub)
    updates = new_data([12, 10, 11])
    commit(disk, 5, updates)
    equal(disk.writes, 5, label="writes for a 3-block commit (begin + 3 data + end)")
    equal(db(disk.read(0)), (5, [10, 11, 12]), label="TxBegin at block 0")
    equal([disk.read(i) for i in (1, 2, 3)], [updates[10], updates[11], updates[12]], label="journal data blocks 1..3")
    equal(de(disk.read(4)), 5, label="TxEnd at block 4")
    equal(homes_state(disk, [10, 11, 12]), [pad("old-10"), pad("old-11"), pad("old-12")], label="home blocks after commit")
    for label, args in [
        ("empty transaction", (1, {})),
        ("address inside the journal", (1, {3: pad("x")})),
        ("address past the disk", (1, {26: pad("x")})),
        ("wrong block size", (1, {10: b"short"})),
        ("txid 0", (0, {10: pad("x")})),
        ("nine blocks", (1, {a: pad("x") for a in range(10, 19)})),
    ]:
        disk = make_disk(sub)
        try:
            commit(disk, *args)
        except ValueError:
            equal(disk.writes, 0, label=f"writes made before rejecting the {label}")
            continue
        fail(f"{label}: expected ValueError, but commit returned normally")
    commit(make_disk(sub), 1, {a: pad("x") for a in range(10, 18)})  # eight blocks is the maximum


@check("checkpoint copies blocks home in order, and free_log zeroes TxBegin")
def test_checkpoint(sub):
    commit, checkpoint, free_log = has(sub, "commit"), has(sub, "checkpoint"), has(sub, "free_log")
    disk = make_disk(sub)
    updates = new_data([10, 11])
    commit(disk, 2, updates)
    disk.writes = 0
    checkpoint(disk, updates)
    equal(disk.writes, 2, label="writes in checkpoint")
    equal(homes_state(disk, [10, 11]), [updates[10], updates[11]], label="home blocks after checkpoint")
    free_log(disk)
    equal(disk.writes, 3, label="writes after free_log")
    equal(disk.read(0), bytes(N), label="block 0 after free_log")


@check("journaled_write makes 2n + 3 writes and leaves the new data home with an empty log")
def test_journaled_write(sub):
    jw = has(sub, "journaled_write")
    for n in (1, 2, 4, 8):
        disk = make_disk(sub, homes=range(10, 18))
        updates = new_data(range(10, 10 + n))
        jw(disk, 1, updates)
        equal(disk.writes, 2 * n + 3, label=f"writes for a {n}-block transaction")  # begin + n + end + n + free
        equal(homes_state(disk, list(updates)), [updates[a] for a in updates], label=f"home blocks, n={n}")
        equal(disk.read(0), bytes(N), label=f"journal head, n={n}")
        other = [a for a in range(10 + n, 18)]
        equal(homes_state(disk, other), [pad(f"old-{a}") for a in other], label=f"untouched blocks, n={n}")


@check("recover on a clean disk does nothing, and replays a committed transaction after a crash before checkpoint")
def test_recover_committed(sub):
    jw, recover = has(sub, "journaled_write"), has(sub, "recover")
    disk = make_disk(sub)
    equal(recover(disk), None, label="recover on a clean disk")
    equal(disk.writes, 0, label="writes made by recover on a clean disk")
    updates = new_data([10, 12])
    # Writes: 0 begin, 1-2 data, 3 end (commit). Crash after 4 writes: the first home write is the 5th.
    run_with_crash(sub, disk, 4, lambda d: jw(d, 3, updates))
    equal(homes_state(disk, [10, 12]), [pad("old-10"), pad("old-12")], label="home blocks right after the crash")
    equal(recover(disk), 3, label="recover returns the replayed txid")
    equal(homes_state(disk, [10, 12]), [updates[10], updates[12]], label="home blocks after recovery")
    equal(disk.read(0), bytes(N), label="journal head after recovery")
    equal(recover(disk), None, label="a second recover has nothing to do")


@check("recover discards a transaction whose commit never reached the disk")
def test_recover_uncommitted(sub):
    jw, recover = has(sub, "journaled_write"), has(sub, "recover")
    updates = new_data([10, 11, 12])
    # Commit takes 5 writes (begin, 3 data, end). Crashes after 1..4 writes all lose the transaction.
    for k in range(0, 5):
        disk = make_disk(sub)
        run_with_crash(sub, disk, k, lambda d: jw(d, 4, updates))
        got = recover(disk)
        equal(got, None, label=f"recover after a crash with {k} writes done")
        equal(homes_state(disk, [10, 11, 12]), [pad("old-10"), pad("old-11"), pad("old-12")], label=f"home blocks, crash after {k} writes")
        equal(disk.read(0), bytes(N), label=f"journal head cleared, crash after {k} writes")


@check("a TxEnd left over from an earlier transaction does not commit a later one")
def test_stale_end(sub):
    jw, recover = has(sub, "journaled_write"), has(sub, "recover")
    disk = make_disk(sub)
    jw(disk, 1, new_data([10, 11], "first"))  # leaves a stale TxEnd(1) in journal block 3
    second = new_data([12, 13], "second")
    # Crash after TxBegin(2) and the first data block: block 3 still holds the stale TxEnd(1).
    run_with_crash(sub, disk, 2, lambda d: jw(d, 2, second))
    equal(recover(disk), None, label="recover must not treat TxEnd(1) as the commit of transaction 2")
    equal(homes_state(disk, [12, 13]), [pad("old-12"), pad("old-13")], label="blocks of the second transaction")
    equal(homes_state(disk, [10, 11]), [pad("first-10"), pad("first-11")], label="blocks of the first transaction")


@check("after a crash at ANY point and a recovery, the transaction is all old or all new, never half")
def test_every_crash_point(sub):
    jw, recover = has(sub, "journaled_write"), has(sub, "recover")
    for n in (1, 2, 3, 5):
        addrs = list(range(10, 10 + n))
        updates = new_data(addrs)
        old = [pad(f"old-{a}") for a in addrs]
        new = [updates[a] for a in addrs]
        total = 2 * n + 3
        commit_done = n + 2  # after this many writes the TxEnd is on disk
        for k in range(total + 1):
            disk = make_disk(sub, homes=range(10, 18))
            run_with_crash(sub, disk, k, lambda d: jw(d, 9, updates))
            recover(disk)
            got = homes_state(disk, addrs)
            want = new if k >= commit_done else old
            if got != want:
                kind = "new" if k >= commit_done else "old"
                fail(f"n={n}, power cut after {k} of {total} writes: expected every block {kind} after recovery.\n  got:  {got}\n  want: {want}")
            if disk.read(0) != bytes(N):
                fail(f"n={n}, power cut after {k} writes: the journal head should be cleared after recovery")


@check("without a journal a crash can tear a transaction, and recovery can itself crash and be re-run")
def test_naive_and_nested(sub):
    naive, jw, recover = has(sub, "naive_write"), has(sub, "journaled_write"), has(sub, "recover")
    addrs = [10, 11, 12]
    updates = new_data(addrs)
    old = [pad(f"old-{a}") for a in addrs]
    new = [updates[a] for a in addrs]
    torn = 0
    for k in range(4):
        disk = make_disk(sub)
        run_with_crash(sub, disk, k, lambda d: naive(d, updates))
        equal(disk.writes, k, label=f"writes made by naive_write before the cut at {k}")
        state = homes_state(disk, addrs)
        if state not in (old, new):
            torn += 1
    if torn != 2:
        fail(f"naive_write cut after 0, 1, 2, or 3 writes should tear in exactly 2 cases (after 1 and 2 writes), found {torn}")
    # Crash during recovery: committed transaction, cut at each write of recover, then recover again.
    for j in range(5):
        disk = make_disk(sub)
        run_with_crash(sub, disk, 6, lambda d: jw(d, 2, updates))  # begin, 3 data, end, then 1 home write
        run_with_crash(sub, disk, j, recover)
        equal(recover(disk), 2 if j < 4 else None, label=f"recover after a crash during recovery (cut {j})")
        equal(homes_state(disk, addrs), new, label=f"home blocks after re-running recovery (cut {j})")


@check("a sequence of transactions with a crash at any write leaves a state after some whole prefix")
def test_sequence(sub):
    jw, recover = has(sub, "journaled_write"), has(sub, "recover")
    txs = [new_data([10, 11], "a"), new_data([11, 12, 13], "b"), new_data([10, 13], "c")]
    homes = [10, 11, 12, 13]
    states = []
    base = make_disk(sub)
    cur = {a: pad(f"old-{a}") for a in homes}
    states.append([cur[a] for a in homes])
    for tx in txs:
        cur.update(tx)
        states.append([cur[a] for a in homes])

    def workload(d):
        for i, tx in enumerate(txs):
            jw(d, i + 1, tx)

    writes_per_tx = [2 * len(t) + 3 for t in txs]
    total = sum(writes_per_tx)
    snap = base.snapshot()
    for k in range(total + 1):
        base.restore(snap)
        run_with_crash(sub, base, k, workload)
        recover(base)
        got = homes_state(base, homes)
        # Transactions i whose TxEnd write index is below k are committed.
        committed, used = 0, 0
        for w, t in zip(writes_per_tx, txs):
            if k >= used + len(t) + 2:
                committed += 1
            used += w
        if got != states[committed]:
            fail(f"power cut after {k} of {total} writes: expected the state after {committed} whole transactions.\n  got:  {got}\n  want: {states[committed]}")
