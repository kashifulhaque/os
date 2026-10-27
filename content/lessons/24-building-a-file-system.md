---
title: Building a file system
slug: 24-building-a-file-system
part: "Part 6 — Storage and file systems"
summary: Lay out a superblock, bitmaps, inodes, and directories on a bytearray disk, and write mkfs, create, write, read, and path lookup.
minutes: 70
gpu: false
objectives:
  - Draw the on-disk layout of a simple file system and say what each region holds.
  - Compute which block and offset hold a given inode, and which bit tracks a given block.
  - Explain how a directory is stored as a file of name and inode pairs, and how a path lookup walks it.
  - Write mkfs, block and inode allocation, file read and write, and path lookup against a disk made of bytes.
prereqs:
  - 23-files-and-directories
exercise: 24-building-a-file-system
---

# Building a file system

You have used files and directories through the system call API. You saw
that every file has an inode, that a directory maps names to inode numbers,
and that a disk is an array of blocks. Now you assemble these into a working
file system.

A file system is *only* a way of arranging bytes on a block device, plus the
code that reads and writes that arrangement. There is no hidden state. If you
copy the bytes of the disk, you copy the whole file system. This is why you can
unplug a USB drive, plug it into another machine, and read your files.

In this lesson, you build a *very simple file system*, which we call vsfs,
after the one in *Operating Systems: Three Easy Pieces*. It is small enough to
fit in your head and complete enough to create directories, write files, and
find them again by path. Your code runs on a Python `bytearray` posing as a
disk, so you can inspect every byte it writes.

## What you already know

- A disk is an array of fixed-size blocks, addressed by number.
- An inode holds a file's metadata, and its number is unique within a file system. The inode does not hold the name.
- A directory is a file whose contents are pairs of a name and an inode number.
- A bitmap uses one bit per item, and you read and set a bit with shifts and masks.

## The design in one picture

A file system has to answer five questions about the blocks of a disk. Which
blocks are free? Where is each file's metadata? Where is each file's data? How
big is the file system? Which names lead to which files?

vsfs answers them by cutting the disk into regions of different jobs. The
picture below shows a 64-block disk with 512-byte blocks and 16 inodes. Block
numbers run along the top.

```text
block:   0     1       2       3     4      5  6  7  ...                 63
      +-----+-------+-------+-----+-----+-----+-----+-----+--- ... ---+-----+
      |  S  | i-bmp | d-bmp |  inode    |        data blocks (59)           |
      |     |       |       |  table    |                                   |
      +-----+-------+-------+-----+-----+-----+-----+-----+--- ... ---+-----+
        |      |       |        |                |
        |      |       |        |                +-- file and directory contents
        |      |       |        +------------------- 16 inodes x 64 bytes = 2 blocks
        |      |       +---------------------------- which data blocks are in use
        |      +------------------------------------ which inodes are in use
        +------------------------------------------- superblock: the map of the rest
```

Each region has a job:

- **Superblock (block 0).** A small record that describes the whole file system: its block size, how many blocks and inodes it has, and where each region starts. The kernel reads it first when it mounts the disk. It also holds a *magic number*, a fixed value that says "this really is a vsfs disk."
- **Inode bitmap (block 1).** One bit per inode. 1 means in use and 0 means free.
- **Data bitmap (block 2).** One bit per data block, with the same meaning.
- **Inode table (blocks 3 and 4).** A packed array of inodes.
- **Data region (blocks 5 to 63).** The contents of files and directories.

A *bitmap* is the cheapest way to track free space. Finding a free block means
scanning for a 0 bit. One 512-byte block holds 4096 bits, so a single bitmap
block can track 4096 blocks, or 2 MiB of data.

> [!KEY]
> A file system is a set of fixed regions on the disk plus a handful of rules for how bytes inside them are interpreted. The superblock is the map, the bitmaps say what is free, the inode table says what exists, and the data region holds the contents.

## Bitmaps: bit i lives in byte i // 8

To read bit `i` of a block, find the byte that holds it and the position inside
that byte. Byte index is `i // 8` and bit position is `i % 8`, counting from the
least significant bit. With the byte `0b00000101`, bits 0 and 2 are set:

```text
byte:        0   0   0   0   0   1   0   1
bit number:  7   6   5   4   3   2   1   0
                                 ^       ^
                                 bit 2   bit 0
```

In Python, `(buf[i // 8] >> (i % 8)) & 1` reads a bit. To set it, OR the byte
with `1 << (i % 8)`. To clear it, AND the byte with the inverse of that mask.
You wrote bit operations in lesson 3. Here they decide which blocks live.

The data bitmap has one more detail. Bit 0 does not stand for block 0 of the
disk, because block 0 is the superblock and is never data. Bit `i` stands for
block `data_start + i`. In our 64-block layout, `data_start` is 5, so bit 0 is
block 5 and bit 58 is block 63.

## Inodes: a fixed-size record at a computed address

An inode in vsfs is 64 bytes. It stores the type of the file (free, regular
file, or directory), its size in bytes, and twelve *direct pointers*. A direct
pointer is a block number where a piece of the file's data lives.

```text
one inode (64 bytes)
+--------+--------+---------+---------+-----+----------+----------+
| type   | size   | blocks  | blocks  | ... | blocks   | (unused) |
| 4 B    | 4 B    | [0] 4 B | [1] 4 B |     | [11] 4 B | 8 B      |
+--------+--------+---------+---------+-----+----------+----------+
   2=dir   1300       9         10          ...    0
```

A pointer of 0 means "no block here." Block 0 is the superblock, so it can
never be a data block, and 0 is safe to use as the empty value.

Twelve pointers of 512 bytes each limit a file to 6144 bytes in this lesson.
Real file systems add pointers to *indirect blocks*, which are blocks full of
more pointers. We discuss that at the end.

Because every inode has the same size, finding inode number `n` takes
arithmetic, not a search. Inode `n` starts `n * 64` bytes into the inode
table:

$$
\text{block} = \text{inode\_table} + \left\lfloor \frac{n \times 64}{512} \right\rfloor
\qquad
\text{offset} = (n \times 64) \bmod 512
$$

For inode 9, the byte position is $9 \times 64 = 576$. That is block
$3 + 1 = 4$ at offset $576 - 512 = 64$. Inode 7 is at byte 448, the last slot in
block 3. Inode 8 is the first slot in block 4.

```text
inode table
block 3: [ i0 ][ i1 ][ i2 ][ i3 ][ i4 ][ i5 ][ i6 ][ i7 ]   8 inodes x 64 B = 512
block 4: [ i8 ][ i9 ][i10 ][i11 ][i12 ][i13 ][i14 ][i15 ]
                 ^ offset 64
```

To change one inode, you cannot write 64 bytes. A disk reads and writes whole
blocks. So you read the 512-byte block, change 64 bytes inside it, and write
the whole block back. This *read-modify-write* cycle recurs in every file
system.

## Files: finding the bytes

To read byte `pos` of a file, you need the inode. The pointer
`blocks[pos // 512]` names the data block, and `pos % 512` is the offset inside
it. A 1300-byte file needs $\lceil 1300 / 512 \rceil = 3$ blocks:

```text
inode: size = 1300, blocks = [9, 10, 11, 0, 0, ...]

file bytes   0..511   -> block 9    (full)
file bytes 512..1023  -> block 10   (full)
file bytes 1024..1299 -> block 11   (276 bytes used, 236 bytes of zero padding)
```

Reading bytes 500 to 529 crosses a boundary. It takes the last 12 bytes of
block 9 and the first 18 bytes of block 10. The `size` field says where the file
really ends, so the padding in the last block is never returned.

The blocks of a file need not be next to each other. The inode lists whichever
free blocks the allocator found. This is *indexed allocation*, and it avoids
the fragmentation that plagues schemes that need contiguous space.

## Directories: files full of entries

A directory in vsfs is a file like any other, with its own inode (type 2) and
data blocks. Its bytes are a list of fixed-size entries. Each is 32 bytes: 28
bytes for the name, padded with zero bytes, and 4 bytes for the inode number.
Sixteen entries fit in one 512-byte block.

```text
directory /docs  (inode 1, size 128, one data block)
+--------------------------+--------+
| name (28 bytes)          | inum   |
+--------------------------+--------+
| "."                      | 1      |   itself
| ".."                     | 0      |   its parent, the root
| "notes.txt"              | 2      |
| "old"                    | 3      |
+--------------------------+--------+
```

Adding a name means rewriting the directory's contents with one more entry.
Removing one means rewriting it with one fewer. That rewrite goes through the
same `write_data` code as an ordinary file. The directory *is* a file, and no
special storage is needed.

The root directory is always inode 0, so the code has a place to start.

### Walking a path

To resolve `/docs/notes.txt`, start at the root inode and look at one name at a
time:

```text
path: /docs/notes.txt

start at inode 0 (root)
  read root's entries, find "docs"       -> inode 1
  read inode 1's entries, find "notes.txt" -> inode 2
result: inode 2
```

Every step reads an inode, then its directory data, then searches entries.
Because directories store `.` and `..`, a path with `..` needs no special
handling: it is just another name in the entries. For the root, `..` points
back to inode 0, which is why `/..` is `/`.

## A worked example: creating a file

Start from a freshly formatted disk. The root has inode 0 and data block 5.
Create `/docs` and then write `"hello"` into `/docs/a.txt`. Each line is one
change on disk:

```text
mkdir /docs
  1. alloc_inode   -> inode 1       inode bitmap: 0b11
  2. write_inode 1 type=dir
  3. alloc_block   -> block 6       data bitmap:  0b11
  4. write block 6: entries (".",1) ("..",0)       inode 1 size = 64
  5. add_entry to root: ("docs",1) -> rewrite block 5; root size 64 -> 96

write /docs/a.txt  b"hello"
  6. alloc_inode   -> inode 2       inode bitmap: 0b111
  7. write_inode 2 type=file
  8. add_entry to inode 1: ("a.txt",2) -> rewrite block 6; size 64 -> 96
  9. alloc_block   -> block 7       data bitmap:  0b111
 10. write block 7: "hello" + 507 zero bytes
 11. write_inode 2: size=5, blocks[0]=7
```

That is about a dozen separate changes on disk for one small file. That count matters in the next
lesson, because a crash between any two of those writes leaves the disk in a
half-finished state.

## Real file systems

Real file systems follow the same plan with larger numbers. ext4 uses 4096-byte
blocks, 256-byte inodes, and splits the disk into *block groups*, each with its own
bitmaps and inode table, so that a file's inode, data, and directory stay near each
other. Its root directory is inode 2. Inode 1 is reserved for bad blocks.

To reach bigger files, the classic Unix inode has 12 direct pointers followed by
one *single indirect* pointer to a block of 1024 further pointers, one *double
indirect* pointer to 1024 such blocks, and one *triple indirect*. With 4 KiB
blocks, that reaches $(12 + 1024 + 1024^2 + 1024^3) \times 4096$ bytes, a bit
over 4 TiB. Modern ext4 uses *extents* instead. An extent says "N blocks starting at
block B" in a few bytes, which is compact for large, contiguous files.

## Try it on your own machine

You can inspect a real ext4 file system without mounting it or using root,
by making an image file. This needs the `e2fsprogs` package (Linux):

1. Make a 16 MiB image and format it:

   ```bash
   dd if=/dev/zero of=/tmp/disk.img bs=1M count=16
   mkfs.ext4 -q /tmp/disk.img
   ```

2. Read its superblock and layout:

   ```bash
   dumpe2fs /tmp/disk.img 2>/dev/null | head -40
   ```

   Look at `Block size`, `Inode count`, `Inodes per group`, and `Inode size`. This is the superblock your vsfs imitates.

3. Look at the root directory's inode with `debugfs` (read-only):

   ```bash
   debugfs -R "stat <2>" /tmp/disk.img
   ```

   Find the `Type: directory`, the `Size`, and the `EXTENTS` line that gives the data block. Inode 2 is the ext4 root.

4. See how many inodes and blocks your real file systems have left (Linux or macOS):

   ```bash
   df -i /
   df -h /
   ```

5. Peek at the first bytes of a real disk image, as hex:

   ```bash
   xxd -s 1024 -l 64 /tmp/disk.img
   ```

   The ext4 superblock starts 1024 bytes in. The two bytes `53 ef` at offset 0x38 of the superblock are its magic number, `0xEF53`, stored little-endian.

## Build it step by step

The starter gives you `Disk`, `Inode`, the error classes, and the `pack_*` and
`unpack_*` helpers that turn records into bytes. You write the logic. Every
function takes the `disk` as its first argument and keeps nothing in memory.

1. `get_bit(buf, i)` and `set_bit(buf, i, value)` read and write one bit. `set_bit` changes a `bytearray` in place. The mistake is forgetting to keep the clear mask inside 8 bits.
2. `inode_location(sb, inum)` returns `(block, offset)` using the formula above. It takes the superblock dict and returns a tuple.
3. `read_superblock(disk)` unpacks block 0 and raises `FSError` for a wrong magic number. `read_inode(disk, inum)` and `write_inode(disk, inum, inode)` read and rewrite the right 64-byte slice. The mistake is writing only the 64 bytes instead of the whole block, or writing the block back over its neighbours.
4. `mkfs(disk, ninodes=16)` zeroes the disk, writes the superblock, and sets bit 0 in both bitmaps. It writes the root inode with its first data block, and writes the root's entries `.` and `..`. The inode table has `ceil(ninodes * 64 / block_size)` blocks, and `data_start` comes right after it. Use `-(-a // b)` for a ceiling.
5. `alloc_inode`, `free_inode`, `alloc_block`, `free_block`, `free_inodes`, and `free_blocks` manage the bitmaps. `alloc_block` returns an absolute block number and zero-fills the block. The mistake is returning the bitmap index instead of `data_start + index`.
6. `read_data(disk, inum, offset, n)` collects bytes across blocks, never past `size`. `write_data(disk, inum, data)` frees the old blocks, allocates new ones, pads the last block, and updates the inode. Check for `FileTooBig` and `NoSpace` first, so a failed write leaves the file as it was.
7. `dir_entries`, `add_entry`, and `remove_entry` read and rewrite the directory's data with `unpack_dirents` and `pack_dirents`. Reject empty names, names with `/`, and names over 28 bytes.
8. `lookup(disk, path)` walks the path from inode 0. `create(disk, path, kind)` and `mkdir` allocate an inode, link it into its parent, and give a new directory its `.` and `..`. A failed `create` must not leak an inode or block.
9. `write_file`, `read_file`, `listdir`, and `unlink` combine the pieces. `unlink` frees the blocks and the inode and removes the entry.

The last check *remounts*: it builds a new `Disk` over a copy of your disk's
bytes and reads everything back. If any state hid in a Python variable, this
check finds it.

## Where this breaks

- **It is slow for big directories.** A lookup in vsfs reads the whole directory and scans it. Real file systems use hashed or tree-shaped directories, such as ext4's HTree, so lookup in a million-file directory does not read a million entries.
- **Fixed limits.** The number of inodes is fixed when you run `mkfs`. The file size limit here is 6144 bytes. Real systems add indirect blocks or extents, and some, such as XFS and Btrfs, allocate inodes on demand.
- **Many writes per operation.** The example above took about a dozen disk changes for one small file. Real systems cache blocks in memory and write them back later, which is fast but makes a crash more dangerous.
- **No crash protection.** If power fails between steps 8 and 11 in the example, the directory names a file whose inode or data was never written. Lesson 25 is about exactly this.
- **Poor locality.** Using the lowest free block spreads a file's blocks as the disk ages. Real allocators try to place a file's blocks together, which, as lesson 22 showed, matters a great deal on a hard disk.

## Further reading

- [OSTEP chapter 40: File System Implementation](https://pages.cs.wisc.edu/~remzi/OSTEP/file-implementation.pdf) — the vsfs design this lesson follows, with the same layout and the same read and write walkthroughs.
- [OSTEP chapter 41: Locality and the Fast File System](https://pages.cs.wisc.edu/~remzi/OSTEP/file-ffs.pdf) — block groups, and how placement fights the cost of seeks.
- [ext4 Data Structures and Algorithms](https://www.kernel.org/doc/html/latest/filesystems/ext4/index.html) — the on-disk format of the file system on most Linux machines.
- [debugfs(8) manual page](https://man7.org/linux/man-pages/man8/debugfs.8.html) — the tool for looking at inodes and blocks of an ext file system.
- [xv6 book, chapter 8: File system](https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf) — a real teaching file system with a log, written in about a thousand lines of C.

## The exercise

You write the vsfs in one module. The starter gives you `Disk`, `Inode`, the error classes, and the `pack_*` and `unpack_*` helpers. You write `get_bit`, `set_bit`, `inode_location`, `read_superblock`, `read_inode`, `write_inode`, `mkfs`, `alloc_inode`, `free_inode`, `alloc_block`, `free_block`, `free_blocks`, `free_inodes`, `read_data`, `write_data`, `dir_entries`, `add_entry`, `remove_entry`, `lookup`, `create`, `mkdir`, `write_file`, `read_file`, `listdir`, and `unlink`.

The checks test each layer on a 64-block disk: bit arithmetic, inode addresses, the layout `mkfs` writes, allocation order and exhaustion, multi-block reads and writes, directory entries down to their raw bytes, and path lookup with `.` and `..`. Last, they copy the disk's bytes into a new `Disk` and confirm that every file survives.
