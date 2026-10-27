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
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        view = memoryview(data)
        done = 0
        while done < len(data):
            # A write can be short; the return value says how much went out.
            done += os.write(fd, view[done:])
    finally:
        os.close(fd)
    return len(data)


def append_file(path: str, data: bytes) -> None:
    """Append `data` to the end of `path`, creating the file if it is missing.

    Use the O_APPEND flag so every write lands at the end.

    >>> append_file("/tmp/x", b" world")   # file now holds b"hello world"
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        view = memoryview(data)
        done = 0
        while done < len(data):
            done += os.write(fd, view[done:])
    finally:
        os.close(fd)


def read_file(path: str) -> bytes:
    """Return the entire contents of `path`, using os.open and os.read.

    >>> read_file("/tmp/x")
    b'hello world'
    """
    fd = os.open(path, os.O_RDONLY)
    try:
        chunks = []
        while True:
            chunk = os.read(fd, 4096)
            if chunk == b"":  # end of file
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def read_at(path: str, offset: int, n: int) -> bytes:
    """Return up to `n` bytes starting `offset` bytes into the file, using os.lseek.

    Fewer than `n` bytes (possibly none) come back near or past the end.

    >>> read_at("/tmp/x", 6, 3)
    b'wor'
    """
    fd = os.open(path, os.O_RDONLY)
    try:
        os.lseek(fd, offset, os.SEEK_SET)
        out = b""
        while len(out) < n:
            chunk = os.read(fd, n - len(out))
            if chunk == b"":
                break
            out += chunk
        return out
    finally:
        os.close(fd)


def file_info(path: str) -> dict:
    """Describe `path` with os.stat (following symbolic links).

    Returns {"inode": st_ino, "links": st_nlink, "size": st_size, "is_dir": bool}.

    >>> file_info("/tmp/x")["size"]
    11
    """
    st = os.stat(path)
    return {
        "inode": st.st_ino,
        "links": st.st_nlink,
        "size": st.st_size,
        "is_dir": os.path.isdir(path),
    }


def same_file(a: str, b: str) -> bool:
    """True when two paths name the same inode on the same device.

    Follow symbolic links, so a symlink and its target are the same file.
    A byte-for-byte copy is NOT the same file.

    >>> same_file("/tmp/x", "/tmp/x")
    True
    """
    sa, sb = os.stat(a), os.stat(b)
    # An inode number is only unique within one device.
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def classify(path: str) -> str:
    """Say what `path` is, without following a final symbolic link.

    Returns one of "file", "dir", "symlink", "broken symlink", or "missing".
    A "broken symlink" is a symbolic link whose target does not exist.

    >>> classify("/definitely/not/here")
    'missing'
    """
    if os.path.islink(path):
        return "symlink" if os.path.exists(path) else "broken symlink"
    if os.path.isdir(path):
        return "dir"
    if os.path.exists(path):
        return "file"
    return "missing"


def walk_tree(root: str) -> list[str]:
    """Return the lines a `tree`-style listing of `root` would print.

    The first line is the basename of `root` followed by "/". Entries of a
    directory are sorted by name. Each level indents two more spaces.
    A directory shows a trailing "/" and its children follow it. A symbolic
    link shows "name -> target" and is never followed. Use os.scandir.

    >>> walk_tree("/tmp/proj")
    ['proj/', '  a.txt', '  src/', '    main.py']
    """
    lines = [os.path.basename(os.path.normpath(root)) + "/"]

    def visit(directory: str, depth: int) -> None:
        with os.scandir(directory) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            pad = "  " * depth
            if entry.is_symlink():
                lines.append(f"{pad}{entry.name} -> {os.readlink(entry.path)}")
            elif entry.is_dir(follow_symlinks=False):
                lines.append(f"{pad}{entry.name}/")
                visit(entry.path, depth + 1)
            else:
                lines.append(f"{pad}{entry.name}")

    visit(root, 1)
    return lines


def normalize_path(path: str) -> str:
    """Clean a path by text alone, the way POSIX does, touching no files.

    Drop empty parts (from "//") and ".". A ".." removes the part before it.
    At the root of an absolute path, ".." is dropped ("/.." is "/").
    In a relative path, leading ".." parts stay ("../a"). An empty result
    is "/" for an absolute path and "." for a relative one.

    >>> normalize_path("/a/b/../c/./d//")
    '/a/c/d'
    """
    absolute = path.startswith("/")
    stack: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack and stack[-1] != "..":
                stack.pop()
            elif not absolute:
                stack.append("..")
            # absolute and empty stack: ".." at the root stays at the root
        else:
            stack.append(part)
    joined = "/".join(stack)
    if absolute:
        return "/" + joined
    return joined or "."


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
