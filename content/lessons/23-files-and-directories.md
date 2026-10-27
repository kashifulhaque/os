---
title: Files, directories, and the file API
slug: 23-files-and-directories
part: "Part 6 — Storage and file systems"
summary: Use the real Linux file API with file descriptors, inspect inodes and links, walk a directory tree, and normalise paths.
minutes: 55
gpu: false
objectives:
  - Open, read, write, and seek a file with raw file descriptors, and say what each system call does.
  - Read an inode's number, link count, and size with os.stat.
  - Tell a hard link from a symbolic link, and say what deleting a name does.
  - Walk a directory tree with os.scandir, and resolve "." and ".." in a path by text alone.
prereqs:
  - 22-disks-and-io
exercise: 23-files-and-directories
---

# Files, directories, and the file API

The last lesson showed that a disk is a numbered array of blocks. Nobody wants to
remember "my essay lives in blocks 9,120 to 9,147." People want to say
`essay.txt` and have the computer find it. A *file system* is the part of the
operating system that turns names into blocks.

It gives you two abstractions. A *file* is a named sequence of bytes that stays
around after the program exits. A *directory* is a place that holds names of
files and of other directories. Together they form a tree. You use both
through a small set of system calls that has barely changed in fifty years.

In this lesson, you use that API for real, from Python, and look at what the
kernel keeps for each file. The next lesson builds a file system from scratch,
and everything you meet here will be a part you implement there.

## What you already know

- A system call is how a process asks the kernel for something it may not do itself.
- A file descriptor is a small number that a process uses to refer to something the kernel opened for it.
- A disk is an array of fixed-size blocks, and reading a contiguous run is far cheaper than reading scattered ones.
- A byte string in Python, `bytes`, holds raw data and slices like a list.

## A file is bytes plus metadata

A file has two parts that live in different places.

- The *data*: the bytes you wrote.
- The *metadata*: facts about the file that are not its contents. Its size, who owns it, who may read it, when it last changed, and which disk blocks hold its data.

The kernel keeps a file's metadata in a structure called an *inode* (short for
"index node"). Each inode has a number, its *inode number*, that is unique within
one file system. Think of a library. The books are the data. The catalogue card
for each book is the inode. The card says where on the shelves the book sits,
and the card has a number.

Notice what the inode does *not* hold: the file's name. That surprises almost
everyone, and it explains hard links later in the lesson.

## Directories map names to inode numbers

A *directory* is itself a file, with an inode of its own. Its data is a list
of pairs: a name and the inode number of whatever the name refers to.

```text
directory "/home/ana" (inode 20)         inode 31 (a file)
+---------------+-----------+            +----------------------+
| name          | inode no. |            | size: 11 bytes       |
+---------------+-----------+            | links: 1             |
| .             | 20        |            | owner: ana           |
| ..            | 5         |            | blocks: 900          |
| notes.txt     | 31   -----+----------> +----------------------+
| photos        | 44        |                      |
+---------------+-----------+                      v
                                         block 900: "hello world"
```

Every directory contains two special entries. `.` refers to the directory
itself and `..` to its parent. At the top of the tree, the *root directory*
`/` is its own parent.

A *path* such as `/home/ana/notes.txt` is a recipe. Start at the root. Look up
`home` in it to get an inode number. Open that directory and look up `ana`.
Repeat until the last name. This step-by-step search is called *path
resolution*. A path that starts with `/` is *absolute*. Any other path is
*relative*, and starts from the process's *current working directory*.

## Files through file descriptors

You work with an open file through a *file descriptor* (fd), a small
non-negative integer. A process starts with three open: 0 is standard input, 1
is standard output, and 2 is standard error. Each new `open` returns the lowest
free number, so the first one you open is usually 3.

The core calls are these:

| System call | Python | What it does |
|---|---|---|
| `open` | `os.open(path, flags, mode)` | Find the file, optionally create it, and return an fd |
| `read` | `os.read(fd, n)` | Copy up to `n` bytes from the file into memory |
| `write` | `os.write(fd, data)` | Copy bytes from memory into the file |
| `lseek` | `os.lseek(fd, offset, whence)` | Move the fd's position |
| `close` | `os.close(fd)` | Release the fd |

The kernel keeps a *current offset* for each open file: where the next read or
write starts. `read` and `write` both advance it by the number of bytes
transferred. `lseek` sets it directly. Reading a file front to back is a series
of `read` calls with no seeks at all.

### Flags for `os.open`

The `flags` argument says how you want to use the file. You combine flags with
`|`:

| Flag | Meaning |
|---|---|
| `os.O_RDONLY` | Open for reading only |
| `os.O_WRONLY` | Open for writing only |
| `os.O_RDWR` | Open for both |
| `os.O_CREAT` | Create the file if it does not exist |
| `os.O_TRUNC` | If it exists, throw away its old contents |
| `os.O_APPEND` | Every write goes to the end, whatever the offset |

When you pass `O_CREAT`, the third argument `mode` gives the new file's
permission bits, for example `0o644`. The kernel removes any bits in the
process's *umask* from it. That is why a file you ask to be `0o666` often shows
up as `0o644`.

Here is the whole lifecycle in a few lines:

```python
import os

fd = os.open("notes.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
os.write(fd, b"hello world")
os.close(fd)

fd = os.open("notes.txt", os.O_RDONLY)
os.lseek(fd, 6, os.SEEK_SET)      # skip "hello "
print(os.read(fd, 5))             # b'world'
os.close(fd)
```

Two details trip up beginners:

- `os.write` returns how many bytes it wrote, and that can be fewer than you gave it. This is common with pipes and sockets and possible with files. A careful program loops until every byte is out.
- `os.read` returns `b""` at end of file. It returns fewer bytes than you asked for when fewer remain, and it can also return fewer in the middle of a file. Never assume one `read` gets everything.

> [!KEY]
> The kernel, not your program, remembers where you are in an open file. The offset belongs to the open file, and `read`, `write`, and `lseek` all work on it.

Always close the descriptor, even on errors. A process may hold only a limited
number of fds (often 1024 by default), and leaking them eventually makes
`open` fail. A `try`/`finally` makes sure `close` runs.

## Looking at the inode with stat

`os.stat(path)` asks the kernel for a file's metadata and returns an object
with these fields:

| Field | Meaning |
|---|---|
| `st_ino` | The inode number |
| `st_dev` | The device the file system lives on |
| `st_nlink` | The number of names (links) that refer to this inode |
| `st_size` | The size in bytes |
| `st_mode` | The type of file and the permission bits |
| `st_uid`, `st_gid` | The owner and the owning group |
| `st_mtime` | When the data last changed |

The pair `(st_dev, st_ino)` identifies a file uniquely on a machine. An inode
number is unique only inside one device, so you need both.

## Hard links and symbolic links

Because a directory entry is just a name paired with an inode number, nothing
stops two entries from naming the same inode. That is a *hard link*. In the
diagram below, `notes.txt` and `backup.txt` are two names for one file.

```text
directory entries                 inode 31
+--------------------+            +-------------------+
| notes.txt  -> 31   |----------> | links: 2          |
| backup.txt -> 31   |----------> | size: 11          |
| soft.txt   -> 77   |            +-------------------+
+--------------------+
                                  inode 77 (a symbolic link)
                                  +-------------------+
                                  | data: "notes.txt" |  <- just a path in text
                                  +-------------------+
```

You make one with `os.link("notes.txt", "backup.txt")`, and the shell command
is `ln`. Afterwards `st_nlink` is 2. Neither name is the "real" one. They are
equal. Deleting a file, which the system call names `unlink`, removes one name
and decrements the link count. The kernel frees the inode and its blocks only
when the count reaches zero *and* no process still has the file open.

A *symbolic link* (symlink) is a different thing. It is a small file of its
own, with its own inode, whose data is a path as text. `os.symlink("notes.txt",
"soft.txt")` makes one, and `ln -s` does the same. When you open `soft.txt`,
the kernel reads that text and resolves the path it finds.

| | Hard link | Symbolic link |
|---|---|---|
| Is its own inode | No, it shares the target's | Yes |
| Can cross file systems | No | Yes |
| Can point to a directory | Not allowed for users | Yes |
| If the target is deleted | The data survives under the other name | The link dangles (it is *broken*) |
| `os.stat` follows it | Not applicable | Yes (use `os.lstat` to look at the link itself) |

> [!WARNING]
> `os.stat` follows symbolic links, and `os.lstat` does not. To ask whether a path is itself a symlink, use `os.path.islink` or `os.lstat`. A broken symlink makes `os.path.exists` return `False`, even though the link is there.

## Walking a directory

`os.scandir(path)` lists a directory's entries. Each entry carries its name,
its full path, and cheap type tests: `entry.is_dir()`, `entry.is_symlink()`.
The listing comes back in no promised order, so sort it by name when you need a
stable result.

The `tree` command prints a directory as an indented outline. You write the
same thing with recursion: print a directory's name, then call yourself on each
child directory with one more level of indent.

```text
proj/
  a.txt
  src/
    deep/
      z
    main.py
  link -> src
```

The bug to avoid is following a symbolic link that points back up the tree.
A loop like `a/b/loop -> ..` would make a naive walk run forever. The safe rule
is to test `entry.is_dir(follow_symlinks=False)`, so you treat a symlink as a
leaf.

## Cleaning up a path by text

Paths arrive with clutter: `/a/b/../c/./d//`. You can clean one *without touching
the disk*, using only its text. The rules are these:

- Empty parts (from `//` or a trailing `/`) and `.` parts disappear.
- A `..` removes the part before it.
- At the root, `/..` is just `/`. The root is its own parent.
- In a relative path, a `..` with nothing before it stays. `../a` is already clean.

Take `/a/b/../c/./d//` and keep a stack of parts:

```text
part    action              stack
a       push                [a]
b       push                [a, b]
..      pop                 [a]
c       push                [a, c]
.       skip                [a, c]
d       push                [a, c, d]
(empty) skip                [a, c, d]

result: "/" + "a/c/d" = "/a/c/d"
```

This text-only method has a limit. If `b` were a symlink to some other
directory, then `b/..` would mean the parent of the *target*, and the real
file system would give a different answer. The kernel resolves `..` on the
real tree, one step at a time. Text-only cleaning is right only when you know
there are no symlinks in the way. Python's `os.path.normpath` has the same
limit.

## Try it on your own machine

1. List inode numbers and link counts (Linux or macOS):

   ```bash
   mkdir /tmp/play && cd /tmp/play
   echo hello > a.txt
   ln a.txt hard.txt
   ln -s a.txt soft.txt
   ls -li
   ```

   The first column is the inode number. `a.txt` and `hard.txt` show the same number and a link count of 2. `soft.txt` has its own number and an arrow to its target.

2. Ask `stat` for the raw fields (Linux syntax):

   ```bash
   stat a.txt
   ```

   Find `Inode`, `Links`, `Size`, and `Blocks`. A file with 6 bytes still uses one whole block.

3. Check how many inodes your disk has left (Linux or macOS):

   ```bash
   df -i /
   ```

   A file system can run out of inodes while having free space. The `IUse%` column shows it.

4. Watch the real system calls (Linux only, needs `strace`):

   ```bash
   strace -e trace=openat,read,write,close cat /tmp/play/a.txt
   ```

   You see `openat` return a number such as 3, then `read(3, ...)`, then `close(3)`. `cat` uses the same API you use in this lesson.

5. See your process's open files (Linux only):

   ```bash
   ls -l /proc/self/fd
   ```

   Descriptors 0, 1, and 2 are your terminal, and one more is the `ls` call reading this directory.

## Build it step by step

Everything runs on real files. The checks create a temporary directory and
delete it afterwards, so you can experiment freely.

1. `write_file(path, data)` opens with `O_WRONLY | O_CREAT | O_TRUNC` and mode `0o644`, writes every byte in a loop, closes the fd in `finally`, and returns the byte count. The mistake people make is writing once and trusting the return value.
2. `append_file(path, data)` does the same with `O_APPEND` instead of `O_TRUNC`, and returns nothing.
3. `read_file(path)` opens read-only and calls `os.read(fd, 4096)` in a loop until it gets `b""`. Join the chunks. The mistake is reading once with a huge size and assuming that is the whole file.
4. `read_at(path, offset, n)` opens, calls `os.lseek(fd, offset, os.SEEK_SET)`, and reads up to `n` bytes. Near the end of the file you get fewer bytes, and past the end you get `b""`.
5. `file_info(path)` returns a dict with the keys `"inode"`, `"links"`, `"size"`, and `"is_dir"`, taken from `os.stat`. The check makes hard links and counts them.
6. `same_file(a, b)` compares `(st_dev, st_ino)` of the two paths. Use `os.stat`, so a symlink and its target compare equal. A copy has a different inode, so it compares unequal.
7. `classify(path)` returns `"file"`, `"dir"`, `"symlink"`, `"broken symlink"`, or `"missing"`. Test for a symlink first with `os.path.islink`, because `os.path.exists` follows links.
8. `walk_tree(root)` returns a list of lines. The first is the basename of `root` plus `/`. Sort entries by name, indent two spaces per level, add `/` after directories, and print a symlink as `name -> target` using `os.readlink`. Do not follow symlinks. Strip trailing slashes before taking the basename.
9. `normalize_path(path)` keeps a stack as in the table above. Compare with `os.path.normpath` in your own experiments, but do not call it in your answer.

## Where this breaks

- **Names are not atomic with data.** The sequence "check that a file does not exist, then create it" has a gap in which another process can create it. The fix is `O_CREAT | O_EXCL`, which makes the kernel do both steps as one.
- **Writes are not immediately on disk.** `os.write` hands bytes to the kernel's cache. They reach the disk later. If the power fails first, they are lost. `os.fsync(fd)` forces them out and waits. Lesson 25 shows why this matters.
- **Inodes can run out.** A file system holds a fixed number of inodes, chosen when it was made. Millions of tiny files can exhaust them while gigabytes stay free.
- **Hard links make the tree a graph.** Two directory entries can name one inode, so "the" path of a file is not unique, and tools that walk the tree can count a file twice. Hard links to directories are forbidden for this reason, since they could form cycles.
- **Race conditions in walks.** A directory can change while you list it. A file listed a moment ago can be gone when you open it, so programs that walk trees must handle `FileNotFoundError`.
- **Text-only path cleaning lies about symlinks.** Servers that clean a user's path to block `..` must still resolve real links, or the user can escape the directory they should stay in. `os.path.realpath` asks the real file system.

## Further reading

- [OSTEP chapter 39: Files and Directories](https://pages.cs.wisc.edu/~remzi/OSTEP/file-intro.pdf) — the API from this lesson, including links, `fsync`, and file descriptors.
- [open(2) manual page](https://man7.org/linux/man-pages/man2/open.2.html) — every flag, and the exact atomicity guarantees of `O_EXCL` and `O_APPEND`.
- [stat(2) manual page](https://man7.org/linux/man-pages/man2/stat.2.html) — each field of the inode metadata.
- [path_resolution(7) manual page](https://man7.org/linux/man-pages/man7/path_resolution.7.html) — how the kernel turns a path into an inode, including symlinks and `..`.
- [Python `os` module documentation](https://docs.python.org/3/library/os.html) — the file-descriptor functions used in the exercise.

## The exercise

You write the file API calls and the path helper in one module. The functions are `write_file`, `append_file`, `read_file`, `read_at`, `file_info`, `same_file`, `classify`, `walk_tree`, and `normalize_path`.

The checks run against real files in a temporary directory. They write more data than one read chunk, make hard and symbolic links, and test the link counts that the kernel reports. They compare `walk_tree` to an exact expected outline, and they compare `normalize_path` to hand-written cases and to Python's `posixpath.normpath` on 300 seeded random paths.
