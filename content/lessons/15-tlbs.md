---
title: Translation lookaside buffers
slug: 15-tlbs
part: "Part 4 — Memory"
summary: Cache recent address translations in a tiny LRU buffer, then measure hit rates and the cost of context switches.
minutes: 50
gpu: false
objectives:
  - Explain why paging needs a cache of translations, and why that cache works.
  - Compute the TLB hit rate of a sequential array walk by hand.
  - Implement a TLB with least-recently-used eviction in front of a page table.
  - Compare ASID tags with flushing the TLB on a context switch.
prereqs:
  - 14-paging
exercise: 15-tlbs
---

# Translation lookaside buffers

Paging has a cost. Without help, every load or store the program makes needs extra memory reads to walk the page table first. On x86-64 that means four table reads before the one read the program asked for. The computer would run at one fifth of its speed.

Real machines run nearly at full speed anyway. The trick is a cache: a small, fast memory that remembers recent translations. If the program touches a page it used a moment ago, the hardware skips the walk.

This cache is the **translation lookaside buffer**, or TLB. The name is historical, and "address translation cache" would describe it better. This lesson builds one, measures how well it works on arrays, and shows what a context switch does to it.

## What you already know

- A virtual address splits into a page number and an offset.
- A page table maps page numbers to frame numbers. A multi-level table needs one memory read per level.
- An invalid or forbidden access raises `PageFault`.
- A process is a running program with its own address space, and the kernel switches the CPU between processes.
- A cache keeps a few recent results so that repeated requests are fast.

## Why a cache works: locality

A cache helps only if programs ask for the same things again. Programs do. This habit is called **locality**:

- **Temporal locality.** A program that touched an address will probably touch it again soon. Think of a loop counter, or the stack.
- **Spatial locality.** A program that touched an address will probably touch a nearby one. Think of walking through an array.

Locality matters doubly for translation, because a page is large. A 4 KiB page holds 1024 four-byte integers, so a whole page of data shares one translation. After the first access to a page, the next 1023 accesses to it can reuse the same cached entry.

## How a TLB works

A TLB stores **entries**. Each entry says "page number P maps to frame F". It has a fixed capacity, usually between 16 and a couple of thousand entries.

On every memory access, hardware does this:

```text
virtual address
      |
      v
  split into (vpn, offset)
      |
      v
  look vpn up in the TLB
      |
  +---+-------------------------+
  | hit                         | miss
  v                             v
frame from the entry      walk the page table (slow)
      |                   store (vpn -> frame) in the TLB
      |                         |
      +------------+------------+
                   v
          physical address = frame * page_size + offset
```

A **hit** means the TLB had the entry. A **miss** means it did not, so the hardware or the OS walks the page table. The **hit rate** is `hits / (hits + misses)`.

On x86 and ARM, a hardware page-table walker handles misses. On some older designs, such as MIPS, a TLB miss traps to the kernel, which fills the entry in software. Both fit the same model.

A TLB that is full must evict an entry to make room. The usual choice is **least recently used** (LRU): evict the entry that has gone unused the longest. It bets that the past predicts the future. Real hardware often uses a cheaper approximation, but exact LRU is the model to learn.

Here is LRU on a TLB with capacity 2. The left end is the oldest entry:

```text
step                 TLB (oldest ... newest)   note
insert vpn 1         [1]
insert vpn 2         [1, 2]
lookup vpn 1 (hit)   [2, 1]                    hit moves 1 to the newest end
insert vpn 3         [1, 3]                    full: evict 2, the oldest
```

A hit must refresh the entry's recency. If you forget, you evict pages that are still in use.

> [!KEY]
> A TLB is a small cache of page-number-to-frame translations. It works because programs reuse pages, and one page holds thousands of bytes.

## Hit rates on array walks

You can predict a TLB's hit rate by arithmetic. Take 4 KiB pages and an array of 4-byte integers that a loop reads from start to end.

```text
page size                 4096 bytes
integer size                 4 bytes
integers per page         4096 / 4 = 1024
```

The first access to each page misses, because the TLB has never seen it. The next 1023 accesses to that page hit. So one access in 1024 misses:

```text
hit rate = 1023 / 1024 = 0.99902  (about 99.9 percent)
```

Now run the loop over a whole array of 4096 integers:

```text
array size        4096 * 4 = 16384 bytes = 4 pages
accesses          4096
misses            4        (one per page)
hits              4096 - 4 = 4092
hit rate          4092 / 4096 = 0.99902
```

Bigger elements mean fewer accesses per page, so more misses. Take an array of 16-byte structures:

```text
structures per page   4096 / 16 = 256
hit rate              255 / 256 = 0.99609  (about 99.6 percent)
```

The general rule for a long, cold, sequential walk with element size `s` bytes (where `s` divides the page size `P`) is:

$$
\text{hit rate} = 1 - \frac{s}{P}
$$

When `s` is a whole page or larger, every access lands on a new page and the hit rate is 0. This is the **column walk**: a program that reads a big two-dimensional array down a column jumps a whole row each step. If a row is 4096 bytes or more, each access touches a different page. A loop that looks equivalent to the row-by-row one can run many times slower.

Capacity matters only for pages you revisit. A sequential walk touches each page and never returns, so even a one-entry TLB gets the same hit rate. A loop that cycles over many pages is different. Take 5 pages visited in order, three times, with a 4-entry LRU TLB:

```text
pages: 0 1 2 3 4 0 1 2 3 4 0 1 2 3 4
after 0 1 2 3:   TLB = [0 1 2 3]
access 4 (miss): evict 0 -> [1 2 3 4]
access 0 (miss): evict 1 -> [2 3 4 0]
access 1 (miss): evict 2 -> [3 4 0 1]
... every access misses: 15 misses, 0 hits
```

LRU evicts the page the loop needs next, every time. With 5 entries the same loop has 5 misses and 10 hits. A loop one page too big for the TLB falls off a cliff.

## What a miss costs

Let `t` be the time to check the TLB, `m` the time of one memory access, and `L` the number of page-table levels. A hit costs `t + m`. A miss costs `t` for the check, `L * m` for the walk, and `m` for the data:

```text
hit  = t + m
miss = t + L*m + m
average = hit_rate * hit + (1 - hit_rate) * miss
```

Use `t = 1 ns`, `m = 100 ns`, and a four-level walk. A hit costs 101 ns. A miss costs 1 + 400 + 100 = 501 ns.

| Hit rate | Average access time |
|---|---|
| 100% | 101 ns |
| 99% | 0.99 * 101 + 0.01 * 501 = 105 ns |
| 80% | 0.8 * 101 + 0.2 * 501 = 181 ns |
| 0% | 501 ns |

At 99% the paging overhead is 4 percent. At 80% it is nearly doubled. The TLB must hit almost every time for paging to be cheap. These are round numbers for teaching. Real memory is faster than 100 ns when the data is in a CPU cache, and real walkers cache upper levels too.

## Context switches

A TLB entry says "page 0 maps to frame 7". But whose page 0? Every process has its own page 0. Suppose process A is running, and the TLB holds A's entry for page 0. The kernel switches to process B. If B touches page 0, the TLB would hand back A's frame, and B would read A's memory. That is a serious bug.

There are two fixes.

**Flush on switch.** When the kernel switches to a different process, it empties the TLB. This is always correct. The cost is that the incoming process starts with a cold TLB and misses on every page until it warms up. If two processes ping-pong, each switch throws away what the other just loaded.

**Tag entries with an ASID.** An **address space identifier** (ASID) is a small number that names a process. The TLB stores it in each entry and compares it on every lookup. Entries for A and B live side by side, and a switch needs no flush. A returning process finds its entries still warm.

Here is an example. Processes A (ASID 1) and B (ASID 2) alternate six times, each reading page 0:

```text
access   with ASIDs            flush on switch
A        miss, cache (1,0)     miss
B        miss, cache (2,0)     miss (flushed)
A        hit                   miss (flushed)
B        hit                   miss (flushed)
A        hit                   miss (flushed)
B        hit                   miss (flushed)
total    4 hits, 2 misses      0 hits, 6 misses
```

On x86 the feature is called PCID, and Linux uses it on processors that support it. ARM calls it an ASID. A TLB has a limited number of tag values, 4096 for x86 PCID and 256 or 65536 on ARM. The kernel has to recycle them when it runs more processes than tags.

Flushing is also needed when the page table itself changes. If the kernel unmaps a page or changes its permissions, a stale TLB entry could still allow the old access. The kernel removes the entry with an instruction such as `invlpg`. On a multi-core machine, one core must tell the others to drop the entry too, a slow operation called a TLB shootdown.

> [!WARNING]
> A TLB entry is a copy of a page-table entry. The hardware does not notice when the page table changes. The kernel must invalidate stale entries itself, or a process could keep using memory it should have lost.

## Try it on your own machine

1. Read your CPU's TLB sizes (Linux-only, needs the `cpuid` package or `lscpu` support):

   ```bash
   lscpu | grep -i -E 'cache|model name'
   ```

   `lscpu` shows data and instruction cache sizes. TLB sizes appear in the vendor manuals and in tools such as `cpuid -1 | grep -i tlb`. Expect tens of entries for the first-level TLB and roughly a thousand or more for the second level.

2. Count TLB misses for a real program (Linux-only, needs the `perf` tool and permission to use it):

   ```bash
   perf stat -e dTLB-loads,dTLB-load-misses python3 -c "sum(range(10**7))"
   ```

   Look at the ratio of misses to loads. Some virtual machines do not expose these counters, and `perf` then prints `<not supported>`.

3. Compare a row walk with a column walk in Python. Save this as `walk.py` and run `python3 walk.py`:

   ```python
   import time

   n = 2000
   grid = [[1] * n for _ in range(n)]

   start = time.perf_counter()
   total = sum(grid[i][j] for i in range(n) for j in range(n))
   by_rows = time.perf_counter() - start

   start = time.perf_counter()
   total = sum(grid[i][j] for j in range(n) for i in range(n))
   by_columns = time.perf_counter() - start

   print(f"rows {by_rows:.2f}s, columns {by_columns:.2f}s")
   ```

   The column version is usually slower. Python's overhead hides most of the effect, and the gap comes mostly from CPU data caches rather than the TLB. In C with a large array the gap is much bigger.

4. See that Linux reports transparent huge pages, which cut TLB pressure (Linux-only):

   ```bash
   cat /sys/kernel/mm/transparent_hugepage/enabled
   ```

   The bracketed word is the active setting. A 2 MiB huge page needs one TLB entry for what would take 512 ordinary entries.

## Build it step by step

Open `starter.py`. `PageFault` is given. A page table here is a plain `dict` from page number to frame number.

1. `TLB.__init__(capacity)` stores the capacity, an empty ordered container, and two counters, `hits` and `misses`. A `collections.OrderedDict` keyed by `(asid, vpn)` is a good fit, with the oldest entry first.

2. `TLB.lookup(asid, vpn)` returns the frame or `None`. On a hit, call `move_to_end` on the key and count a hit. On a miss, count a miss. The common mistake is forgetting to refresh recency on a hit.

3. `TLB.insert(asid, vpn, frame)` stores an entry. If the key is already present, update it and make it newest without evicting anything. If the TLB is full and the key is new, drop the oldest with `popitem(last=False)`.

4. `TLB.flush(asid=None)` clears everything, or only the entries whose ASID matches. `TLB.hit_rate()` returns `hits / (hits + misses)`, or `0.0` before any lookup. `TLB.__len__` returns the entry count.

5. `MMU.__init__(tlb, page_tables, page_size, use_asids, asid)` remembers its arguments, tracks the running process in `current`, and counts page-table walks in `walks`.

6. `MMU.translate(vaddr)` splits the address with `divmod`, looks in the TLB, and on a miss walks `page_tables[current]`. A missing page raises `PageFault` and adds nothing to the TLB. Without ASIDs, tag every entry with `0`. The common mistake is to cache the entry before you know the walk succeeded.

7. `MMU.switch(asid)` sets the running process. When `use_asids` is false and the process changes, flush the TLB.

8. `array_walk(base, count, elem_size)` returns the list of addresses `base + i * elem_size`.

9. `simulate_walk(addresses, capacity, page_size)` builds a page table that maps every touched page to itself, runs the addresses through an `MMU`, and returns `(hits, misses)`.

10. `sequential_hit_rate(page_size, elem_size)` is the formula above, floored at `0.0`. `effective_access_time(hit_rate, tlb_ns, mem_ns, levels)` is the average-cost formula.

## Where this breaks

- **Reach is small.** A 64-entry TLB with 4 KiB pages covers 256 KiB. A program that scatters accesses over gigabytes misses constantly. Databases and virtual machines use huge pages (2 MiB or 1 GiB) so that one entry covers far more.
- **Pointer chasing defeats locality.** Walking a linked list or a big hash table jumps between pages with no pattern. Each step can be a TLB miss, and a miss on a four-level table is expensive.
- **Context switches still hurt.** ASIDs keep entries across switches, but a busy system with many processes competes for the same few entries.
- **Shootdowns are slow.** Changing a mapping on a multi-core machine means interrupting other cores. Programs that call `munmap` or `mprotect` in a tight loop feel it.
- **Side channels.** The TLB is shared state, and timing differences reveal which pages another program touched. Some security fixes, such as the kernel page-table isolation added for Meltdown, flush or retag TLB entries on every system call, which makes ASIDs more important.
- **LRU is costly in hardware.** Tracking exact recency across hundreds of entries takes real circuitry. Hardware uses cheaper schemes, such as tree-based pseudo-LRU, that behave similarly.

## Further reading

- [OSTEP chapter 19, Paging: Faster Translations (TLBs)](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-tlbs.pdf) is the standard introduction, including the array example and context switches.
- [OSTEP chapter 20, Paging: Smaller Tables](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-smalltables.pdf) shows why multi-level walks make TLB misses costly.
- [What Every Programmer Should Know About Memory, by Ulrich Drepper](https://akkadia.org/drepper/cpumemory.pdf) covers TLB behaviour and the cost of poor locality in section 4.
- [The perf_event_open man page](https://man7.org/linux/man-pages/man2/perf_event_open.2.html) documents the hardware counters, including TLB events, that `perf stat` reads.
- [Linux kernel documentation, Transparent Hugepage Support](https://docs.kernel.org/admin-guide/mm/transhuge.html) explains how Linux uses large pages to reduce TLB pressure.

## The exercise

You build a TLB and an MMU around it, then use them for experiments. `TLB` caches `(asid, vpn)` translations with LRU eviction, counts hits and misses, and supports flushing by ASID. `MMU` translates addresses through the TLB, walks a page table on a miss, raises `PageFault` for unmapped pages, and either tags entries with ASIDs or flushes on `switch`.

`array_walk`, `simulate_walk`, `sequential_hit_rate`, and `effective_access_time` put numbers on the lesson. The checks cover LRU order and recency refresh, the 4092-hit and 4-miss walk of 4096 integers, the 255 of 256 rate for 16-byte structures, the thrashing loop of five pages in a four-entry TLB, the ASID versus flush comparison, and the 105 ns average access time.
