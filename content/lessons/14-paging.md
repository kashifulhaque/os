---
title: Paging
slug: 14-paging
part: "Part 4 — Memory"
summary: Chop memory into fixed-size pages, translate addresses through page tables, and count what the tables cost.
minutes: 55
gpu: false
objectives:
  - Split a virtual address into a page number and an offset, in hex and in code.
  - Translate an address through a linear page table with valid, read, and write bits, raising a page fault when the access is not allowed.
  - Translate through a two-level page table and explain why it uses far less memory than a linear one.
  - "Say what x86-64 does: 4 KiB pages and a four-level table walk."
prereqs:
  - 13-address-spaces
exercise: 14-paging
---

# Paging

Segmentation, from the last lesson, gives each process a few variable-sized chunks of memory. Variable sizes cause trouble. When a chunk needs to grow, the neighbour may be in the way. When chunks come and go, memory fills with gaps too small to use.

Paging fixes this by cutting memory into pieces of one fixed size. Every piece is the same, so any free piece fits any request. The operating system hands a process as many pieces as it needs, in any order, and hardware stitches them into one tidy address space.

This is how nearly every computer you use runs programs. This lesson builds the translation by hand, then in Python. It ends with the real x86-64 layout, so you can see the toy model is the real thing with smaller numbers.

## What you already know

- A virtual address is the number a program uses. The hardware turns it into a physical address, the actual location in RAM.
- Base and bounds gives each process one contiguous region. Segmentation gives it several.
- Violating a boundary raises an exception that the kernel handles, such as `SegmentationFault` in the last lesson.
- A byte is eight bits, and hex digits are four bits each, so `0xF` is `1111`.
- A Python `dict` or `list` maps a key or index to a value.

## The big idea: pages and frames

Think of a hotel. Guests ask for room 7, but the front desk decides which physical room that is. Guest A's room 7 and guest B's room 7 are different rooms. Paging does the same for memory.

Two words matter, and they name the same size of thing in two places:

- A **page** is a fixed-size chunk of *virtual* memory. The process sees a long line of pages, numbered 0, 1, 2, and so on.
- A **frame** is a chunk of *physical* memory of the same size. RAM is a long line of frames.

The operating system decides which frame holds each page. A **page table** is the list that records the decision. The page table is indexed by page number, and each slot says which frame holds that page.

The page size is a power of two. The usual choice is 4 KiB, which is 4096 bytes or 2^12 bytes. A power of two makes the next step cheap.

> [!KEY]
> Paging splits memory into equal pages and frames. A page table maps each virtual page to a physical frame, so pages can sit in any frames, in any order.

## Splitting an address

A virtual address is one number. To translate it, hardware cuts it into two parts:

- The **virtual page number** (VPN) says which page. It is the high bits.
- The **offset** says which byte inside the page. It is the low bits.

With 4 KiB pages, the offset needs 12 bits, because 2^12 = 4096 positions. The offset is the low 12 bits. The page number is everything above them.

Hex makes this easy. Each hex digit is four bits, so 12 bits is exactly three hex digits. The last three digits are the offset. Everything to their left is the page number.

Take the address `0x3ABC`:

```text
virtual address  0x3ABC
                  | |||
                  | +++-- offset = 0xABC  (low 12 bits, 3 hex digits)
                  +------- page   = 0x3    (the rest)
```

In code, the offset is `vaddr & 0xFFF` and the page number is `vaddr >> 12`. For other page sizes, the mask is `page_size - 1`, and the shift is the number of bits in the offset.

Translation changes only the page number. The offset passes through untouched. Suppose the page table says page 3 lives in frame 9:

```text
page 3  -->  frame 9
offset 0xABC stays 0xABC
physical address = 9 * 4096 + 0xABC = 0x9ABC
```

Multiplying by 4096 shifts the frame number left by 12 bits, which puts it in the high digits. In hex you read the answer straight off: frame `9`, then offset `ABC`, gives `0x9ABC`.

## A page table with permission bits

A page table entry (PTE) holds more than a frame number. It holds a few bits that say what is allowed. This lesson uses three:

| Bit | Meaning |
|---|---|
| `valid` | The page is mapped. If it is 0, the page is not part of the process, or the OS took it away. |
| `read` | The program may read bytes from this page. |
| `write` | The program may write bytes to this page. |

Permission bits let the OS protect memory. Program code is mapped read-only, so a bug cannot overwrite it. A page that holds data but no code is not executable on real hardware, which blocks a family of attacks.

When a translation breaks a rule, the hardware cannot continue. It raises a **page fault**: a trap to the kernel, in the same way a system call traps. In the exercise, the `PageFault` exception plays that role.

Here is a four-page table and four accesses. The table has a normal page, a read-only page, an empty slot, and a page marked invalid:

```text
vpn   entry
 0    frame 5, valid, read, write
 1    frame 9, valid, read only
 2    None (never mapped)
 3    frame 2, valid = 0
```

| Access | Page, offset | Result |
|---|---|---|
| read `0x0123` | 0, `0x123` | frame 5, so `0x5123` |
| read `0x1FFF` | 1, `0xFFF` | frame 9, so `0x9FFF` |
| write `0x1000` | 1, `0x000` | page fault: page 1 is read-only |
| read `0x2000` | 2, `0x000` | page fault: nothing is mapped |

The check order matters. Look at the slot first. If it is empty, invalid, or past the end of the table, fault. Only then look at the permission bits. Never read `frame` from an entry you have not validated.

> [!WARNING]
> A page fault is not always a crash. A fault is only the hardware asking the kernel what to do. The kernel might kill the process (a "segmentation fault" you see in a terminal), or it might fix the problem and retry the instruction. The next lesson uses that second kind to swap pages to disk.

## The cost of a page table

A page table must have a slot for every page the address space *could* use, not only the pages it does use. Count it for a 32-bit address space:

```text
address space      = 2^32 bytes
page size          = 2^12 bytes
number of pages    = 2^32 / 2^12 = 2^20 = 1,048,576
bytes per entry    = 4
page table size    = 2^20 * 4 = 4 MiB   (per process!)
```

Every process needs its own page table, because each has its own address space. A hundred processes cost 400 MiB, even if each one uses a few pages. And most of that table is empty. A small program uses code near the bottom of the address space and a stack near the top. Everything between them is invalid.

The cost is worse for 64-bit machines. With 48-bit addresses, 4 KiB pages, and 8-byte entries:

```text
number of pages = 2^48 / 2^12 = 2^36
table size      = 2^36 * 8 = 2^39 bytes = 512 GiB
```

No machine has that to spare for each process. A linear table cannot work here, and we need a table that costs memory only for the parts that are in use.

## Two-level page tables

The fix is to page the page table. Instead of one giant list, build a tree:

1. A **directory** is a small list. Each slot is either empty or points to a second-level table.
2. A **second-level table** is a list of PTEs that covers a slice of the address space.

If a whole slice of the address space is unused, its directory slot stays empty, and no second-level table exists for it.

The tree shows in the address. The page number splits again. Take 32-bit addresses with 4 KiB pages and 1024 entries per table. A table of 1024 four-byte entries is exactly 4096 bytes, one page, which is no accident. The bit budget is 10 + 10 + 12:

```text
 31            22 21            12 11             0
+----------------+----------------+----------------+
| directory index|   table index  |     offset     |
|    10 bits     |    10 bits     |    12 bits     |
+----------------+----------------+----------------+
```

The directory index is `vpn // 1024` (or `vpn >> 10`), and the table index is `vpn % 1024` (or `vpn & 0x3FF`). Work an example with `0x00403ABC`:

```text
0x00403ABC
offset         = 0xABC
vpn            = 0x00403ABC >> 12 = 0x403 = 1027
directory idx  = 1027 // 1024 = 1
table idx      = 1027 %  1024 = 3
```

The walk takes two memory reads before the data itself:

```text
directory[1]  -->  second-level table
table[3]      -->  PTE (frame 7)
physical      =    7 * 4096 + 0xABC = 0x7ABC
```

If `directory[1]` is `None`, or `table[3]` is empty, or the entry's bits forbid the access, the walk ends in a `PageFault`.

Now the cost. A process maps three pages: code at `0x00400000`, data at `0x10000000`, and a stack at `0xBFFFF000`. They land in directory slots 1, 64, and 767. The tree has:

```text
directory:           1024 entries * 4 bytes =  4096 bytes
three tables:     3 * 1024 entries * 4 bytes = 12288 bytes
total                                         16384 bytes = 16 KiB
```

Sixteen KiB, against 4 MiB for the linear table. A process that maps a single page costs 8 KiB, the directory plus one table.

The price is speed. A linear table needs one extra memory read per access. The two-level table needs two. The next lesson shows how a cache hides most of that cost.

> [!KEY]
> A multi-level page table spends memory only where the address space is in use. The price is one extra memory read per level on every translation that misses the cache.

## What x86-64 really does

Your laptop's processor uses this same design with more levels. On x86-64 in the common mode:

- Pages are 4 KiB, with a 12-bit offset.
- Addresses are 48 bits wide. The remaining high bits of the 64-bit register must copy bit 47, so the address space is two ranges of 128 TiB each.
- Each page-table level is one page: 512 entries of 8 bytes each, indexed by 9 bits.
- There are four levels: 9 + 9 + 9 + 9 + 12 = 48 bits.

The levels have two sets of names. Intel's manuals call them PML4, PDPT, PD, and PT. Linux calls them PGD, PUD, PMD, and PTE. A control register, `CR3` on x86, holds the physical address of the top table. The OS changes `CR3` when it switches from one process to another.

Here is one address, `0x00007F1234567ABC`, split by hand into four 9-bit indices and an offset:

```text
bits 47-39  index 254   top level (PGD)
bits 38-30  index  72   PUD
bits 29-21  index 418   PMD
bits 20-12  index 359   PTE
bits 11-0   offset 0xABC
```

Some processors add a fifth level. With 5-level paging, addresses have 57 bits (9 + 9 + 9 + 9 + 9 + 12) and the address space grows from 256 TiB to 128 PiB. Linux enables it only for programs that ask for addresses beyond the 48-bit range.

Real PTEs pack more than our three bits into their 64. x86 has a *present* bit (our `valid`), a read/write bit, a user/supervisor bit that keeps programs out of kernel pages, an *accessed* bit, a *dirty* bit, and a no-execute bit. x86 has no separate read bit: a present page is always readable. The toy model's separate `read` bit lets you practice a rule that other architectures do have.

Page sizes also vary. x86-64 supports 2 MiB and 1 GiB "huge" pages, which skip the last one or two levels. Fewer levels means a faster walk and fewer entries to cache.

## Try it on your own machine

Run these in a terminal. Commands marked Linux-only read `/proc`, which macOS does not have.

1. Ask the system for its page size:

   ```bash
   getconf PAGESIZE
   ```

   Expect `4096` on most x86-64 machines. Apple silicon Macs report `16384`.

2. See your process's virtual layout (Linux-only):

   ```bash
   cat /proc/self/maps | head
   ```

   Each line is a range of virtual addresses, such as `5da42c121000-5da42c215000`. Every address ends in `000` in hex, because regions start and end on page boundaries. The `r-xp` column shows the permission bits: read, write, execute, private. Code is `r-x`, with no `w`.

3. See how much memory the kernel spends on page tables (Linux-only):

   ```bash
   grep PageTables /proc/meminfo
   ```

   This number grows with the number of processes and the memory they map.

4. Split an address in Python:

   ```bash
   python3 -c "a = 0x7F1234567ABC; print(hex(a >> 12), hex(a & 0xFFF))"
   ```

   The first value is the page number, the second is the offset `0xabc`.

## Build it step by step

Open `starter.py`. The `PageFault` exception and the `PTE` dataclass (`frame`, `valid`, `read`, `write`) are given. You write seven functions, in this order.

1. `split_address(vaddr, page_size)` takes an address and a power-of-two page size, and returns `(page_number, offset)`. Compute the offset bit count with `page_size.bit_length() - 1`, then shift and mask. The common mistake is to mask with `page_size` instead of `page_size - 1`.

2. `translate(page_table, vaddr, page_size=4096, write=False)` walks a linear table, a list of `PTE` or `None`. Raise `PageFault` for a page number past the end, a `None` slot, `valid` false, `read` false, or `write=True` with `write` false. Otherwise return `entry.frame * page_size + offset`. The common mistake is to use the entry before you check that it exists, which gives an `AttributeError` on `None` instead of a `PageFault`.

3. `split_two_level(vaddr, page_size, entries_per_table)` returns `(directory_index, table_index, offset)`. Reuse `split_address`, then split the page number with `//` and `%`.

4. `map_page(directory, vpn, pte, entries_per_table)` stores an entry, and creates the second-level table (`[None] * entries_per_table`) if the directory slot is `None`. The common mistake is to rebuild a table that already exists, which erases its other entries.

5. `translate_two_level(directory, vaddr, page_size, entries_per_table, write=False)` does the two-step walk. A directory index past the end, or a `None` directory slot, is a `PageFault`. Share the entry checks from step 2 through a small helper.

6. `linear_table_bytes(address_bits, page_size, pte_size=4)` returns the size of a full linear table. Use `(1 << address_bits) // page_size` for the page count.

7. `two_level_table_bytes(directory, entries_per_table, pte_size=4)` returns the directory's size plus one full table for every slot that is not `None`. The common mistake is to count only the filled entries. Hardware allocates whole tables.

## Where this breaks

Paging solves fragmentation of *virtual* memory, and it opens four other problems.

- **Every access costs more.** A four-level walk adds four memory reads to each access, so each access would cost five reads. Real hardware keeps recent translations in a cache. That cache is the subject of the next lesson.
- **Internal fragmentation.** A process that needs 5 KiB gets two 4 KiB pages. The unused 3 KiB is wasted inside the second page. With 4 KiB pages the average waste is about half a page per region.
- **Page tables still take memory.** Even a sparse tree costs about 12 KiB per mapped region, and a busy server with thousands of processes spends a real share of RAM on tables. Linux reports it as `PageTables` in `/proc/meminfo`. Huge pages shrink the tree for large regions.
- **Not every page fits in RAM.** A valid page does not have to be in a frame. The OS can store it on disk and mark it not present, then bring it back when a fault arrives. Lesson 16 covers that.
- **Choosing a page size is a trade-off.** Small pages waste less and need bigger tables. Large pages need small tables and waste more.

## Further reading

- [OSTEP chapter 18, Paging: Introduction](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf) covers the same ideas with a different worked example.
- [OSTEP chapter 20, Paging: Smaller Tables](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-smalltables.pdf) develops multi-level tables and the memory they save.
- [MIT 6.1810 xv6 book, chapter 3](https://pdos.csail.mit.edu/6.1810/2023/xv6/book-riscv-rev3.pdf) walks a real kernel's page-table code, on RISC-V's three-level tables.
- [Linux kernel documentation, Page Tables](https://docs.kernel.org/mm/page_tables.html) explains how Linux names and handles the levels.
- [The proc(5) man page](https://man7.org/linux/man-pages/man5/proc.5.html) documents `/proc/PID/maps` and `/proc/meminfo`.

## The exercise

You build the translation machinery of a paging MMU in plain Python. `split_address` and `translate` handle a linear table with `PTE` entries and raise `PageFault` for every kind of illegal access. `split_two_level`, `map_page`, and `translate_two_level` do the same for a directory-plus-tables tree. `linear_table_bytes` and `two_level_table_bytes` count what each design costs.

The checks compare against the hand-worked addresses in this lesson, including `0x3ABC` and `0x00403ABC`. They try every fault path, check that `map_page` creates tables only where needed, and check that a sparse tree is far smaller than a linear table. The Run button prints the four-page example and the cost of a 32-bit table.
