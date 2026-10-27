---
title: Address spaces, base and bounds, and segmentation
slug: 13-address-spaces
part: "Part 4 — Memory"
summary: Give every process a private view of memory, and translate its addresses with base and bounds, then with code, heap, and stack segments.
minutes: 55
gpu: false
objectives:
  - Say what an address space is, and why a program's addresses differ from physical ones.
  - Translate a virtual address with a base register and a bounds register, and raise a fault when it is out of range.
  - "Translate through code, heap, and stack segments, including a stack that grows down."
prereqs:
  - 03-bits-bytes-and-memory
  - 06-processes
exercise: 13-address-spaces
---

# Address spaces, base and bounds, and segmentation

Part 3 shared the CPU among processes. Part 4 shares memory, and memory is harder. A CPU is given back after a time slice, and nothing of the previous owner remains. Memory holds data that must survive until the process asks for it again, and no other process may read or damage it.

Consider what happens without any protection. Two programs sit in the same physical memory. One has a bug and writes to a wrong location. If that location belongs to the other program, or to the kernel, something breaks, and it is hard to find out why. A buggy program must not be able to take down its neighbours.

The solution is the *address space*: a private view of memory that each process gets. The process believes it owns a large, empty memory that starts at address 0. The hardware and the kernel work together to make that belief true. In this lesson, you build the two simplest mechanisms for it, *base and bounds* and *segmentation*.

Think of a hotel. Every guest is told "your room is number 1". Room 1 means a different physical room for each guest, and a key card refuses to open anyone else's door. The guest's number is the *virtual address*. The room's real location in the building is the *physical address*. The key card is the hardware check.

## What you already know

- A byte is eight bits, and memory is a long row of bytes, each with a numbered address (lesson 03).
- Hexadecimal and bit shifts split a number into parts (lesson 03).
- A process is a running program with a record in the kernel (lesson 06).
- User mode is restricted, and the kernel runs in a privileged mode that can change protections (lesson 05).
- A program that breaks a rule triggers an exception, and the kernel decides what happens next (lesson 05).

## Where Part 4 goes

The next five lessons build up virtual memory in steps. Each step fixes a weakness of the one before.

| Lesson | Mechanism | What it fixes |
|---|---|---|
| 13 | Base and bounds, segments | The idea of translation and protection |
| 14 | Paging | Holes between variable-sized chunks |
| 15 | TLBs | The cost of translating every access |
| 16 | Page replacement | Programs larger than physical memory |
| 17 | Heap allocation | Handing out memory inside a program |

This lesson stays simple on purpose. Real machines use paging, and paging is easier to grasp when you have seen the simpler designs and why they fall short.

## What an address space holds

An *address* is a number that names one byte. A program uses addresses all the time: each variable, each function, and each array element lives at one. Three kinds of memory make up a typical program.

- *Code* holds the program's instructions. It is fixed in size and does not change.
- The *heap* holds data that the program allocates while it runs, such as the result of `malloc` in C or a growing Python list. It grows toward higher addresses.
- The *stack* holds function calls: each call's local variables and return address. By convention it grows toward lower addresses, which is why we say it "grows down".

The next diagram shows a small 16 KiB address space. Addresses increase down the page.

```text
virtual address
     0  +---------------------+
        | code                |  fixed size, read-only
 2 KiB  +---------------------+
        | heap                |  grows toward higher addresses
        |         |           |
        |         v           |
        |                     |
        |   free space        |
        |                     |
        |         ^           |
        |         |           |
        | stack               |  grows toward lower addresses
16 KiB  +---------------------+
```

The free space in the middle is the room both can grow into. It is what makes the address space feel large. A process that uses 7 KiB of the 16 KiB has 9 KiB of empty space between its heap and stack.

A key point: these are *virtual* addresses. If a program prints the address of a variable, it sees a virtual one. Two processes can both have a variable at address 4200, and those are two different physical bytes.

> [!KEY]
> Every address a program uses is virtual. The hardware turns it into a physical address on each memory access, and refuses addresses the process does not own.

## Base and bounds

The first mechanism needs two special CPU storage slots, called *registers*: a *base* register and a *bounds* register. The part of the CPU that does the translation is the *memory management unit*, or MMU.

On every memory access, the MMU does two things:

1. It checks that the virtual address is less than the bounds. If not, it raises an exception.
2. It adds the base to the virtual address. The sum is the physical address.

Take a process whose space is 4096 bytes, loaded at physical address 16384. The base is 16384 and the bounds are 4096. The table shows three accesses.

| Virtual address | Check | Physical address |
|---|---|---|
| 128 | 128 < 4096, ok | 16384 + 128 = 16512 |
| 3000 | 3000 < 4096, ok | 16384 + 3000 = 19384 |
| 4400 | 4400 >= 4096, fault | — |

An address of 4096 is also a fault. The valid virtual addresses are 0 to 4095, which is exactly 4096 bytes.

```text
physical memory
 0      +---------------+
        | kernel, others|
 16384  +---------------+  <- base
        | process A     |
        | (4096 bytes)  |
 20480  +---------------+  <- base + bounds
        | other         |
```

The process only ever sees 0 to 4095. The base moves that range to wherever the kernel found room.

### Who sets the registers

If user programs could write the base and bounds registers, protection would be pointless. So only kernel mode can change them. When the kernel switches from process A to process B (lesson 04), it saves A's registers in A's process record and loads B's. Each process gets its own pair, and so each sees its own memory.

Because every access goes through the base register, the kernel can move a process. It copies the bytes to another physical place and updates the base. The program notices nothing, because its virtual addresses stay the same. The exercise function `relocate` does exactly this copy.

### What happens on a fault

An out-of-range access makes the hardware raise an exception, which transfers control to the kernel (lesson 05). Linux then sends the process the signal `SIGSEGV` (lesson 09). The default action is to terminate it, and the shell prints "Segmentation fault". In the exercise, the function raises `SegmentationFault`.

### The weakness: wasted space

Base and bounds forces the kernel to find one contiguous block as big as the whole address space, including the empty gap between heap and stack. For the 16 KiB space with 7 KiB in use, that is 9 KiB of real memory reserved for nothing. This waste inside an allocated block is called *internal fragmentation*.

## Segmentation

The fix is to give each region its own base and bounds. A *segment* is one contiguous region of the address space, such as the code, the heap, or the stack, with its own base and size. The kernel can put each segment anywhere in physical memory, and the empty gap needs no memory at all.

How does the hardware know which segment an address belongs to? The exercise uses an explicit scheme. The address space is 14 bits, which is 16384 bytes. The top 2 bits of an address pick the segment, and the low 12 bits are the *offset* within it. A segment can therefore hold at most 4096 bytes.

Take virtual address 4200. In binary it is 14 bits:

```text
4200 = 01 000001101000
       ^^ ^^^^^^^^^^^^
       |  offset = 104
       segment 1
```

Check: 1 × 4096 + 104 = 4200. In Python, `vaddr >> 12` gives the segment and `vaddr & 0xFFF` gives the offset.

The exercise uses this segment table, in bytes.

| Segment | Number | Physical base | Size | Notes |
|---|---|---|---|---|
| code | 0 | 32768 | 2048 | read-only |
| heap | 1 | 34816 | 3072 | grows up |
| stack | 3 | 28672 | 2048 | grows down |

Segment number 2 is unused. Here is where the segments sit in physical memory.

```text
physical address
26624  +-------------------+
       | stack (2048 B)    |   virtual 14336..16383
28672  +-------------------+  <- stack "base": one past its top byte
       |       ...         |
32768  +-------------------+
       | code (2048 B)     |   virtual 0..2047
34816  +-------------------+
       | heap (3072 B)     |   virtual 4096..7167
37888  +-------------------+
```

### Segments that grow up

For code and heap, translation is base plus offset, with a bounds check on the offset.

- Virtual 100: segment 0, offset 100. 100 < 2048, so the physical address is 32768 + 100 = 32868.
- Virtual 4200: segment 1, offset 104. 104 < 3072, so the physical address is 34816 + 104 = 34920.
- Virtual 2048: segment 0, offset 2048. 2048 is not less than 2048, so it is a fault. The code segment ends at offset 2047.

### The stack, which grows down

The stack starts at the top of its range and grows toward lower addresses. So a stack segment of 2048 bytes occupies the *top* 2048 bytes of its 4096-byte virtual range, offsets 2048 to 4095. The exercise defines the stack's base as the physical address one past its top byte.

To translate, compute how far below the top the byte is: `back = 4096 - offset`. The byte is valid when `back` is at most the size. The physical address is `base - back`.

Take virtual address 15360. It is segment 3 because 15360 = 3 × 4096 + 3072, so the offset is 3072.

- back = 4096 − 3072 = 1024.
- 1024 <= 2048, so it is valid.
- physical = 28672 − 1024 = 27648.

The top byte, virtual 16383, has offset 4095, so back = 1 and the physical address is 28671. The lowest valid stack byte has back = 2048 and offset 2048, so it is virtual 12288 + 2048 = 14336. It maps to 28672 − 2048 = 26624. Virtual 14335 has back = 2049, which is more than the size, so it is a fault.

> [!KEY]
> Segmentation gives each region its own base and bounds. A stack segment grows down, so its translation subtracts from the base instead of adding.

### Protection and sharing

Each segment can carry permission bits. Code is read-only, so a write to the code segment faults even when the address is inside it. That stops a bug from overwriting instructions. It also allows sharing: two processes running the same program can point their code segments at one physical copy, since neither can change it.

### How much is valid?

Count the addresses that do not fault in the example: 2048 for code, 3072 for the heap, and 2048 for the stack. That is 7168 of 16384 addresses, about 44 percent. The other 9216 addresses fault, and they cost no physical memory at all. A check in the exercise enumerates all 16384 addresses and verifies the count.

> [!WARNING]
> Do not mix up a segment's size with its address range. The valid offsets of a down-growing segment are 4096 − size through 4095, not 0 through size − 1.

## The problems that remain

Segmentation saves the gap, and still leaves two problems.

- **External fragmentation.** Segments have different sizes, and as processes start and stop, free physical memory breaks into many small holes. An incoming 3 KiB segment may find no hole big enough even if 5 KiB is free in total. Moving segments together, called *compaction*, copies a lot of bytes.
- **Growth.** A heap that needs to grow may find the next bytes occupied. The kernel then has to move the segment.

Both come from segments having varying sizes. Lesson 14 cuts memory into pieces of one fixed size, and the problems go away.

Real hardware has also moved on. On x86-64 processors in 64-bit mode, the base and limit of the code, data, and stack segments are ignored, and the segments behave as one flat space. Two segment registers, `FS` and `GS`, keep a usable base, and operating systems use them for per-thread data. Linux relies on paging for translation and protection. The region types you saw here, code, heap, and stack, still exist as areas in the process's memory map.

## Try it on your own machine

These commands are for Linux.

1. List the regions of a process's address space. Each line has a range of virtual addresses, permissions, and a name. Look for `r-xp` (readable, executable, private, so code), `[heap]`, and `[stack]`.

   ```bash
   cat /proc/self/maps
   ```

2. Run the same command twice and compare. The addresses of the stack and heap change between runs, because Linux randomizes them. That is called address space layout randomization.

   ```bash
   cat /proc/self/maps | grep -E 'heap|stack'
   cat /proc/self/maps | grep -E 'heap|stack'
   cat /proc/sys/kernel/randomize_va_space
   ```

   A value of 2 means full randomization.

3. Trigger a real segmentation fault. Python reads the byte at address 0, which no process may touch. The shell reports exit status 139, which is 128 plus signal number 11, `SIGSEGV`.

   ```bash
   python3 -c "import ctypes; ctypes.string_at(0)"; echo "exit status $?"
   ```

4. Look at the stack size limit that the kernel enforces for your shell. The value is in kilobytes, and the usual default is 8192.

   ```bash
   ulimit -s
   ```

5. Print a Python object's address and run it twice. In CPython, `id` returns the object's virtual address, and it differs between runs.

   ```bash
   python3 -c "print(hex(id(object())))"
   ```

> [!RECAP]
> - An address space is a private, virtual view of memory. Hardware translates each virtual address and refuses addresses the process does not own.
> - Base and bounds checks `vaddr < bounds` and adds `base`. Only the kernel can change the two registers.
> - Segmentation gives code, heap, and stack their own base and size, and the top bits of the address pick the segment.
> - A stack segment grows down, so its physical address is `base - (4096 - offset)`.
> - Variable-sized segments cause external fragmentation, which paging fixes in lesson 14.

## Build it step by step

`SegmentationFault`, `Segment`, and the constants `SEG_SIZE`, `OFFSET_BITS`, and `ADDRESS_SPACE` are given. You write six functions in the order the checks test them.

1. **`split_virtual_address(vaddr)`** returns `(segment, offset)`. Use `vaddr >> OFFSET_BITS` and `vaddr & (SEG_SIZE - 1)`. Raise `SegmentationFault` if the address is negative or at least `ADDRESS_SPACE`. The usual mistake is to forget the negative case.
2. **`translate_base_bounds(vaddr, base, bounds)`** returns `base + vaddr` when `0 <= vaddr < bounds`, and raises `SegmentationFault` otherwise. The usual mistake is `<=`, which lets one byte too many through.
3. **`translate_segmented(vaddr, table, write=False)`** takes a dictionary from segment number to `Segment`. Split the address, look up the segment, check the permission, then branch on `grows_down`. Raise `SegmentationFault` for every bad case. The usual mistake is to apply the growing-up formula to the stack.
4. **`load_byte(mem, table, vaddr)`** translates with `write=False` and reads from the `bytearray`.
5. **`store_byte(mem, table, vaddr, value)`** translates with `write=True` and writes. Translate first, so that a fault changes nothing.
6. **`relocate(mem, segment, new_base)`** copies a segment's bytes to another place and returns `dataclasses.replace(segment, base=new_base)`. For a stack, the bytes occupy `base - size` up to `base`. Raise `ValueError` before changing anything when the new range does not fit. Copy the bytes into a temporary `bytes` object first, because the old and new ranges can overlap.

The `__main__` block prints the translations from this lesson and three faults.

## Where this breaks

- **External fragmentation.** Variable-sized segments leave unusable holes, and compaction is slow. Paging avoids this.
- **Wasted space inside segments.** A segment is allocated whole, so a heap that is mostly empty still holds its memory.
- **Segments must be contiguous.** Programs with large, sparse regions fit poorly.
- **Memory bigger than RAM.** Moving a whole segment to disk and back is slow. Lesson 16 swaps in small pieces instead.
- **Two registers per segment cost a lookup.** The hardware must read a segment table on each access, which is one reason later designs add a cache, the subject of lesson 15.
- **Flat address spaces are the norm.** Modern hardware and Linux use paging, so your knowledge of segments mostly helps you read older material and understand the memory map in `/proc/self/maps`.

## Further reading

- [OSTEP, chapter 13: The abstraction of address spaces](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf) explains why isolation matters and introduces the three regions.
- [OSTEP, chapter 15: Address translation](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-mechanism.pdf) develops base and bounds, including what the hardware and the kernel each do.
- [OSTEP, chapter 16: Segmentation](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-segmentation.pdf) is the source of the 14-bit example and the stack arithmetic used here.
- [proc(5)](https://man7.org/linux/man-pages/man5/proc.5.html) documents the columns of `/proc/<pid>/maps`.
- [signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html) lists `SIGSEGV` and what the kernel does when it delivers it.

## The exercise

You write `split_virtual_address`, `translate_base_bounds`, `translate_segmented`, `load_byte`, `store_byte`, and `relocate`. The exception type `SegmentationFault` and the `Segment` dataclass come with the starter.

The checks use the segment table from this lesson. They verify the address split, base and bounds at the edges, code and heap translation, the stack arithmetic at its top and bottom bytes, faults for unmapped segments, overruns, and writes to code, and two processes that share virtual addresses but not physical bytes. Two more checks cover relocation, including an overlapping move, and a property test that counts exactly 7168 valid virtual addresses, all landing in distinct bytes inside the segments.
