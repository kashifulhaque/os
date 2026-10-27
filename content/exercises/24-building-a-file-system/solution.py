"""A very simple file system (vsfs) on a bytearray disk.

On-disk layout, for the default 64-block disk with 512-byte blocks:

    block 0      superblock
    block 1      inode bitmap   (bit i = inode i is in use)
    block 2      data bitmap    (bit i = block data_start + i is in use)
    blocks 3-4   inode table    (64-byte inodes, 8 per block)
    blocks 5-63  data blocks

Every piece of state lives on the Disk. Functions take the disk as their first
argument and keep nothing in memory, so a "remount" is just a new Disk over the
same bytes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# --- Given: constants, the Disk, helpers, and exceptions --------------------

MAGIC = 0x56534653  # "VSFS"
INODE_SIZE = 64
NDIRECT = 12  # direct pointers per inode
DIRENT_SIZE = 32  # 28 bytes of name + 4 bytes of inode number
NAME_MAX = 28
ROOT_INUM = 0
T_FREE, T_FILE, T_DIR = 0, 1, 2


class FSError(Exception):
    """Base class for every file system error."""


class FileNotFound(FSError):
    pass


class FileExists(FSError):
    pass


class NotADirectory(FSError):
    pass


class IsADirectory(FSError):
    pass


class NoSpace(FSError):
    pass


class FileTooBig(FSError):
    pass


class Disk:
    """An array of fixed-size blocks stored in a bytearray."""

    def __init__(self, nblocks: int = 64, block_size: int = 512) -> None:
        self.block_size = block_size
        self.nblocks = nblocks
        self.data = bytearray(nblocks * block_size)

    @classmethod
    def from_image(cls, image: bytes, block_size: int = 512) -> "Disk":
        """Build a Disk over a copy of existing bytes (a 'remount')."""
        disk = cls(len(image) // block_size, block_size)
        disk.data[:] = image
        return disk

    def image(self) -> bytes:
        """The whole disk as immutable bytes."""
        return bytes(self.data)

    def read_block(self, n: int) -> bytes:
        if not 0 <= n < self.nblocks:
            raise IndexError(f"block {n} is outside the disk (0..{self.nblocks - 1})")
        start = n * self.block_size
        return bytes(self.data[start : start + self.block_size])

    def write_block(self, n: int, data: bytes) -> None:
        if not 0 <= n < self.nblocks:
            raise IndexError(f"block {n} is outside the disk (0..{self.nblocks - 1})")
        if len(data) != self.block_size:
            raise ValueError(f"a block is {self.block_size} bytes, got {len(data)}")
        start = n * self.block_size
        self.data[start : start + self.block_size] = data


@dataclass
class Inode:
    """type is T_FREE, T_FILE, or T_DIR. blocks holds NDIRECT absolute block
    numbers; 0 means "no block" (block 0 is the superblock, never data)."""

    type: int = T_FREE
    size: int = 0
    blocks: list = field(default_factory=lambda: [0] * NDIRECT)


SB_FIELDS = (
    "magic", "block_size", "nblocks", "ninodes",
    "inode_bitmap", "data_bitmap", "inode_table", "data_start",
)


def pack_superblock(sb: dict) -> bytes:
    """Superblock dict -> bytes (one block's worth of padding is added by you)."""
    return struct.pack("<8I", *(sb[name] for name in SB_FIELDS))


def unpack_superblock(raw: bytes) -> dict:
    return dict(zip(SB_FIELDS, struct.unpack_from("<8I", raw)))


def pack_inode(inode: Inode) -> bytes:
    return struct.pack("<II12I", inode.type, inode.size, *inode.blocks).ljust(INODE_SIZE, b"\0")


def unpack_inode(raw: bytes) -> Inode:
    fields = struct.unpack_from("<II12I", raw)
    return Inode(type=fields[0], size=fields[1], blocks=list(fields[2:]))


def pack_dirents(entries: list) -> bytes:
    """[(name, inum), ...] -> the bytes of a directory file, 32 bytes per entry."""
    return b"".join(struct.pack("<28sI", name.encode(), inum) for name, inum in entries)


def unpack_dirents(raw: bytes) -> list:
    out = []
    for i in range(0, len(raw), DIRENT_SIZE):
        name, inum = struct.unpack_from("<28sI", raw, i)
        out.append((name.rstrip(b"\0").decode(), inum))
    return out


# --- Step 1: bitmaps --------------------------------------------------------


def get_bit(buf: bytes, i: int) -> int:
    """Bit `i` of `buf` as 0 or 1. Bit 0 is the least significant bit of byte 0.

    >>> get_bit(bytes([0b00000101]), 2)
    1
    """
    return (buf[i // 8] >> (i % 8)) & 1


def set_bit(buf: bytearray, i: int, value: int) -> None:
    """Set bit `i` of the bytearray `buf` to `value` (0 or 1), in place.

    >>> b = bytearray(2); set_bit(b, 9, 1); b[1]
    2
    """
    if value:
        buf[i // 8] |= 1 << (i % 8)
    else:
        buf[i // 8] &= ~(1 << (i % 8)) & 0xFF


# --- Step 2: where things live ---------------------------------------------


def inode_location(sb: dict, inum: int) -> tuple:
    """(block number, byte offset in that block) of inode `inum`.

    Uses sb["block_size"] and sb["inode_table"]. Inodes are INODE_SIZE bytes.

    >>> inode_location({"block_size": 512, "inode_table": 3}, 9)
    (4, 64)
    """
    pos = inum * INODE_SIZE
    return sb["inode_table"] + pos // sb["block_size"], pos % sb["block_size"]


def read_superblock(disk: Disk) -> dict:
    """Read and return the superblock dict. Raise FSError if the magic is wrong.

    >>> read_superblock(disk)["data_start"]   # after mkfs(disk) on 64 blocks
    5
    """
    sb = unpack_superblock(disk.read_block(0))
    if sb["magic"] != MAGIC:
        raise FSError("not a vsfs disk: bad magic number")
    return sb


def read_inode(disk: Disk, inum: int) -> Inode:
    """Load inode `inum` from the inode table. Raise FSError if `inum` is out of range.

    >>> read_inode(disk, 0).type   # the root directory
    2
    """
    sb = read_superblock(disk)
    if not 0 <= inum < sb["ninodes"]:
        raise FSError(f"inode {inum} out of range 0..{sb['ninodes'] - 1}")
    block, offset = inode_location(sb, inum)
    return unpack_inode(disk.read_block(block)[offset : offset + INODE_SIZE])


def write_inode(disk: Disk, inum: int, inode: Inode) -> None:
    """Store `inode` as inode number `inum`, leaving neighbouring inodes untouched."""
    sb = read_superblock(disk)
    if not 0 <= inum < sb["ninodes"]:
        raise FSError(f"inode {inum} out of range 0..{sb['ninodes'] - 1}")
    block, offset = inode_location(sb, inum)
    raw = bytearray(disk.read_block(block))
    raw[offset : offset + INODE_SIZE] = pack_inode(inode)
    disk.write_block(block, bytes(raw))


# --- Step 3: mkfs -----------------------------------------------------------


def mkfs(disk: Disk, ninodes: int = 16) -> None:
    """Format `disk`: zero it, write the superblock and bitmaps, create the root.

    Layout: block 0 superblock, 1 inode bitmap, 2 data bitmap, then the inode
    table (ceil(ninodes * INODE_SIZE / block_size) blocks), then data blocks.
    The root directory is inode 0. It owns the first data block and holds the
    entries (".", 0) and ("..", 0). Mark inode 0 and data block 0 as used in
    the bitmaps. Raise ValueError if the disk is too small.
    """
    bs = disk.block_size
    table_blocks = -(-ninodes * INODE_SIZE // bs)  # ceiling division
    data_start = 3 + table_blocks
    ndata = disk.nblocks - data_start
    if ndata < 1 or ninodes < 1 or ninodes > bs * 8 or ndata > bs * 8:
        raise ValueError("disk too small, or too many inodes or blocks for one-block bitmaps")
    for n in range(disk.nblocks):
        disk.write_block(n, bytes(bs))
    sb = {
        "magic": MAGIC, "block_size": bs, "nblocks": disk.nblocks, "ninodes": ninodes,
        "inode_bitmap": 1, "data_bitmap": 2, "inode_table": 3, "data_start": data_start,
    }
    disk.write_block(0, pack_superblock(sb).ljust(bs, b"\0"))
    ibm, dbm = bytearray(bs), bytearray(bs)
    set_bit(ibm, ROOT_INUM, 1)
    set_bit(dbm, 0, 1)
    disk.write_block(1, bytes(ibm))
    disk.write_block(2, bytes(dbm))
    entries = pack_dirents([(".", ROOT_INUM), ("..", ROOT_INUM)])
    disk.write_block(data_start, entries.ljust(bs, b"\0"))
    root = Inode(T_DIR, len(entries))
    root.blocks[0] = data_start
    write_inode(disk, ROOT_INUM, root)


# --- Step 4: allocation -----------------------------------------------------


def alloc_inode(disk: Disk) -> int:
    """Claim the lowest-numbered free inode, mark it used, and return its number.

    The inode's contents are reset to a blank Inode(). Raise NoSpace if none is free.
    """
    sb = read_superblock(disk)
    bm = bytearray(disk.read_block(sb["inode_bitmap"]))
    for i in range(sb["ninodes"]):
        if get_bit(bm, i) == 0:
            set_bit(bm, i, 1)
            disk.write_block(sb["inode_bitmap"], bytes(bm))
            write_inode(disk, i, Inode())
            return i
    raise NoSpace("no free inodes")


def free_inode(disk: Disk, inum: int) -> None:
    """Mark inode `inum` free in the bitmap and blank its table entry."""
    sb = read_superblock(disk)
    bm = bytearray(disk.read_block(sb["inode_bitmap"]))
    set_bit(bm, inum, 0)
    disk.write_block(sb["inode_bitmap"], bytes(bm))
    write_inode(disk, inum, Inode())


def alloc_block(disk: Disk) -> int:
    """Claim the lowest free data block and return its ABSOLUTE block number.

    The block is zero-filled. Bit i of the data bitmap stands for block
    data_start + i. Raise NoSpace if none is free.
    """
    sb = read_superblock(disk)
    bm = bytearray(disk.read_block(sb["data_bitmap"]))
    for i in range(sb["nblocks"] - sb["data_start"]):
        if get_bit(bm, i) == 0:
            set_bit(bm, i, 1)
            disk.write_block(sb["data_bitmap"], bytes(bm))
            block = sb["data_start"] + i
            disk.write_block(block, bytes(disk.block_size))
            return block
    raise NoSpace("no free data blocks")


def free_block(disk: Disk, block: int) -> None:
    """Mark absolute block number `block` free. Raise FSError for a non-data block."""
    sb = read_superblock(disk)
    i = block - sb["data_start"]
    if not 0 <= i < sb["nblocks"] - sb["data_start"]:
        raise FSError(f"block {block} is not a data block")
    bm = bytearray(disk.read_block(sb["data_bitmap"]))
    set_bit(bm, i, 0)
    disk.write_block(sb["data_bitmap"], bytes(bm))


def free_blocks(disk: Disk) -> int:
    """How many data blocks are free."""
    sb = read_superblock(disk)
    bm = disk.read_block(sb["data_bitmap"])
    return sum(1 for i in range(sb["nblocks"] - sb["data_start"]) if get_bit(bm, i) == 0)


def free_inodes(disk: Disk) -> int:
    """How many inodes are free."""
    sb = read_superblock(disk)
    bm = disk.read_block(sb["inode_bitmap"])
    return sum(1 for i in range(sb["ninodes"]) if get_bit(bm, i) == 0)


# --- Step 5: file contents --------------------------------------------------


def read_data(disk: Disk, inum: int, offset: int = 0, n: int | None = None) -> bytes:
    """Bytes of inode `inum` from `offset`, at most `n` of them (all, if None).

    Never reads past the inode's size. Works for files and directories.

    >>> read_data(disk, inum, 2, 3)   # bytes 2, 3, 4 of the file
    """
    inode = read_inode(disk, inum)
    bs = disk.block_size
    end = inode.size if n is None else min(inode.size, offset + n)
    out = bytearray()
    pos = offset
    while pos < end:
        within = pos % bs
        take = min(bs - within, end - pos)
        block = inode.blocks[pos // bs]
        out += disk.read_block(block)[within : within + take]
        pos += take
    return bytes(out)


def write_data(disk: Disk, inum: int, data: bytes) -> None:
    """Replace the whole contents of inode `inum` with `data`.

    Free the old blocks, allocate ceil(len(data) / block_size) new ones, fill
    them (the last is zero-padded), and update the inode's blocks and size.
    Raise FileTooBig when more than NDIRECT blocks are needed, and NoSpace
    when the disk cannot hold the data. On either error the file is unchanged.
    """
    bs = disk.block_size
    need = -(-len(data) // bs)
    if need > NDIRECT:
        raise FileTooBig(f"{len(data)} bytes needs {need} blocks; the limit is {NDIRECT}")
    inode = read_inode(disk, inum)
    old = [b for b in inode.blocks if b]
    if need > free_blocks(disk) + len(old):
        raise NoSpace(f"need {need} blocks, only {free_blocks(disk) + len(old)} available")
    for b in old:
        free_block(disk, b)
    new = []
    for i in range(need):
        b = alloc_block(disk)
        disk.write_block(b, data[i * bs : (i + 1) * bs].ljust(bs, b"\0"))
        new.append(b)
    inode.blocks = new + [0] * (NDIRECT - len(new))
    inode.size = len(data)
    write_inode(disk, inum, inode)


# --- Step 6: directories ----------------------------------------------------


def dir_entries(disk: Disk, dir_inum: int) -> list:
    """The (name, inum) pairs stored in directory `dir_inum`, in stored order.

    Raise NotADirectory if the inode is not a directory.
    """
    if read_inode(disk, dir_inum).type != T_DIR:
        raise NotADirectory(f"inode {dir_inum} is not a directory")
    return unpack_dirents(read_data(disk, dir_inum))


def add_entry(disk: Disk, dir_inum: int, name: str, inum: int) -> None:
    """Append (name, inum) to the directory.

    Raise ValueError for an empty name, a name containing "/", or a name longer
    than NAME_MAX bytes. Raise FileExists if the name is already there.
    """
    if not name or "/" in name or len(name.encode()) > NAME_MAX:
        raise ValueError(f"bad file name {name!r}")
    entries = dir_entries(disk, dir_inum)
    if any(n == name for n, _ in entries):
        raise FileExists(name)
    write_data(disk, dir_inum, pack_dirents(entries + [(name, inum)]))


def remove_entry(disk: Disk, dir_inum: int, name: str) -> None:
    """Delete the entry called `name`. Raise FileNotFound if it is missing."""
    entries = dir_entries(disk, dir_inum)
    kept = [(n, i) for n, i in entries if n != name]
    if len(kept) == len(entries):
        raise FileNotFound(name)
    write_data(disk, dir_inum, pack_dirents(kept))


# --- Step 7: paths ----------------------------------------------------------


def lookup(disk: Disk, path: str) -> int:
    """Inode number of an absolute path. "/" is the root; "." and ".." work.

    Raise ValueError if the path does not start with "/", FileNotFound if a
    name is missing, and NotADirectory if a middle part is a file.

    >>> lookup(disk, "/docs/a.txt")   # e.g. 2
    """
    if not path.startswith("/"):
        raise ValueError(f"path must be absolute, got {path!r}")
    cur = ROOT_INUM
    for part in path.split("/"):
        if part == "":
            continue
        for name, inum in dir_entries(disk, cur):  # raises NotADirectory for a file
            if name == part:
                cur = inum
                break
        else:
            raise FileNotFound(path)
    return cur


def create(disk: Disk, path: str, kind: str = "file") -> int:
    """Create an empty file (kind="file") or directory (kind="dir") and return its inode number.

    The parent must exist and be a directory. A new directory starts with the
    entries (".", itself) and ("..", parent). Raise FileExists if the path is
    taken. Do not leak an inode or block when something fails.
    """
    if kind not in ("file", "dir"):
        raise ValueError("kind must be 'file' or 'dir'")
    parent_path, _, name = path.rstrip("/").rpartition("/")
    parent = lookup(disk, parent_path or "/")
    if any(n == name for n, _ in dir_entries(disk, parent)):
        raise FileExists(path)
    inum = alloc_inode(disk)
    try:
        write_inode(disk, inum, Inode(T_DIR if kind == "dir" else T_FILE))
        if kind == "dir":
            write_data(disk, inum, pack_dirents([(".", inum), ("..", parent)]))
        add_entry(disk, parent, name, inum)
    except (FSError, ValueError):
        for b in read_inode(disk, inum).blocks:
            if b:
                free_block(disk, b)
        free_inode(disk, inum)
        raise
    return inum


def mkdir(disk: Disk, path: str) -> int:
    """Create a directory; shorthand for create(disk, path, "dir")."""
    return create(disk, path, "dir")


def write_file(disk: Disk, path: str, data: bytes) -> int:
    """Create `path` if needed, then replace its contents. Return its inode number.

    Raise IsADirectory if `path` is a directory.
    """
    try:
        inum = lookup(disk, path)
    except FileNotFound:
        inum = create(disk, path, "file")
    if read_inode(disk, inum).type == T_DIR:
        raise IsADirectory(path)
    write_data(disk, inum, data)
    return inum


def read_file(disk: Disk, path: str) -> bytes:
    """Contents of the file at `path`. Raise IsADirectory for a directory."""
    inum = lookup(disk, path)
    if read_inode(disk, inum).type == T_DIR:
        raise IsADirectory(path)
    return read_data(disk, inum)


def listdir(disk: Disk, path: str) -> list:
    """Sorted names in the directory at `path`, without "." and "..".

    Raise NotADirectory if `path` is a file.
    """
    names = [n for n, _ in dir_entries(disk, lookup(disk, path)) if n not in (".", "..")]
    return sorted(names)


def unlink(disk: Disk, path: str) -> None:
    """Delete a file: free its blocks and inode, and remove its directory entry.

    Raise IsADirectory for a directory and FileNotFound for a missing path.
    """
    inum = lookup(disk, path)
    inode = read_inode(disk, inum)
    if inode.type == T_DIR:
        raise IsADirectory(path)
    parent_path, _, name = path.rstrip("/").rpartition("/")
    remove_entry(disk, lookup(disk, parent_path or "/"), name)
    for b in inode.blocks:
        if b:
            free_block(disk, b)
    free_inode(disk, inum)


if __name__ == "__main__":
    disk = Disk(64, 512)
    mkfs(disk)
    sb = read_superblock(disk)
    print("superblock:", sb)
    mkdir(disk, "/docs")
    write_file(disk, "/docs/hello.txt", b"hello, vsfs!")
    write_file(disk, "/big.bin", bytes(range(256)) * 5)  # 1280 bytes, 3 blocks
    print("root holds:", listdir(disk, "/"))
    inode = read_inode(disk, lookup(disk, "/big.bin"))
    print("big.bin inode:", inode.size, "bytes in blocks", [b for b in inode.blocks if b])
    print("free blocks:", free_blocks(disk), "free inodes:", free_inodes(disk))
    again = Disk.from_image(disk.image())  # unmount and mount again
    print("after remount:", read_file(again, "/docs/hello.txt"))
