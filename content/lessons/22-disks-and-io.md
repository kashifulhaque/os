---
title: Disks, SSDs, and I/O
slug: 22-disks-and-io
part: "Part 6 — Storage and file systems"
summary: Compute how long a disk access takes from seek, rotation, and transfer, and order a queue of requests with four disk schedulers.
minutes: 55
gpu: false
objectives:
  - Compute the average time of one hard disk access from seek time, rotational latency, and transfer time.
  - Explain why random reads are far slower than sequential reads, with numbers.
  - Describe how an SSD stores data in pages and erase blocks, and what the flash translation layer does.
  - Order a request queue with FCFS, SSTF, SCAN, and C-LOOK, and compare the head movement.
prereqs:
  - 21-deadlock
exercise: 22-disks-and-io
---

# Disks, SSDs, and I/O

Memory forgets everything when the power goes off. A computer that kept
nothing between power cuts would be useless, so every computer also has
*storage*: a device that keeps its bytes for years. Your files, your programs,
and the operating system itself live there.

Storage is also slow. A read from RAM takes about a hundred nanoseconds. A read
from a spinning hard disk takes about eight *milli*seconds. That is eighty
thousand times longer. The operating system exists partly to hide this gap, and
the first step is to understand where the time goes.

In this lesson, you learn how a hard disk works, work out its access time by
hand, and see why the order in which you ask for data changes how long the
disk takes to deliver it. Then you look at the solid-state drive that has
replaced the spinning disk in most computers. You finish by writing the
arithmetic and four disk schedulers in Python.

## What you already know

- A byte is eight bits, and memory is an array of bytes with addresses.
- A scheduler picks which waiting job runs next, and different policies give different waiting times.
- A process asks the kernel to do work for it through a system call.
- A device is slower than the CPU, so the CPU should not sit idle waiting for it.

## Block devices: a disk is an array of blocks

To a programmer, a disk looks like a long array. You do not ask for "byte
7,000,000." You ask for *block* number 13,672. A block is a fixed-size chunk,
traditionally a *sector* of 512 bytes. Many modern disks use 4096-byte sectors.

The operating system sends the disk a short command: read or write block
number N. That is the whole interface. The file system you build in the next
lessons sits on top of this array and decides which blocks hold which file.

A device that you read and write in fixed-size blocks is a *block device*. On
Linux they appear as names such as `/dev/sda` or `/dev/nvme0n1`.

> [!KEY]
> A disk is an array of numbered blocks. Everything a file system does is a decision about which block numbers to read and write, and in what order.

## Inside a hard disk drive

A *hard disk drive* (HDD) stores bits as tiny magnetic patches on one or more
spinning metal platters. The picture below shows one platter from above, with
the arm that carries the read/write head.

```text
        a track (one ring)
          ___________
        /   _______   \
       /  /   ___   \  \        platter spins at a fixed speed
      |  |   | o |   |  |       (for example 7200 times a minute)
      |  |   |___|   |  |
       \  \_________/  /        o = spindle (the center)
        \_____________/
                      \
   arm  ===============*   <- head floats over one track
```

Three words matter:

- A *track* is one ring on the platter. A disk has tens of thousands of them.
- A *sector* is a slice of a track and the smallest unit the disk reads or writes.
- A *cylinder* is the same track number on every platter. The arms of all platters move together, so they sit over one cylinder at a time.

To read a sector, the disk does three things in order. Each one costs time.

1. **Seek.** The arm moves the head to the right track. This is mechanical movement. A typical average seek is 4 ms, and the full range is from about 1 ms for a neighbouring track to about 10 ms across the whole platter.
2. **Rotational latency.** The head waits until the wanted sector rotates underneath it. This is the time you wait for the right seat to come around on a merry-go-round.
3. **Transfer.** The sector passes under the head and its bits are read. The time depends on how fast bits move past the head.

## Working out the access time

The total is the sum of the three:

$$
T_{I/O} = T_{seek} + T_{rotation} + T_{transfer}
$$

### Rotational latency

A disk spinning at 7200 revolutions per minute (RPM) turns 7200 times in 60
seconds. One rotation takes:

$$
\frac{60{,}000\ \text{ms}}{7200} = 8.33\ \text{ms}
$$

You arrive at a random moment, so the sector you want is on average half a
rotation away. The average rotational latency is 4.17 ms. In the worst case
you just missed it and wait the full 8.33 ms. In the best case it is already
under the head and you wait 0 ms.

Other speeds give other numbers:

| RPM | One rotation | Average latency |
|---|---|---|
| 5400 | 11.11 ms | 5.56 ms |
| 7200 | 8.33 ms | 4.17 ms |
| 15000 | 4.00 ms | 2.00 ms |

### Transfer time

Say the disk delivers 125 megabytes per second once the head is in place. Disk
makers count a megabyte as 1,000,000 bytes, so that is 125,000 bytes per
millisecond. A 4096-byte read then takes:

$$
\frac{4096\ \text{bytes}}{125{,}000\ \text{bytes/ms}} = 0.033\ \text{ms}
$$

### Random access versus sequential access

Put the numbers together for a *random* 4 KiB read. The head must seek, wait
for rotation, and transfer:

```text
seek          4.000 ms   ##################################
rotation      4.167 ms   ###################################
transfer      0.033 ms   |
-------------------------
total         8.200 ms   -> 4096 bytes / 8.2 ms = 0.50 MB/s
```

The disk can deliver 125 MB/s, yet this access gets half a megabyte per
second. The head spends 99.6 percent of the time moving and waiting.

Now read 100 MB that sits in one contiguous run. You pay for one seek and one
rotation, then the data streams past the head:

$$
4 + 4.17 + \frac{100{,}000{,}000}{125{,}000} = 4 + 4.17 + 800 = 808.17\ \text{ms}
$$

That is 100 MB in 0.808 s, or 123.7 MB/s. It reaches 99 percent of the disk's peak
rate. The same disk is 250 times faster for sequential data than for random
4 KiB reads (123.7 divided by 0.5).

> [!KEY]
> On a hard disk, the cost of an access is almost entirely the wait before the data moves. Read big contiguous runs, and avoid scattered small reads. Every file system design in the next three lessons bends toward this fact.

## Why the order of requests matters

Many programs ask for blocks at once. The kernel keeps them in a queue. It can
send them to the disk in any order, and the order changes the total head
movement, because seek time grows with the distance the head travels.

It works like a delivery driver with a list of addresses along one long street.
Visiting them in the order the customers phoned is easy and can send the van
back and forth. Visiting them by position along the street takes less driving.

A *disk scheduler* chooses the order. Unlike a CPU scheduler, it does not
care about fairness to a job so much as it cares about total head movement.
We measure distance in tracks. In the examples below, the head starts at
track 53 on a disk with tracks 0 to 199, and the queue is:

```text
98  183  37  122  14  124  65  67
```

### FCFS: first come, first served

Serve the requests in arrival order. It is fair and simple, and it is the
baseline.

```text
tracks: 0        37  53      98   122      183       199
        |---------|---|--------|----|--------|---------|
path:   53 -> 98 -> 183 -> 37 -> 122 -> 14 -> 124 -> 65 -> 67

moves:  45 + 85 + 146 + 85 + 108 + 110 + 59 + 2 = 640 tracks
```

The head crosses the same middle tracks over and over.

### SSTF: shortest seek time first

Always go to the pending request nearest the head. The path is:

```text
53 -> 65 -> 67 -> 37 -> 14 -> 98 -> 122 -> 124 -> 183
moves: 12 + 2 + 30 + 23 + 84 + 24 + 2 + 59 = 236 tracks
```

SSTF is far better at 236 tracks. It has a flaw: *starvation*. If new
requests keep arriving near the head, a request at the far edge waits as long
as the nearby ones keep coming. Your exercise breaks ties by choosing the
lower track number, so the result is the same on every run.

### SCAN: the elevator

SCAN moves the head in one direction, serving every request on the way. At the
edge of the disk it turns around and serves the rest on the way back. It works
like an elevator that goes up to the top floor, then down to the ground floor.

Going up from track 53:

```text
53 -> 65 -> 67 -> 98 -> 122 -> 124 -> 183 -> 199 -> 37 -> 14
moves: 146 (to the top edge) + 185 (from 199 down to 14) = 331 tracks
```

No request waits longer than about two sweeps, so SCAN cannot starve anything.
It still treats the middle of the disk better than the edges, since middle
tracks are passed twice per cycle. Your version stops turning at the last
request if nothing is left behind the head, and it only goes to the edge when it
has to turn around for requests that remain. It adds the edge track to the
path in that case. The exercise states this rule in the docstring.

### C-LOOK: one direction only

*C-SCAN* serves requests in one direction only. When it reaches the top, it
jumps back to track 0 and sweeps up again. That gives every track the same
wait. *LOOK* variants go only as far as the last request, not to the edge.
*C-LOOK* combines the two: sweep up to the highest request, jump to the lowest
request, and sweep up again.

```text
53 -> 65 -> 67 -> 98 -> 122 -> 124 -> 183 -> 14 -> 37
moves: 130 (up to 183) + 169 (jump to 14) + 23 (14 up to 37) = 322 tracks
```

The jump is a long seek, but one long seek is cheaper than many short ones in
the middle, and it makes the wait more even.

Here are the four results side by side:

| Scheduler | Total movement | Weakness |
|---|---|---|
| FCFS | 640 | Zig-zags across the disk |
| SSTF | 236 | Can starve far requests |
| SCAN (up) | 331 | Edges wait longer than the middle |
| C-LOOK | 322 | One long jump per cycle |

SSTF wins on total movement here. It is not always the best choice, because
total movement is not the same as fairness.

> [!WARNING]
> The lowest total head movement is not automatically the best policy. SSTF minimises movement and can starve a request forever. The elevator-style schedulers give up a little speed in exchange for a bound on waiting.

## Solid-state drives

A *solid-state drive* (SSD) has no moving parts. It stores bits in *flash*
memory chips, as electric charge trapped in tiny cells. With no arm and no
spinning platter, there is no seek and no rotational delay. A random 4 KiB read
takes about 0.05 to 0.1 ms, roughly a hundred times faster than the HDD example
above. Sequential and random reads are much closer in cost.

Flash has odd rules that shape the whole design:

- **Pages.** You read and write in *pages*, typically 4 KiB to 16 KiB.
- **Erase blocks.** You can only erase a large group of pages at once, an *erase block* of maybe 256 pages (1 MiB or more).
- **No overwrite.** A page that holds data cannot be rewritten in place. It must be erased first, and erasing is possible only for the whole block.
- **Wear.** Each erase damages the cells slightly. A block survives a limited number of erase cycles, from a few thousand to around a hundred thousand depending on the kind of flash.

```text
one erase block (for example 256 pages)
+------+------+------+------+------+-----+
| pg 0 | pg 1 | pg 2 | pg 3 | pg 4 | ... |
+------+------+------+------+------+-----+
 write each page once, in order; erase only the whole block
```

If the SSD showed these rules to the operating system, writing to one block of
a file would force the host to erase and rewrite a whole erase block. Instead,
the drive hides them behind a *flash translation layer* (FTL), a small program
running on the drive's own controller.

The FTL keeps a table from the block number the OS used (the *logical* address)
to the physical page that holds the data. When the OS overwrites logical block
7, the FTL writes the new data to a fresh, already-erased page, updates the
table, and marks the old page as stale. Nothing is erased yet.

Later, *garbage collection* picks an erase block that is mostly stale, copies the
few live pages elsewhere, and erases it. *Wear levelling* spreads the writes so
that no block wears out far ahead of the others.

Two consequences show up in practice. First, the OS can tell the drive which
blocks it no longer uses (the *TRIM* command), so garbage collection has less
live data to copy. Second, one write from the OS can cause more than one write
inside the drive. This effect is called *write amplification*.

Everything the next lessons teach about layout still applies. SSDs prefer
large, aligned writes. But the biggest rule changes: seek-minimising schedulers
matter much less, and Linux often uses a simple no-op or a deadline-style
scheduler on SSDs.

## Talking to the device

How does the OS learn that a disk finished? With *polling*, it asks "done yet?" in a loop, which wastes CPU when the device takes milliseconds. With *interrupts*, it starts the command and runs another process. The disk sends an interrupt when it finishes, and a kernel handler wakes the waiting process. For large transfers, *direct memory access* (DMA) lets the disk copy data to RAM without the CPU touching each byte, and the CPU gets one interrupt at the end.

## Try it on your own machine

These commands show what your own storage is.

1. List block devices and whether each one spins (Linux only):

   ```bash
   lsblk -d -o NAME,ROTA,SIZE,MODEL
   ```

   `ROTA` is 1 for a rotating disk and 0 for an SSD.

2. See which scheduler the kernel uses for a device (Linux only). Replace `sda` with your device name from step 1:

   ```bash
   cat /sys/block/sda/queue/scheduler
   ```

   The name in square brackets is the active one. You are likely to see `mq-deadline`, `none`, or `bfq`, not the textbook names.

3. Watch real I/O with `iostat` from the `sysstat` package (Linux only):

   ```bash
   iostat -x 1 3
   ```

   Look at the `r_await` column, the average time in milliseconds for a read. On an HDD you see values around 5 to 15 under load. On an SSD you see well below 1.

## Build it step by step

You write two groups of functions. The first group is access-time arithmetic.
The second is four schedulers that return the path the head takes.

1. `rotational_latency_ms(rpm)` returns the average rotational latency in ms. It takes the RPM and returns half of `60000 / rpm`. The common mistake is to forget the half, which gives the worst case.
2. `transfer_time_ms(nbytes, mb_per_s)` returns milliseconds. Convert megabytes per second into bytes per millisecond: multiply by 1,000,000 and divide by 1000. The common mistake is to use 1024 × 1024 for a megabyte. This exercise counts a megabyte as 1,000,000 bytes.
3. `access_time_ms(seek_ms, rpm, nbytes, mb_per_s)` adds the seek, the average rotational latency, and the transfer time. Reuse your two functions.
4. `io_rate_mb_s(nbytes, time_ms)` returns megabytes per second. Convert milliseconds to seconds and bytes to megabytes. The common mistake is to leave the time in milliseconds and be off by 1000.
5. `total_movement(start, path)` walks the path from `start` and adds `abs(next - here)` for each stop. Use a loop with a running position. An empty path moves 0.
6. `fcfs(start, requests)` returns a copy of the requests in the given order. Return a new list, so the caller's list is untouched.
7. `sstf(start, requests)` repeatedly picks the pending request with the smallest `(distance, track)` key, removes one copy, and moves the head there. The key's second part makes ties go to the lower track. A common mistake is to call `remove` for every equal value at once. `list.remove` removes only one, which is what you want for duplicates.
8. `scan(start, requests, direction, max_track)` splits the requests into those ahead of the head and those behind it. Sort the ones ahead in the direction of travel. When any remain behind, append the edge track (`max_track` going up, `0` going down) unless the head already ends there, then add the rest in the opposite direction. Raise `ValueError` for any direction other than `"up"` or `"down"`. A request at exactly `start` counts as ahead.
9. `c_look(start, requests)` returns the requests at or above `start` in ascending order, followed by the ones below `start` in ascending order. The jump back is a real seek, and `total_movement` counts it.

## Where this breaks

- **The disk lies about its geometry.** Modern disks have more sectors on outer tracks than inner ones, remap bad sectors, and hide the true layout. The OS cannot know which block numbers are physically close, so real schedulers treat nearby block numbers as nearby tracks and hope. The drive often reorders requests itself.
- **Built-in command queues.** SATA and NVMe drives accept many requests at once and reorder them internally. The kernel's scheduler then mostly adds fairness between processes, not seek optimisation.
- **SSDs slow down.** When almost all pages hold data, garbage collection has to copy more live pages for each erase, and writes slow down. Drives keep spare capacity the OS cannot see, partly for this reason.
- **Caches hide the real cost.** The OS keeps recently used blocks in RAM, and drives have their own caches. A benchmark that runs twice can produce wildly different numbers.
- **Fairness is a separate problem.** Seek-based schedulers ignore which process asked. Linux layers fairness on top: `bfq` gives each process a share, and cgroups can limit a group's I/O.

## Further reading

- [OSTEP chapter 37: Hard Disk Drives](https://pages.cs.wisc.edu/~remzi/OSTEP/file-disks.pdf) — the access-time model and disk scheduling in the same notation as this lesson.
- [OSTEP chapter 44: Flash-based SSDs](https://pages.cs.wisc.edu/~remzi/OSTEP/file-ssd.pdf) — pages, erase blocks, the FTL, garbage collection, and wear levelling in detail.
- [iostat(1) manual page](https://man7.org/linux/man-pages/man1/iostat.1.html) — what every column of the live I/O report means.
- [Linux block layer schedulers](https://www.kernel.org/doc/html/latest/block/index.html) — kernel documentation for `mq-deadline`, `bfq`, and the rest.

## The exercise

You build the access-time model and the four schedulers in one file. The functions are `rotational_latency_ms`, `transfer_time_ms`, `access_time_ms`, `io_rate_mb_s`, `total_movement`, `fcfs`, `sstf`, `scan`, and `c_look`.

The checks compute the numbers in this lesson: 4.17 ms rotational latency, 8.2 ms for a random 4 KiB access, and head movements of 640, 236, 331, and 322 tracks on the example queue. They also test the tie rule in SSTF, both directions of SCAN, and a property check that every scheduler serves each request exactly once on random queues.
