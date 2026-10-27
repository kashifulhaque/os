"""Checks for the files and directories exercise. All files live in temp directories."""

import os
import posixpath
import random
import shutil
import tempfile
from contextlib import contextmanager

from oscheck import check, equal, fail, has


@contextmanager
def workdir():
    root = tempfile.mkdtemp(prefix="oscheck23-")
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("write_file and read_file round-trip bytes, including data larger than one read chunk")
def test_roundtrip(sub):
    write_file, read_file = has(sub, "write_file"), has(sub, "read_file")
    with workdir() as d:
        p = os.path.join(d, "a.bin")
        equal(write_file(p, b"hello"), 5, label="write_file return value")
        equal(read_file(p), b"hello", label="read_file after write")
        big = bytes(range(256)) * 1000  # 256,000 bytes
        equal(write_file(p, big), len(big), label="write_file return value for big data")
        got = read_file(p)
        if got != big:
            fail(f"big file came back with {len(got)} bytes, expected {len(big)} identical bytes")
        equal(os.stat(p).st_size, len(big), label="size on disk")


@check("write_file truncates an existing file and creates a missing one with mode 0o644 minus umask")
def test_truncate(sub):
    write_file, read_file = has(sub, "write_file"), has(sub, "read_file")
    with workdir() as d:
        p = os.path.join(d, "t.txt")
        write_file(p, b"a long first version")
        write_file(p, b"short")
        equal(read_file(p), b"short", label="file after second write")
        write_file(p, b"")
        equal(read_file(p), b"", label="file after writing nothing")
        mode = os.stat(p).st_mode & 0o777
        if mode & 0o133:
            fail(f"new file mode is {oct(mode)}; expected at most 0o644 (the umask can only remove bits)")


@check("append_file adds to the end and creates the file when missing")
def test_append(sub):
    append_file, read_file = has(sub, "append_file"), has(sub, "read_file")
    with workdir() as d:
        p = os.path.join(d, "log.txt")
        append_file(p, b"one\n")
        append_file(p, b"two\n")
        equal(read_file(p), b"one\ntwo\n", label="two appends")


@check("read_at seeks to an offset and returns up to n bytes, fewer near the end")
def test_read_at(sub):
    write_file, read_at = has(sub, "write_file"), has(sub, "read_at")
    with workdir() as d:
        p = os.path.join(d, "n.txt")
        write_file(p, b"0123456789")
        equal(read_at(p, 3, 4), b"3456", label="read_at(3, 4)")
        equal(read_at(p, 8, 10), b"89", label="read_at(8, 10) near the end")
        equal(read_at(p, 10, 5), b"", label="read_at at end of file")
        equal(read_at(p, 50, 5), b"", label="read_at past end of file")
        equal(read_at(p, 0, 0), b"", label="read_at asking for 0 bytes")


@check("file_info reports inode, size, directory flag, and link count that grows with hard links")
def test_info(sub):
    write_file, file_info = has(sub, "write_file"), has(sub, "file_info")
    with workdir() as d:
        p = os.path.join(d, "f")
        write_file(p, b"abcdefg")
        info = file_info(p)
        equal(info["size"], 7, label="size")
        equal(info["links"], 1, label="links of a fresh file")
        equal(info["is_dir"], False, label="is_dir of a file")
        equal(info["inode"], os.stat(p).st_ino, label="inode")
        os.link(p, os.path.join(d, "g"))
        equal(file_info(p)["links"], 2, label="links after os.link")
        os.link(p, os.path.join(d, "h"))
        equal(file_info(os.path.join(d, "h"))["links"], 3, label="links seen through the third name")
        os.unlink(os.path.join(d, "g"))
        equal(file_info(p)["links"], 2, label="links after unlinking one name")
        equal(file_info(d)["is_dir"], True, label="is_dir of a directory")


@check("same_file is true for hard links and symlinks, false for a copy")
def test_same_file(sub):
    write_file, same_file = has(sub, "write_file"), has(sub, "same_file")
    with workdir() as d:
        a, hard, soft, copy = (os.path.join(d, n) for n in ("a", "hard", "soft", "copy"))
        write_file(a, b"data")
        os.link(a, hard)
        os.symlink("a", soft)
        write_file(copy, b"data")
        equal(same_file(a, hard), True, label="same_file(a, hard link)")
        equal(same_file(a, soft), True, label="same_file(a, symlink to a)")
        equal(same_file(a, copy), False, label="same_file(a, byte-for-byte copy)")
        equal(same_file(a, a), True, label="same_file(a, a)")


@check("classify tells files, directories, symlinks, broken symlinks, and missing paths apart")
def test_classify(sub):
    write_file, classify = has(sub, "write_file"), has(sub, "classify")
    with workdir() as d:
        f, sub_d = os.path.join(d, "f"), os.path.join(d, "dir")
        write_file(f, b"x")
        os.mkdir(sub_d)
        os.symlink("f", os.path.join(d, "good"))
        os.symlink("nowhere", os.path.join(d, "bad"))
        os.symlink("dir", os.path.join(d, "dirlink"))
        equal(classify(f), "file", label="regular file")
        equal(classify(sub_d), "dir", label="directory")
        equal(classify(os.path.join(d, "good")), "symlink", label="symlink to a file")
        equal(classify(os.path.join(d, "dirlink")), "symlink", label="symlink to a directory")
        equal(classify(os.path.join(d, "bad")), "broken symlink", label="dangling symlink")
        equal(classify(os.path.join(d, "ghost")), "missing", label="missing path")


@check("walk_tree prints a sorted, indented tree and shows symlinks without following them")
def test_walk(sub):
    write_file, walk_tree = has(sub, "write_file"), has(sub, "walk_tree")
    with workdir() as d:
        root = os.path.join(d, "proj")
        os.makedirs(os.path.join(root, "src", "deep"))
        os.mkdir(os.path.join(root, "empty"))
        write_file(os.path.join(root, "b.txt"), b"b")
        write_file(os.path.join(root, "a.txt"), b"a")
        write_file(os.path.join(root, "src", "main.py"), b"m")
        write_file(os.path.join(root, "src", "deep", "z"), b"z")
        os.symlink("src", os.path.join(root, "link"))
        want = [
            "proj/",
            "  a.txt",
            "  b.txt",
            "  empty/",
            "  link -> src",
            "  src/",
            "    deep/",
            "      z",
            "    main.py",
        ]
        equal(walk_tree(root), want, label="walk_tree(proj)")
        equal(walk_tree(os.path.join(d, "proj") + "/"), want, label="walk_tree with a trailing slash")


@check("normalize_path resolves '.', '..', and repeated slashes by text alone")
def test_normalize(sub):
    norm = has(sub, "normalize_path")
    cases = {
        "/a/b/../c/./d//": "/a/c/d",
        "/": "/",
        "/..": "/",
        "/../../a": "/a",
        "/a/..": "/",
        "a/b/..": "a",
        "a/..": ".",
        "": ".",
        ".": ".",
        "./": ".",
        "../a": "../a",
        "../../a/b/../c": "../../a/c",
        "a/../..": "..",
        "///x///y": "/x/y",
        "a/b/c/../../..": ".",
        "..": "..",
    }
    for raw, want in cases.items():
        equal(norm(raw), want, label=f"normalize_path({raw!r})")


@check("normalize_path agrees with posixpath.normpath on random paths")
def test_normalize_random(sub):
    norm = has(sub, "normalize_path")
    rng = random.Random(0)
    parts = ["a", "b", "cc", ".", "..", ".."]
    for _ in range(300):
        body = "/".join(rng.choice(parts + [""]) for _ in range(rng.randrange(0, 8)))
        path = rng.choice(["", "/"]) + body
        if path.startswith("//"):
            path = "/" + path.lstrip("/")  # POSIX keeps a leading double slash; we do not test that
        equal(norm(path), posixpath.normpath(path), label=f"normalize_path({path!r})")
