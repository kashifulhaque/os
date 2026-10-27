---
title: "Heap allocation: malloc and free"
slug: 17-heap-allocation
part: "Part 4 — Memory"
summary: Build a free-list allocator with first fit, best fit, splitting, and coalescing, and measure its fragmentation.
minutes: 55
gpu: false
objectives:
  - Explain what malloc and free do, and why the heap needs an allocator on top of pages.
  - Allocate from a free list with first fit and best fit, splitting blocks when the leftover is big enough.
  - Free a block, coalesce it with free neighbours, and detect double frees and invalid pointers.
  - Compute external fragmentation from a precise definition.
prereqs:
  - 16-page-replacement
exercise: 17-heap-allocation
---

# Heap allocation: malloc and free

Paging gives a process memory in pages of 4096 bytes. Programs rarely want 4096 bytes. They want 24 bytes for a list node, 100 bytes for a string, 40 bytes for a record. Asking the kernel for a page each time would waste almost all of it, and each request would cost a system call.

So programs use a library on top of the kernel. It asks the kernel for big regions of memory, then hands out small pieces on request. In C these calls are `malloc(n)`, which returns the address of `n` usable bytes, and `free(p)`, which gives them back. The region the pieces come from is the **heap**. The library code that manages it is the **allocator**.

Allocators look simple and hide a hard problem. Requests arrive in any order, in any size, and the allocator cannot move a block once it has given out its address. This lesson builds a working allocator over a fixed arena of bytes, and shows how memory ends up full of holes that are individually too small to use.

## What you already know

- Memory is an array of bytes, and an address is an index into it.
- A process gets virtual pages from the kernel, and the kernel gives more when the program asks.
- A Python list can hold tuples, and you can insert into the middle of it.
- A `MemoryError` tells a program that memory ran out.
- Round-up and round-down arithmetic with integers, such as `(n + 7) // 8 * 8`.

## Where the heap comes from

A process has several regions in its address space: code, global data, a stack for function calls, and the heap for everything allocated at run time. On Linux, the allocator in the C library (glibc, a program library that nearly every Linux program uses) gets heap memory from the kernel in two ways:

- `brk` (or `sbrk`) moves the end of the heap region. The heap grows like a stack of pages.
- `mmap` maps a fresh region of pages anywhere in the address space. glibc uses it for very large requests, 128 KiB by default.

The kernel deals only in whole pages. Cutting those pages into small blocks, and recycling them when the program calls `free`, is the allocator's job.

To study that job, we shrink it. Our **arena** is a fixed array of `size` bytes, such as 256, addressed by integers 0 to 255. There is no kernel and no growth. An allocation is an integer offset into the arena, and the allocator is Python code that tracks which ranges are in use.

## Blocks, headers, and the free list

The arena is divided into **blocks**. Each block has two parts:

- A **header** of 8 bytes, where the allocator stores bookkeeping. Real allocators keep the block's size and a flag here.
- A **payload**, the bytes handed to the program.

In our model, a block is a tuple `(offset, payload_size, is_free)`. It occupies `HEADER + payload_size` bytes starting at `offset`. The next block starts right after it. The address that `malloc` returns is `offset + HEADER`, the first payload byte, because the program must not overwrite the header.

Blocks tile the arena exactly with no gaps:

```text
arena of 128 bytes, one free block

offset:   0        8                                    128
          +--------+------------------------------------+
          | header |   payload (120 bytes, free)        |
          +--------+------------------------------------+
block = (0, 120, True)
```

The header costs 8 bytes, so a fresh 128-byte arena offers 120 bytes of payload. The blocks, read in address order, form the **free list** when you keep only the free ones. Real allocators often link free blocks through pointers stored inside their unused payloads. Our model keeps a plain sorted list, which is simpler to read.

Real allocators also **align** payloads. Hardware prefers addresses that are multiples of 8 or 16. We round every request up to a multiple of 8, so `round_up(10) = 16` and `round_up(16) = 16`. The extra bytes are **internal fragmentation**, space inside an allocated block that nobody uses.

> [!KEY]
> An allocator keeps a list of blocks that tile the arena. Each block has a header and a payload, and a flag that says whether it is free. `malloc` takes a free block, and `free` marks it free again.

## Choosing a block: first fit and best fit

When `malloc(n)` arrives, the allocator rounds `n` up to `need` and searches the free blocks for one with `payload >= need`. Two simple strategies:

- **First fit** takes the first free block, in address order, that is big enough. It is fast, because the search stops early.
- **Best fit** examines every free block and takes the *smallest* one that is big enough. If several tie, it takes the lowest address. It is slower, and the idea is to leave big blocks alone for big requests.

Take free blocks with payloads 40, 16, and 24, in address order, and a request for 16 bytes. First fit takes the 40-byte block. Best fit takes the 16-byte block, an exact fit. For a request of 20 bytes, first fit still takes the 40-byte block, and best fit takes the 24-byte block.

Neither strategy always wins. Best fit tends to leave tiny, useless leftovers. First fit tends to chew up the start of the arena. Real allocators use cleverer designs, but these two are the foundation.

## Splitting

The block we pick is often bigger than `need`. Giving the whole block to the program wastes the rest. Instead, the allocator **splits** the block: the front becomes the allocation, and the rest stays free as a smaller block with its own header.

The leftover needs a header and at least one useful payload unit. Our rule is exact:

> Split only if `block_payload - need >= HEADER + ALIGN`, which is 16 bytes. Otherwise hand out the whole block, and its payload stays the original size.

Work through a 128-byte arena. It starts as `(0, 120, free)`.

```text
malloc(16):  need = 16, leftover = 120 - 16 = 104 >= 16, so split.
  allocated block: (0, 16, used)        occupies bytes 0..23
  free block:      (24, 96, free)       24 = 0 + 8 + 16, payload 96 = 120 - 16 - 8
  returns 8

malloc(10):  need = 16 (rounded up), take the free block at 24.
  allocated block: (24, 16, used)       occupies bytes 24..47
  free block:      (48, 72, free)       72 = 96 - 16 - 8
  returns 32
```

Check the arithmetic: 24 + 24 + 8 + 72 = 128. The blocks tile the arena. The second request asked for 10 bytes and got 16, so 6 bytes are internal fragmentation.

Here is the arena after those two calls:

```text
offset: 0        8              24       32             48       56                128
        +--------+--------------+--------+--------------+--------+-------------------+
        | hdr    | payload 16   | hdr    | payload 16   | hdr    | payload 72 (free) |
        +--------+--------------+--------+--------------+--------+-------------------+
          block A (used)          block B (used)          block C (free)
          malloc returned 8       malloc returned 32
```

When the leftover is too small, the allocator gives out the whole block. In a 64-byte arena the only block is `(0, 56, free)`. A request for 48 leaves 8 bytes, less than 16, so the block stays `(0, 56, used)` and the extra 8 bytes ride along as internal fragmentation. If nothing fits, `malloc` raises `MemoryError`.

## Freeing and coalescing

`free(p)` finds the block whose payload starts at `p` and marks it free. That alone leaves a trap. Suppose a program allocates three blocks, then frees all three. If each stays a separate small block, the arena is three small free blocks. A later request for a bigger block fails, although the space is free and adjacent.

The cure is **coalescing**: when a block becomes free, merge it with any free neighbour. Merging two free blocks removes a header:

$$
\text{merged payload} = a_{\text{payload}} + \text{HEADER} + b_{\text{payload}}
$$

Here is a worked example in the 128-byte arena. Allocate three 16-byte blocks `a`, `b`, `c` (addresses 8, 32, 56):

```text
(0,16,used) (24,16,used) (48,16,used) (72,48,free)
```

Free `b`. Neither neighbour is free, so nothing merges:

```text
(0,16,used) (24,16,free) (48,16,used) (72,48,free)
```

Free `a`. Its right neighbour `b` is free, so they merge: 16 + 8 + 16 = 40.

```text
(0,40,free) (48,16,used) (72,48,free)
```

Free `c`. Both neighbours are free, so all three merge: 40 + 8 + 16 + 8 + 48 = 120.

```text
(0,120,free)
```

The arena is whole again. No matter what order you free `a`, `b`, and `c`, you end with one block.

Because the blocks are sorted by offset, neighbours are adjacent list entries. A single pass can merge every run of free blocks: compare each block with the last one you kept.

## Catching bad frees

Two bugs are common in C programs, and an allocator can catch them if it keeps careful records.

- A **double free** frees the same pointer twice. In a real allocator it can corrupt the free list and lead to security holes.
- An **invalid free** frees a pointer that `malloc` never returned, such as the middle of a block.

Our allocator follows an exact rule for `free(addr)`:

- If `addr` is the payload start of an allocated block, free it.
- If `addr` lies inside the payload of a *free* block, raise `DoubleFree`.
- Anything else, such as the middle of a used payload, a header address, or an address outside the arena, raises `InvalidFree`.

The second rule matters because of coalescing. After you free `a` and its block merges into a larger free block, the address 8 is no longer the start of any block. It lies inside the merged free block, so the allocator reports `DoubleFree` correctly, rather than a confusing invalid-pointer error.

glibc detects some of these too. It prints `free(): double free detected in tcache 2` and aborts. It cannot catch every case, because checking costs time.

## External fragmentation

Fragmentation is memory you cannot use. It comes in two kinds:

- **Internal fragmentation** is wasted space inside an allocated block, from alignment and from leftovers too small to split.
- **External fragmentation** is free space scattered in pieces too small to satisfy a request, even though the total is large enough.

Here is a 256-byte arena where four allocations were made and two were freed:

```text
a = malloc(48)    s1 = malloc(8)    b = malloc(24)    s2 = malloc(8)
free(a)           free(b)
```

```text
offset: 0      56    72      104   120                        256
        +------+-----+-------+-----+--------------------------+
        | 48 F | 8 U | 24 F  | 8 U |       128 F              |
        +------+-----+-------+-----+--------------------------+
blocks: (0,48,F) (56,8,U) (72,24,F) (104,8,U) (120,128,F)
```

Free payloads are 48, 24, and 128, so the arena has 200 free bytes. A request for 150 bytes still fails. The largest hole is 128 bytes, and the holes are not adjacent. Blocks in use separate them.

We measure this with one number. Let `free_bytes` be the total payload of all free blocks (headers do not count), and `largest_free` the biggest single free payload. Then:

$$
\text{fragmentation} = 1 - \frac{\text{largest\_free}}{\text{free\_bytes}}
$$

When there are no free bytes, the value is 0.0 by definition. Read the number as the fraction of free memory that is *not* in the largest hole.

```text
free_bytes    = 48 + 24 + 128 = 200
largest_free  = 128
fragmentation = 1 - 128 / 200 = 0.36
```

One free block gives 0.0. A value near 1.0 means free memory is crumbs. It is a measure of how badly the free space is split, not of how much is free.

Now compare the strategies on this arena with `malloc(16)`:

```text
first fit: takes the 48-byte hole at offset 0.
  leftover 48 - 16 = 32 >= 16, so split: (0,16,U) then (24,24,F). Returns 8.
best fit:  takes the 24-byte hole at offset 72, the smallest that fits.
  leftover 24 - 16 = 8 < 16, so no split: (72,24,U). Returns 80.
```

Best fit gives the whole 24-byte hole, and the 8 extra bytes become internal fragmentation. After either allocation the free bytes are 176 and the largest hole is still 128, so fragmentation is 1 - 128/176 = 0.273.

> [!KEY]
> Coalescing fights external fragmentation by merging neighbours. It cannot merge free blocks that have a used block between them, and the allocator cannot move used blocks, because the program holds their addresses.

## Try it on your own machine

1. See the heap in a process's memory map (Linux-only):

   ```bash
   cat /proc/self/maps | grep -E 'heap|stack'
   ```

   The line marked `[heap]` is the region `brk` controls. Small `malloc` calls in a C program grow it. Python allocates through its own allocators, so you may see a `[heap]` entry anyway.

2. Watch a program ask the kernel for memory (Linux-only, needs `strace`):

   ```bash
   strace -e trace=brk,mmap python3 -c "x = [0] * 10_000_000" 2>&1 | tail -5
   ```

   The large list triggers `mmap` calls. Many small allocations trigger `brk` instead, and often no system call at all, because the allocator reuses blocks it already holds.

3. Count allocator calls in a real program (Linux-only, needs `ltrace`):

   ```bash
   ltrace -c -e malloc+free ls 2>&1 | tail -6
   ```

   Compare the number of `malloc` and `free` calls. A program that exits cleanly frees most of what it takes.

4. Look at how much memory a Python process holds from the OS, and how much its objects use:

   ```bash
   python3 -c "
   import sys
   data = [bytes(100) for _ in range(100_000)]
   print('one bytes(100) object takes', sys.getsizeof(data[0]), 'bytes')
   "
   ```

   An empty `bytes` object is 33 bytes and the 100 data bytes add to it, so you see 133. The extra bytes are Python's own header, a form of the per-block overhead you built here.

## Build it step by step

Open `starter.py`. The constants `HEADER = 8` and `ALIGN = 8`, and the exceptions `DoubleFree` and `InvalidFree`, are given. Blocks are tuples `(offset, payload_size, is_free)`.

1. `round_up(n, align=ALIGN)` returns the smallest multiple of `align` that is at least `n`. Use `(n + align - 1) // align * align`. The common mistake is rounding down.

2. `find_block(blocks, need, policy="first")` returns the index of the chosen block, or `None`. Skip blocks that are allocated or smaller than `need`. First fit returns the first survivor. Best fit remembers the smallest survivor and uses a strict `<`, so the lowest address wins a tie. An unknown policy raises `ValueError`. The common mistake is forgetting to skip allocated blocks.

3. `coalesce(blocks)` returns a new list in which every run of adjacent free blocks is merged. Keep an output list. If the current block and the last kept block are both free, replace the last with `(offset, a + HEADER + b, True)`. The common mistake is forgetting the `HEADER` that the merge reclaims.

4. `Allocator.__init__(size, policy="first")` validates the arguments (`ValueError` for an unknown policy, a size that is not a multiple of 8, or a size below 16) and starts with one free block `(0, size - HEADER, True)`.

5. `Allocator.malloc(n)` raises `ValueError` for `n <= 0`, rounds up, calls `find_block`, raises `MemoryError` if there is none, and then splits or hands out the whole block. It returns `offset + HEADER`. The common mistake is returning `offset` instead of the payload address.

6. `Allocator.free(addr)` walks the blocks. A used block whose payload starts at `addr` becomes free, and then `coalesce` runs. An address inside a free block's payload raises `DoubleFree`. Anything else raises `InvalidFree`. A failed free must leave the blocks unchanged.

7. `blocks()` returns a copy of the list. `free_bytes()` sums free payloads. `largest_free()` returns the biggest free payload, or 0. `fragmentation()` returns `1 - largest_free / free_bytes`, or `0.0` when no bytes are free.

## Where this breaks

- **Searching is slow.** A linear scan of a long free list is expensive. Real allocators keep free blocks in size-segregated lists or trees, so a request for 32 bytes looks only at blocks near 32 bytes.
- **Multi-threaded programs contend.** If many threads call `malloc` at once, one lock around the free list becomes a bottleneck. glibc gives each thread its own arena and a small cache, and jemalloc and tcmalloc do the same in their own ways.
- **Fragmentation never goes away.** Long-running servers that allocate and free objects of many sizes drift toward a state full of holes. The allocator cannot move live objects, because programs keep raw pointers. Languages with garbage collectors can move objects and compact memory, and C cannot.
- **Memory is rarely returned.** Even when a program frees a lot, the heap often cannot shrink. A single live block near the end of the heap pins all the pages below it. Large blocks allocated with `mmap` can be returned to the kernel with `munmap`.
- **Bugs corrupt the allocator.** The header sits right before the payload, so a buffer overflow writes into the next block's header. That kills the allocator's records. Tools such as AddressSanitizer and Valgrind find these bugs.
- **No free is a leak.** A program that forgets `free` slowly eats memory. Our allocator catches double frees, and nothing in it can catch a missing free.

## Further reading

- [OSTEP chapter 17, Free-Space Management](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-freespace.pdf) covers headers, splitting, coalescing, and first, best, and worst fit.
- [OSTEP chapter 14, Interlude: Memory API](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-api.pdf) lists the typical mistakes with `malloc` and `free`.
- [The malloc man page](https://man7.org/linux/man-pages/man3/malloc.3.html) documents what glibc guarantees.
- [The brk man page](https://man7.org/linux/man-pages/man2/brk.2.html) describes the system call that grows the heap.
- [The glibc wiki page on malloc internals](https://sourceware.org/glibc/wiki/MallocInternals) describes how the real allocator organises arenas, chunks, and bins.

## The exercise

You build the allocator from this lesson. `round_up`, `find_block`, and `coalesce` are small standalone pieces, and `Allocator` ties them together. `malloc` returns payload addresses, splits blocks when the leftover is at least 16 bytes, and raises `MemoryError` when nothing fits. `free` coalesces neighbours and raises `DoubleFree` or `InvalidFree` for bad addresses. `free_bytes`, `largest_free`, and `fragmentation` report the state of the arena.

The checks use the numbers from this lesson: the 128-byte arena where `malloc(16)` returns 8, the unsplittable 64-byte case, all six orders of freeing three blocks, the 256-byte arena where first fit and best fit pick different holes, and the fragmentation value 0.36.
