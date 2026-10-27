"""The real file API: descriptors, inodes, links, directory walks, and paths."""

from __future__ import annotations

import os


def write_file(path: str, data: bytes) -> int:
    """Create or truncate `path` and write all of `data`. Return the byte count.

    Use os.open, os.write, and os.close. os.write may write less than asked,
    so keep writing until every byte is out.

    >>> write_file("/tmp/x", b"hello")
    5
    """
    raise NotImplementedError("write this function")


def append_file(path: str, data: bytes) -> None:
    """Append `data` to the end of `path`, creating the file if it is missing.

    Use the O_APPEND flag so every write lands at the end.

    >>> append_file("/tmp/x", b" world")   # file now holds b"hello world"
    """
    raise NotImplementedError("write this function")


def read_file(path: str) -> bytes:
    """Return the entire contents of `path`, using os.open and os.read.

    >>> read_file("/tmp/x")
    b'hello world'
    """
    raise NotImplementedError("write this function")


def read_at(path: str, offset: int, n: int) -> bytes:
    """Return up to `n` bytes starting `offset` bytes into the file, using os.lseek.

    Fewer than `n` bytes (possibly none) come back near or past the end.

    >>> read_at("/tmp/x", 6, 3)
    b'wor'
    """
    raise NotImplementedError("write this function")


def file_info(path: str) -> dict:
    """Describe `path` with os.stat (following symbolic links).

    Returns {"inode": st_ino, "links": st_nlink, "size": st_size, "is_dir": bool}.

    >>> file_info("/tmp/x")["size"]
    11
    """
    raise NotImplementedError("write this function")


def same_file(a: str, b: str) -> bool:
    """True when two paths name the same inode on the same device.

    Follow symbolic links, so a symlink and its target are the same file.
    A byte-for-byte copy is NOT the same file.

    >>> same_file("/tmp/x", "/tmp/x")
    True
    """
    raise NotImplementedError("write this function")


def classify(path: str) -> str:
    """Say what `path` is, without following a final symbolic link.

    Returns one of "file", "dir", "symlink", "broken symlink", or "missing".
    A "broken symlink" is a symbolic link whose target does not exist.

    >>> classify("/definitely/not/here")
    'missing'
    """
    raise NotImplementedError("write this function")


def walk_tree(root: str) -> list[str]:
    """Return the lines a `tree`-style listing of `root` would print.

    The first line is the basename of `root` followed by "/". Entries of a
    directory are sorted by name. Each level indents two more spaces.
    A directory shows a trailing "/" and its children follow it. A symbolic
    link shows "name -> target" and is never followed. Use os.scandir.

    >>> walk_tree("/tmp/proj")
    ['proj/', '  a.txt', '  src/', '    main.py']
    """
    raise NotImplementedError("write this function")


def normalize_path(path: str) -> str:
    """Clean a path by text alone, the way POSIX does, touching no files.

    Drop empty parts (from "//") and ".". A ".." removes the part before it.
    At the root of an absolute path, ".." is dropped ("/.." is "/").
    In a relative path, leading ".." parts stay ("../a"). An empty result
    is "/" for an absolute path and "." for a relative one.

    >>> normalize_path("/a/b/../c/./d//")
    '/a/c/d'
    """
    raise NotImplementedError("write this function")


if __name__ == "__main__":
    import shutil
    import tempfile

    root = tempfile.mkdtemp()
    try:
        notes = os.path.join(root, "notes.txt")
        write_file(notes, b"hello")
        append_file(notes, b" world")
        print("read_file:", read_file(notes))
        print("read_at(6, 5):", read_at(notes, 6, 5))
        os.link(notes, os.path.join(root, "hard.txt"))
        os.symlink("notes.txt", os.path.join(root, "soft.txt"))
        os.mkdir(os.path.join(root, "sub"))
        write_file(os.path.join(root, "sub", "inner.txt"), b"x")
        info = file_info(notes)
        print("links:", info["links"], "size:", info["size"])
        print("hard is same file:", same_file(notes, os.path.join(root, "hard.txt")))
        print("soft is:", classify(os.path.join(root, "soft.txt")))
        print("\n".join(walk_tree(root)).replace(os.path.basename(root), "root", 1))
        print(normalize_path("/a/b/../c/./d//"), normalize_path("../a/./b/.."))
    finally:
        shutil.rmtree(root)
