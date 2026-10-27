"""Crash consistency with a write-ahead log (a journal).

Disk layout, 26 blocks of 16 bytes:

    blocks 0-9    the journal: TxBegin, up to 8 data blocks, TxEnd
    blocks 10-25  the "home" area: where the real data lives

One transaction sits in the journal at a time:

    block 0        TxBegin  : b"B", txid, n, then n home addresses
    blocks 1..n    copies of the new contents, in the same order as the addresses
    block n+1      TxEnd    : b"E", txid        <- writing this block is the commit

Transaction ids must increase from one transaction to the next.
"""

from __future__ import annotations

# --- Given: constants, the crashing Disk -------------------------------------

BLOCK_SIZE = 16
LOG_BLOCKS = 10
MAX_TX_BLOCKS = LOG_BLOCKS - 2  # TxBegin and TxEnd take two blocks
HOME_START = LOG_BLOCKS
NBLOCKS = 26


class Crash(Exception):
    """Raised by Disk.write when the simulated power cut arrives."""


class Disk:
    """Blocks of BLOCK_SIZE bytes. Each single-block write is atomic.

    Set `crash_after = k` to let k more writes succeed (counted by `writes`)
    and make the next write raise Crash before it changes anything.
    """

    def __init__(self, nblocks: int = NBLOCKS) -> None:
        self.nblocks = nblocks
        self.blocks = [bytes(BLOCK_SIZE) for _ in range(nblocks)]
        self.writes = 0
        self.crash_after = None

    def read(self, n: int) -> bytes:
        return self.blocks[n]

    def write(self, n: int, data: bytes) -> None:
        if len(data) != BLOCK_SIZE:
            raise ValueError(f"a block is {BLOCK_SIZE} bytes, got {len(data)}")
        if self.crash_after is not None and self.writes >= self.crash_after:
            raise Crash(f"power cut before write number {self.writes + 1}")
        self.blocks[n] = bytes(data)
        self.writes += 1

    def snapshot(self) -> list:
        """A copy of every block, to restore later with `restore`."""
        return list(self.blocks)

    def restore(self, snap: list) -> None:
        self.blocks = list(snap)
        self.writes = 0
        self.crash_after = None


# --- Step 1: the journal's block formats --------------------------------------


def encode_begin(txid: int, addrs: list) -> bytes:
    """TxBegin block: b"B", txid, count, then the addresses, zero-padded to BLOCK_SIZE.

    >>> encode_begin(7, [10, 12]).hex()
    '4207020a0c0000000000000000000000'
    """
    raise NotImplementedError("write this function")


def decode_begin(block: bytes):
    """Return (txid, [addresses]) for a TxBegin block, or None for any other block."""
    raise NotImplementedError("write this function")


def encode_end(txid: int) -> bytes:
    """TxEnd block: b"E", txid, zero-padded to BLOCK_SIZE."""
    raise NotImplementedError("write this function")


def decode_end(block: bytes):
    """Return the txid for a TxEnd block, or None for any other block."""
    raise NotImplementedError("write this function")


# --- Step 2: the four phases ----------------------------------------------------


def _validate(disk: Disk, txid: int, updates: dict) -> None:
    raise NotImplementedError("write this function")


def commit(disk: Disk, txid: int, updates: dict) -> None:
    """Write the transaction into the journal. Touch no home block.

    Order: TxBegin at block 0, then the data blocks at 1..n (in ascending
    home-address order), then TxEnd at block n+1. The TxEnd write is the commit
    point. That is n + 2 writes. Raise ValueError for a bad transaction.

    >>> commit(disk, 1, {10: b"a" * 16})   # writes blocks 0, 1, 2
    """
    raise NotImplementedError("write this function")


def checkpoint(disk: Disk, updates: dict) -> None:
    """Copy the new contents to their home blocks, in ascending address order."""
    raise NotImplementedError("write this function")


def free_log(disk: Disk) -> None:
    """Free the journal by overwriting TxBegin (block 0) with zeros. One write."""
    raise NotImplementedError("write this function")


def journaled_write(disk: Disk, txid: int, updates: dict) -> None:
    """Apply `updates` ({home address: new 16-byte contents}) atomically.

    commit, then checkpoint, then free_log: 2n + 3 writes for n blocks.
    """
    raise NotImplementedError("write this function")


def naive_write(disk: Disk, updates: dict) -> None:
    """The unsafe way: overwrite the home blocks directly, in ascending address order."""
    raise NotImplementedError("write this function")


# --- Step 3: recovery -----------------------------------------------------------


def recover(disk: Disk):
    """Run after a crash. Replay a committed transaction, drop an uncommitted one.

    Read block 0. If it is not a TxBegin, there is nothing to do: write
    nothing and return None. Otherwise a transaction is committed only if
    block n+1 is a TxEnd carrying the SAME txid (an older TxEnd left over
    from an earlier transaction does not count). If committed, copy the n
    journal blocks to their home addresses, free the log, and return the
    txid. If not, free the log and return None. Safe to run twice, or after
    a crash during recovery itself.
    """
    raise NotImplementedError("write this function")


if __name__ == "__main__":
    base = Disk()
    for a in range(HOME_START, HOME_START + 3):
        base.write(a, f"old-{a}".encode().ljust(BLOCK_SIZE, b"."))
    updates = {a: f"NEW-{a}".encode().ljust(BLOCK_SIZE, b".") for a in range(HOME_START, HOME_START + 3)}
    start = base.snapshot()

    def state(d):
        return "".join("N" if d.read(a)[:3] == b"NEW" else "o" for a in updates)

    total = 2 * len(updates) + 3
    print(f"a 3-block transaction takes {total} writes; crash before write k, then recover:")
    for label, writer in (("naive  ", lambda d: naive_write(d, updates)),
                          ("journal", lambda d: journaled_write(d, 1, updates))):
        row = []
        for k in range(total + 1):
            base.restore(start)
            base.crash_after = k
            try:
                writer(base)
            except Crash:
                pass
            base.crash_after = None
            recover(base)
            row.append(state(base))
        print(f"  {label}: " + " ".join(row))
    print("  o = old block, N = new block; a mix such as 'Noo' is a torn update")
