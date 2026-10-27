---
title: Crash consistency and journaling
slug: 25-crash-consistency-and-journaling
part: "Part 6 — Storage and file systems"
summary: Survive a power cut in the middle of a multi-block update with a write-ahead log, and test recovery after every possible write.
minutes: 65
gpu: false
objectives:
  - Explain how a crash between two block writes leaves a file system inconsistent.
  - Describe fsck and why it cannot scale, and how a write-ahead log avoids it.
  - Write a journal with TxBegin, data blocks, TxEnd, checkpoint, and free steps in the right order.
  - Recover from a simulated crash after any write by replaying only committed transactions.
prereqs:
  - 24-building-a-file-system
exercise: 25-crash-consistency-and-journaling
---

# Crash consistency and journaling

Last lesson, creating one small file took about a dozen separate changes on
the disk. A disk can write one block at a time. So what happens if the power
fails after change number seven?

The disk is then in a state that no sequence of correct operations ever
produced. Maybe the directory names a file whose inode was never written. Maybe
the bitmap says a block is free while an inode still points to it. The file
system is *inconsistent*, and the next program to touch it could lose data or
make it worse.

This is the *crash-consistency problem*. In this lesson, you see why it is
hard, how old systems repaired it, and how nearly every modern file system
solves it with a trick borrowed from databases: write down what you are about
to do before you do it. You then build that trick and test it by cutting the
power after every single write.

## What you already know

- A file system update touches several blocks: bitmaps, inodes, directories, and data.
- The disk writes whole blocks, and a single block write is atomic. It either lands or it does not.
- The operating system caches blocks in memory, so a write to the disk can happen later than the system call.
- A bitmap bit says whether an inode or data block is in use.

## The crash-consistency problem

Take the smallest interesting update: appending one block of data to a file.
It needs three writes:

1. The data block with the new bytes.
2. The inode, with the new size and a pointer to the new block.
3. The data bitmap, with the bit for the new block set to 1.

The power can fail between any two of them. The table shows what is left on
disk when exactly one of the three writes made it:

| Only this write landed | Result on disk |
|---|---|
| Data block | The bytes are on disk, but nothing points to them and the bitmap says the block is free. The append is lost. This is harmless. |
| Inode | The inode points to a block that has garbage in it, and the bitmap says the block is free. The file system is inconsistent, and the block may be handed to another file. |
| Bitmap | The bitmap marks a block used that no inode owns. It is a *space leak*. The block is lost until something finds it. |

Two of the three are real damage, and combinations are worse. The root cause
is that the three writes are not one atomic action. The disk guarantees
atomicity for one block and nothing more.

> [!KEY]
> A disk is atomic per block. A file system needs atomicity per operation. Closing that gap is the whole job of crash consistency.

## The old answer: fsck

Early Unix file systems did nothing special. After a crash, a program called
`fsck` (file system check) ran at boot. It read *the whole disk* and looked for
contradictions. It checked that every block marked used belonged to some inode, that
every inode's blocks were marked used, and that directory entries named valid
inodes. Where it found a conflict, it fixed it.

`fsck` has two serious limits:

- **It cannot always recover the lost work.** It can make the disk consistent, but it does not know what you meant to write. In the case where only the inode landed, it can clear the pointer or accept garbage. Both lose data.
- **It is far too slow.** It reads every inode and every block. On a 10 TB disk that takes hours, and the cost grows with the size of the disk, not with how much was in flight when the power failed.

If only a handful of blocks were being written, why scan everything? That
question leads to the journal.

## The modern answer: write-ahead logging

A *write-ahead log*, also called a *journal*, is a small reserved area of the
disk. Before changing the real locations, the file system writes down a
complete description of the change in the journal. Only when that description is
safely on disk does it touch the real data.

Think of a careful chef who writes the plan on a card before cutting anything.
"Move the vegetables from bowl A to bowl B, then wash bowl A." If the kitchen
catches fire halfway, a colleague can read the card and finish the job. And if
the fire came while the chef was still writing the card, the colleague sees an
unfinished card and ignores it.

A group of changes that must all happen or none is a *transaction*. Each
transaction in our journal has a fixed shape:

```text
journal region (blocks 0-9)             home region (blocks 10-25)

 block 0   +-----------------------+    +---+---+---+---+---+---+---+
           | TxBegin  id=5         |    |10 |11 |12 |13 |14 |...|25 |
           | addrs = [10, 12]      |    +---+---+---+---+---+---+---+
 block 1   +-----------------------+     the real data lives here
           | copy of new block 10  |
 block 2   +-----------------------+
           | copy of new block 12  |
 block 3   +-----------------------+
           | TxEnd    id=5         |   <-- writing this block is the COMMIT
           +-----------------------+
```

Here is what happens when you apply a transaction that rewrites blocks 10 and
12. The steps run in this order, and the order is everything:

1. **Journal write.** Write `TxBegin` at block 0, saying "transaction 5 changes home blocks 10 and 12." Then write the new contents of both blocks into journal blocks 1 and 2.
2. **Commit.** Write `TxEnd` for transaction 5 at block 3. This single block write is the *commit point*. Before it, the transaction does not exist. After it, the transaction is promised.
3. **Checkpoint.** Copy the new contents to their home blocks, 10 and 12.
4. **Free.** Mark the journal slot as empty by overwriting `TxBegin` with zeros.

Count the writes for a transaction of $n$ blocks: one begin, $n$ data copies, one
end, $n$ home writes, and one free. That is $2n + 3$ writes, so about twice the
data. This is the price of safety.

### Why the commit must be a separate step

You could write `TxBegin`, the data, and `TxEnd` all at once and let the disk
choose the order. Disks do reorder writes for speed. If `TxEnd` reached the platter
before the data, a crash there leaves a *committed* transaction with garbage
inside. The recovery code would replay the garbage into your files. So the file
system writes `TxBegin` and the data blocks, waits until they are on disk, and
only then writes `TxEnd`. The wait uses a *cache flush* or *barrier* command that makes
the drive empty its write cache before it returns.

## Recovery

When the system starts after a crash, it runs recovery before anything else
touches the disk. Recovery reads block 0 of the journal and asks two questions:

1. Is there a `TxBegin`? If block 0 is zeros, there is nothing to do.
2. Is there a matching `TxEnd`? A transaction touching $n$ blocks has its `TxEnd` at block
   $n + 1$. If that block holds a `TxEnd` with the same transaction id, the
   transaction committed.

A committed transaction is *replayed*: recovery copies each journal block to its
home address, then frees the log. An uncommitted transaction is *discarded*:
recovery frees the log and changes no home block.

Now walk through a transaction of $n = 3$ blocks, for home addresses 10, 11, and 12. It takes nine writes. The table shows what is on disk if the power fails just before each write, and what recovery does about it:

| Crash happens before write | What is on disk | Recovery does | Home blocks end up |
|---|---|---|---|
| 1 (TxBegin) | Nothing | Nothing to do | all old |
| 2 (data 1) | TxBegin | No TxEnd, discard | all old |
| 3 (data 2) | TxBegin, 1 copy | No TxEnd, discard | all old |
| 4 (data 3) | TxBegin, 2 copies | No TxEnd, discard | all old |
| 5 (TxEnd) | TxBegin, 3 copies | No TxEnd, discard | all old |
| 6 (home 10) | Committed | Replay all three | all new |
| 7 (home 11) | Committed, 10 new | Replay all three | all new |
| 8 (home 12) | Committed, 10 and 11 new | Replay all three | all new |
| 9 (free) | Committed, all home new | Replay (a repeat) | all new |
| after 9 | Log empty | Nothing to do | all new |

Every row ends with all old or all new, and never a mixture. That property is
*atomicity*. The line between the two outcomes is write 5, the commit.

> [!KEY]
> A journal makes a multi-block update atomic by making one single-block write the commit point. Before it, recovery throws the transaction away. After it, recovery finishes the job.

### Replay must be safe to repeat

Recovery can itself be interrupted by another power cut. The next boot runs
recovery again, which must give the same final answer. Replaying is *idempotent*,
meaning that doing it twice has the same effect as doing it once. Copying the same journal
block to the same home block a second time changes nothing. The log is freed
last, so any interrupted replay is redone.

### A pitfall: stale commit blocks

Once a transaction is freed, only block 0 is erased. The old `TxEnd` is still
sitting in the journal. The next transaction may put its `TxBegin` at block 0 and
crash before its own `TxEnd` lands. If its `TxEnd` position matches the old one
and recovery only asks "is there a `TxEnd` there?", it would wrongly treat the
old one as a commit. This is why a `TxEnd` carries a transaction id, and the ids must increase.
Recovery accepts a commit only when the ids match.

## Journaling modes in real file systems

Writing every changed block twice is expensive. Real file systems choose how much
to journal.

- **Data journaling** logs file contents and metadata, exactly what you build here. It is the safest and the slowest, because all data is written twice.
- **Metadata journaling** logs only metadata: inodes, bitmaps, and directory blocks. File data goes straight to its home. The risk is that metadata could commit and point at a data block that was not written yet.
- **Ordered mode** is metadata journaling with a rule: write the data blocks to their home first, then commit the metadata transaction. A crash can then lose the newest data, but the metadata never points at garbage. ext4 uses this by default (`data=ordered`).

*Metadata* means data about data: the inodes, bitmaps, and directories, as
opposed to the contents of a file.

## Copy-on-write

Some file systems skip the journal. A *copy-on-write* file system, such as ZFS
and Btrfs, never overwrites a block in place. To change a file it writes the new
version of every block it must change to *new* locations, including the blocks
that point to them, all the way up the tree. Then it changes one root pointer to
the new tree, in a single atomic write. A crash before the pointer flips leaves the
old tree fully intact. A crash after leaves the new one.

The commit point is the same idea as `TxEnd`: one atomic write that decides
between old and new. The cost is different. Copy-on-write spreads a file's blocks
around over time, and it needs garbage collection of the old versions.

## Try it on your own machine

1. See whether your root file system has a journal (Linux, ext4):

   ```bash
   mount | grep ' / '
   ```

   Look for `ext4`, `xfs`, or `btrfs` in the output. ext4 and xfs journal. Btrfs is copy-on-write.

2. Make an ext4 image and read its journal settings (Linux, needs `e2fsprogs`, no root):

   ```bash
   dd if=/dev/zero of=/tmp/j.img bs=1M count=32
   mkfs.ext4 -q /tmp/j.img
   dumpe2fs -h /tmp/j.img 2>/dev/null | grep -i journal
   ```

   Look for `Journal size` and the feature `has_journal`. The default journal on a small file system is a few megabytes.

3. Check a file system with `fsck` on the image, which is safe because it is not mounted (Linux):

   ```bash
   e2fsck -fn /tmp/j.img
   ```

   The `-n` flag means "report problems but fix nothing." You see the passes `fsck` makes: inodes, blocks, directory structure, and reference counts.

4. Force data to disk the way a careful program does:

   ```python
   import os
   fd = os.open("/tmp/important.txt", os.O_WRONLY | os.O_CREAT, 0o644)
   os.write(fd, b"must survive a power cut\n")
   os.fsync(fd)   # wait until the kernel has pushed it to the device
   os.close(fd)
   ```

   Run `strace -e trace=fsync python3 script.py` (Linux) to see the call. Without `fsync`, the bytes may sit in memory for many seconds.

## Build it step by step

You write the journal and its recovery. The starter gives you `Disk`, a disk of
26 blocks of 16 bytes that can simulate a power cut. Setting `disk.crash_after = k`
lets `k` writes succeed and makes the next one raise `Crash` *before* it changes
anything. The journal is blocks 0 to 9, and the home blocks are 10 to 25.

1. `encode_begin(txid, addrs)` returns a 16-byte block: the byte `b"B"`, the txid, the count, then the addresses, padded with zeros. `decode_begin(block)` returns `(txid, [addrs])`, or `None` when the first byte is not `B`. `encode_end(txid)` and `decode_end(block)` do the same for `b"E"`. The mistake is forgetting that a zero block must decode to `None`.
2. `commit(disk, txid, updates)` takes a dict from home address to 16 bytes of new contents. It writes `TxBegin` at block 0, the copies at blocks 1 to $n$, in sorted address order, then `TxEnd` at block $n + 1$. It touches no home block, and it raises `ValueError` for an empty transaction, more than eight blocks, an address outside the home area, or a block of the wrong size. Validate before the first write.
3. `checkpoint(disk, updates)` writes the home blocks in sorted order. `free_log(disk)` writes zeros over block 0.
4. `journaled_write(disk, txid, updates)` calls the three in order. The mistake is writing `TxEnd` before the data copies.
5. `naive_write(disk, updates)` overwrites home blocks directly. It is the unsafe baseline that the checks use to show a torn update.
6. `recover(disk)` reads block 0. With no `TxBegin`, it returns `None` and writes nothing. With one, it looks at block $n + 1$. If that is a `TxEnd` with the same txid, copy each journal block to its home address, free the log, and return the txid. Otherwise free the log and return `None`.

The most important check cuts the power before every write of a transaction in
turn, runs `recover`, and tests that the home blocks are all old before the
commit write and all new after it. Another check cuts the power in the middle
of `recover` itself.

## Where this breaks

- **Disks lie about durability.** A drive can say "done" while data waits in its volatile write cache. The journal's ordering then means nothing. File systems issue flush commands to enforce order, and they slow down as a result.
- **Torn blocks.** The model assumes that a single block write is atomic. Real disks can tear a sector. Real journals add a checksum to each transaction, so recovery can tell a complete commit from a half-written one.
- **The journal is a bottleneck.** One journal means transactions commit one at a time, and every write goes through it. Real file systems batch many operations into one transaction and commit every few seconds.
- **Journaling guards the file system, not your data.** After a crash, the file system structure is sound, but the last few seconds of your writes may be gone. A program that needs a write to survive must call `fsync`, and a database does so on every commit.
- **fsck still exists.** Journaling covers crashes. It does not cover a bad disk, a bug in the kernel, or a flipped bit. That is why `fsck` and checksums, as in ZFS and Btrfs, remain.

## Further reading

- [OSTEP chapter 42: Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf) — the lost-write scenarios, `fsck`, and data and metadata journaling with timelines like the one above.
- [OSTEP chapter 43: Log-structured File Systems](https://pages.cs.wisc.edu/~remzi/OSTEP/file-lfs.pdf) — a file system that is a log, and where copy-on-write ideas begin.
- [ext4 journal documentation](https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html) — the real on-disk journal format, with descriptor, data, and commit blocks.
- [fsync(2) manual page](https://man7.org/linux/man-pages/man2/fsync.2.html) — what the call promises and what it does not.
- [e2fsck(8) manual page](https://man7.org/linux/man-pages/man8/e2fsck.8.html) — the passes a real file system checker makes.

## The exercise

You build a write-ahead log on a 26-block disk that can lose power on command. The functions are `encode_begin`, `decode_begin`, `encode_end`, `decode_end`, `commit`, `checkpoint`, `free_log`, `journaled_write`, `naive_write`, and `recover`.

The checks verify block formats, write counts ($2n + 3$), and the exact blocks written in each phase. Then they cut the power before every single write of transactions of one to five blocks and require that, after `recover`, the home blocks are all old before the commit and all new after it. They check that a stale `TxEnd` is ignored, that a crash during recovery is repaired by running it again, and that a sequence of transactions ends in a state that follows from some whole prefix of them.
