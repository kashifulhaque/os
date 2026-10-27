"""Checks for the vsfs exercise. The disk is a bytearray; nothing touches real files."""

from oscheck import check, equal, fail, has

# For Disk(64, 512) and mkfs(disk, 16): block 0 superblock, 1 inode bitmap, 2 data bitmap,
# 16 inodes * 64 bytes = 1024 bytes = 2 inode-table blocks (3 and 4), so data starts at 5.
# That leaves 64 - 5 = 59 data blocks.


def fresh(sub, nblocks=64, ninodes=16):
    Disk, mkfs = has(sub, "Disk"), has(sub, "mkfs")
    disk = Disk(nblocks, 512)
    mkfs(disk, ninodes)
    return disk


def expect_error(sub, name, func, *args):
    exc = ValueError if name == "ValueError" else has(sub, name)
    try:
        func(*args)
    except exc:
        return
    except Exception as other:  # noqa: BLE001
        fail(f"expected {name}, but got {type(other).__name__}: {other}")
    fail(f"expected {name} to be raised, but the call returned normally")


@check("get_bit and set_bit read and write single bits, least significant bit first")
def test_bits(sub):
    get_bit, set_bit = has(sub, "get_bit"), has(sub, "set_bit")
    equal([get_bit(bytes([0b00000101]), i) for i in range(8)], [1, 0, 1, 0, 0, 0, 0, 0], label="bits of 0b101")
    b = bytearray(3)
    set_bit(b, 9, 1)
    equal(bytes(b), bytes([0, 2, 0]), label="set_bit(b, 9, 1) on 3 zero bytes")
    set_bit(b, 0, 1)
    set_bit(b, 23, 1)
    equal(bytes(b), bytes([1, 2, 128]), label="after setting bits 0 and 23")
    set_bit(b, 9, 0)
    equal(bytes(b), bytes([1, 0, 128]), label="after clearing bit 9")
    set_bit(b, 9, 0)
    equal(bytes(b), bytes([1, 0, 128]), label="clearing an already clear bit changes nothing")


@check("inode_location, read_inode, and write_inode find inodes in the table without disturbing neighbours")
def test_inode_io(sub):
    loc = has(sub, "inode_location")
    sb = {"block_size": 512, "inode_table": 3}
    equal(loc(sb, 0), (3, 0), label="inode 0")
    equal(loc(sb, 7), (3, 448), label="inode 7")  # 7 * 64 = 448, still block 3
    equal(loc(sb, 8), (4, 0), label="inode 8")  # 8 * 64 = 512, first byte of block 4
    equal(loc(sb, 9), (4, 64), label="inode 9")
    equal(loc({"block_size": 4096, "inode_table": 10}, 70), (11, 384), label="4096-byte blocks, inode 70")  # 70*64=4480
    Disk, Inode = has(sub, "Disk"), has(sub, "Inode")
    pack_sb = has(sub, "pack_superblock")
    read_inode, write_inode = has(sub, "read_inode"), has(sub, "write_inode")
    MAGIC = has(sub, "MAGIC")
    disk = Disk(64, 512)
    sb = {"magic": MAGIC, "block_size": 512, "nblocks": 64, "ninodes": 16,
          "inode_bitmap": 1, "data_bitmap": 2, "inode_table": 3, "data_start": 5}
    disk.write_block(0, pack_sb(sb).ljust(512, b"\0"))
    a = Inode(1, 700, [9, 10] + [0] * 10)
    b = Inode(2, 32, [11] + [0] * 11)
    write_inode(disk, 8, a)  # first inode of block 4
    write_inode(disk, 7, b)  # last inode of block 3
    got_a, got_b = read_inode(disk, 8), read_inode(disk, 7)
    equal((got_a.type, got_a.size, got_a.blocks), (1, 700, [9, 10] + [0] * 10), label="inode 8")
    equal((got_b.type, got_b.size, got_b.blocks), (2, 32, [11] + [0] * 11), label="inode 7")
    equal(read_inode(disk, 3).type, 0, label="an untouched inode is blank")
    start = 3 * 512 + 7 * 64
    if disk.data[start : start + 4] != bytes([2, 0, 0, 0]):
        fail(f"inode 7 should sit at byte {start} of the disk; found {bytes(disk.data[start:start+4])!r} there")
    expect_error(sub, "FSError", read_inode, disk, 16)


@check("mkfs lays out the superblock, bitmaps, and a root directory with '.' and '..'")
def test_mkfs(sub):
    read_sb, read_inode = has(sub, "read_superblock"), has(sub, "read_inode")
    get_bit, dir_entries = has(sub, "get_bit"), has(sub, "dir_entries")
    disk = fresh(sub)
    sb = read_sb(disk)
    want = {"block_size": 512, "nblocks": 64, "ninodes": 16, "inode_bitmap": 1,
            "data_bitmap": 2, "inode_table": 3, "data_start": 5}
    for k, v in want.items():
        equal(sb[k], v, label=f"superblock {k}")
    equal(sb["magic"], has(sub, "MAGIC"), label="superblock magic")
    ibm, dbm = disk.read_block(1), disk.read_block(2)
    equal([get_bit(ibm, i) for i in range(16)], [1] + [0] * 15, label="inode bitmap after mkfs")
    equal([get_bit(dbm, i) for i in range(59)], [1] + [0] * 58, label="data bitmap after mkfs")
    root = read_inode(disk, 0)
    equal((root.type, root.size, root.blocks[0]), (2, 64, 5), label="root inode (type, size, first block)")
    equal(dir_entries(disk, 0), [(".", 0), ("..", 0)], label="root directory entries")
    bigger = fresh(sub, 128, 40)  # 40 * 64 = 2560 bytes -> 5 inode-table blocks, data starts at 8
    equal(read_sb(bigger)["data_start"], 8, label="data_start for 40 inodes")
    expect_error(sub, "ValueError", has(sub, "mkfs"), has(sub, "Disk")(4, 512), 16)
    # The bitmaps and tables must be zero outside what mkfs set up.
    if any(disk.read_block(n) != bytes(512) for n in range(6, 64)):
        fail("blocks after the root directory's block should still be all zeros after mkfs")
    expect_error(sub, "FSError", read_sb, has(sub, "Disk")(64, 512))


@check("alloc and free keep the bitmaps in step: lowest free first, reuse after free, NoSpace when full")
def test_alloc(sub):
    alloc_inode, free_inode = has(sub, "alloc_inode"), has(sub, "free_inode")
    alloc_block, free_block = has(sub, "alloc_block"), has(sub, "free_block")
    free_blocks, free_inodes = has(sub, "free_blocks"), has(sub, "free_inodes")
    disk = fresh(sub, 16, 4)  # 4 inodes = 256 bytes = 1 inode-table block; data_start = 4; 12 data blocks
    equal(free_inodes(disk), 3, label="free inodes after mkfs")
    equal(free_blocks(disk), 11, label="free data blocks after mkfs")
    equal([alloc_inode(disk) for _ in range(3)], [1, 2, 3], label="three inode allocations")
    expect_error(sub, "NoSpace", alloc_inode, disk)
    free_inode(disk, 2)
    equal(alloc_inode(disk), 2, label="alloc after freeing inode 2")
    blocks = [alloc_block(disk) for _ in range(11)]
    equal(blocks, list(range(5, 16)), label="eleven block allocations (absolute numbers)")
    equal(free_blocks(disk), 0, label="free blocks when full")
    expect_error(sub, "NoSpace", alloc_block, disk)
    free_block(disk, 9)
    equal(free_blocks(disk), 1, label="free blocks after freeing one")
    disk.write_block(9, b"\xff" * 512)
    equal(alloc_block(disk), 9, label="alloc_block returns the freed block")
    equal(disk.read_block(9), bytes(512), label="a newly allocated block is zero-filled")
    expect_error(sub, "FSError", free_block, disk, 2)  # block 2 is the data bitmap, not a data block


@check("write_data and read_data handle empty, partial, multi-block, and padded contents")
def test_data(sub):
    alloc_inode, write_inode = has(sub, "alloc_inode"), has(sub, "write_inode")
    Inode, T_FILE = has(sub, "Inode"), has(sub, "T_FILE")
    read_inode, free_blocks = has(sub, "read_inode"), has(sub, "free_blocks")
    write_data, read_data = has(sub, "write_data"), has(sub, "read_data")
    disk = fresh(sub)
    inum = alloc_inode(disk)
    write_inode(disk, inum, Inode(T_FILE))
    before = free_blocks(disk)
    equal(read_data(disk, inum), b"", label="empty file")
    payload = bytes((i * 7) % 256 for i in range(1300))  # 1300 bytes -> 3 blocks of 512
    write_data(disk, inum, payload)
    inode = read_inode(disk, inum)
    equal(inode.size, 1300, label="size after write")
    equal(len([b for b in inode.blocks if b]), 3, label="blocks used for 1300 bytes")
    equal(free_blocks(disk), before - 3, label="free blocks after write")
    equal(read_data(disk, inum), payload, label="whole file")
    equal(read_data(disk, inum, 500, 30), payload[500:530], label="read across the first block boundary")
    equal(read_data(disk, inum, 1290, 100), payload[1290:], label="read that runs past the end")
    equal(read_data(disk, inum, 2000, 10), b"", label="read starting past the end")
    last = disk.read_block(inode.blocks[2])
    equal(last[1300 - 1024 :], bytes(512 - (1300 - 1024)), label="padding in the last block")
    write_data(disk, inum, b"tiny")
    equal(read_data(disk, inum), b"tiny", label="after shrinking")
    equal(free_blocks(disk), before - 1, label="blocks returned after shrinking")
    write_data(disk, inum, b"")
    equal(free_blocks(disk), before, label="blocks returned after emptying")
    equal(write_data(disk, inum, b"x" * 512), None, label="exactly one block")
    equal(len([b for b in read_inode(disk, inum).blocks if b]), 1, label="512 bytes fit in one block")


@check("write_data refuses files over 12 blocks or beyond free space, and leaves the file intact")
def test_limits(sub):
    alloc_inode, write_inode = has(sub, "alloc_inode"), has(sub, "write_inode")
    Inode, T_FILE = has(sub, "Inode"), has(sub, "T_FILE")
    write_data, read_data, free_blocks = has(sub, "write_data"), has(sub, "read_data"), has(sub, "free_blocks")
    disk = fresh(sub)
    a = alloc_inode(disk)
    write_inode(disk, a, Inode(T_FILE))
    write_data(disk, a, b"A" * 6144)  # exactly 12 blocks is allowed
    equal(len(read_data(disk, a)), 6144, label="a 12-block file")
    expect_error(sub, "FileTooBig", write_data, disk, a, b"B" * 6145)
    equal(read_data(disk, a), b"A" * 6144, label="file after a FileTooBig error")
    b = alloc_inode(disk)
    write_inode(disk, b, Inode(T_FILE))
    write_data(disk, b, b"C" * 5000)  # 10 blocks: 59 - 1 (root) - 12 - 10 = 36 free
    c = alloc_inode(disk)
    write_inode(disk, c, Inode(T_FILE))
    for i in range(3):
        write_data(disk, c, b"x")  # rewriting must not leak blocks
    equal(free_blocks(disk), 59 - 1 - 12 - 10 - 1, label="free blocks, no leak after rewrites")
    small = fresh(sub, 10, 4)  # data_start = 4, 6 data blocks, 5 free after the root
    d = alloc_inode(small)
    write_inode(small, d, Inode(T_FILE))
    expect_error(sub, "NoSpace", write_data, small, d, b"z" * (6 * 512))
    equal(free_blocks(small), 5, label="free blocks after a NoSpace error")
    write_data(small, d, b"z" * (5 * 512))
    equal(free_blocks(small), 0, label="free blocks after filling the disk")
    write_data(small, d, b"z" * (5 * 512))  # rewriting the same size works: old blocks count as available


@check("directories are files of (name, inum) entries: add_entry and remove_entry edit that file")
def test_dirs(sub):
    dir_entries, add_entry, remove_entry = has(sub, "dir_entries"), has(sub, "add_entry"), has(sub, "remove_entry")
    read_inode, read_data = has(sub, "read_inode"), has(sub, "read_data")
    disk = fresh(sub)
    add_entry(disk, 0, "alpha", 3)
    add_entry(disk, 0, "beta", 4)
    equal(dir_entries(disk, 0), [(".", 0), ("..", 0), ("alpha", 3), ("beta", 4)], label="after two adds")
    equal(read_inode(disk, 0).size, 4 * 32, label="directory size is 32 bytes per entry")
    raw = read_data(disk, 0)
    equal(raw[64:96], b"alpha" + bytes(23) + bytes([3, 0, 0, 0]), label="the bytes of the third entry")
    remove_entry(disk, 0, "alpha")
    equal(dir_entries(disk, 0), [(".", 0), ("..", 0), ("beta", 4)], label="after removing alpha")
    expect_error(sub, "FileExists", add_entry, disk, 0, "beta", 9)
    expect_error(sub, "FileNotFound", remove_entry, disk, 0, "gamma")
    expect_error(sub, "ValueError", add_entry, disk, 0, "", 5)
    expect_error(sub, "ValueError", add_entry, disk, 0, "a/b", 5)
    expect_error(sub, "ValueError", add_entry, disk, 0, "n" * 29, 5)
    add_entry(disk, 0, "m" * 28, 6)  # 28 bytes is allowed
    for i in range(20):  # more than one block of entries (16 fit in 512 bytes)
        add_entry(disk, 0, f"f{i}", 7)
    equal(len(dir_entries(disk, 0)), 3 + 1 + 20, label="entry count across several blocks")
    equal(dir_entries(disk, 0)[-1], ("f19", 7), label="last entry")


@check("create and lookup build and resolve a tree, including '/', '.', '..', and errors")
def test_paths(sub):
    create, mkdir, lookup = has(sub, "create"), has(sub, "mkdir"), has(sub, "lookup")
    dir_entries, read_inode = has(sub, "dir_entries"), has(sub, "read_inode")
    free_blocks, free_inodes = has(sub, "free_blocks"), has(sub, "free_inodes")
    disk = fresh(sub)
    equal(lookup(disk, "/"), 0, label="lookup('/')")
    docs = mkdir(disk, "/docs")
    equal(docs, 1, label="first inode after the root")
    notes = create(disk, "/docs/notes.txt")
    equal(notes, 2, label="second new inode")
    sub_dir = create(disk, "/docs/old/", "dir")  # trailing slash is fine
    equal(lookup(disk, "/docs/notes.txt"), notes, label="lookup file")
    equal(lookup(disk, "/docs//old/"), sub_dir, label="lookup with extra slashes")
    equal(lookup(disk, "/docs/old/.."), docs, label="lookup with '..'")
    equal(lookup(disk, "/docs/./notes.txt"), notes, label="lookup with '.'")
    equal(lookup(disk, "/.."), 0, label="'..' at the root stays at the root")
    equal(dir_entries(disk, docs), [(".", docs), ("..", 0), ("notes.txt", notes), ("old", sub_dir)], label="entries of /docs")
    equal(dir_entries(disk, sub_dir), [(".", sub_dir), ("..", docs)], label="entries of /docs/old")
    equal(read_inode(disk, notes).type, 1, label="a file's inode type")
    equal(read_inode(disk, docs).type, 2, label="a directory's inode type")
    expect_error(sub, "FileNotFound", lookup, disk, "/docs/missing")
    expect_error(sub, "NotADirectory", lookup, disk, "/docs/notes.txt/x")
    expect_error(sub, "ValueError", lookup, disk, "docs")
    expect_error(sub, "FileExists", create, disk, "/docs/notes.txt")
    expect_error(sub, "FileNotFound", create, disk, "/nowhere/file")
    expect_error(sub, "NotADirectory", create, disk, "/docs/notes.txt/inside")
    # A failed create must leak nothing.
    blocks, inodes = free_blocks(disk), free_inodes(disk)
    expect_error(sub, "ValueError", create, disk, "/docs/" + "n" * 40)
    equal((free_blocks(disk), free_inodes(disk)), (blocks, inodes), label="free (blocks, inodes) after a failed create")


@check("write_file, read_file, listdir, and unlink work end to end and release space")
def test_files(sub):
    mkdir, write_file, read_file = has(sub, "mkdir"), has(sub, "write_file"), has(sub, "read_file")
    listdir, unlink = has(sub, "listdir"), has(sub, "unlink")
    free_blocks, free_inodes = has(sub, "free_blocks"), has(sub, "free_inodes")
    lookup = has(sub, "lookup")
    disk = fresh(sub)
    base_blocks, base_inodes = free_blocks(disk), free_inodes(disk)
    mkdir(disk, "/a")
    mkdir(disk, "/a/b")
    write_file(disk, "/a/b/deep.txt", b"deep")
    write_file(disk, "/top.txt", b"first")
    write_file(disk, "/top.txt", b"second version")  # overwrite replaces
    big = bytes(range(256)) * 10  # 2560 bytes, 5 blocks
    write_file(disk, "/a/big.bin", big)
    equal(read_file(disk, "/a/b/deep.txt"), b"deep", label="deep file")
    equal(read_file(disk, "/top.txt"), b"second version", label="overwritten file")
    equal(read_file(disk, "/a/big.bin"), big, label="five-block file")
    equal(listdir(disk, "/"), ["a", "top.txt"], label="listdir /")
    equal(listdir(disk, "/a"), ["b", "big.bin"], label="listdir /a")
    equal(listdir(disk, "/a/b/"), ["deep.txt"], label="listdir /a/b/")
    expect_error(sub, "IsADirectory", read_file, disk, "/a")
    expect_error(sub, "IsADirectory", write_file, disk, "/a", b"x")
    expect_error(sub, "IsADirectory", unlink, disk, "/a")
    expect_error(sub, "NotADirectory", listdir, disk, "/top.txt")
    expect_error(sub, "FileNotFound", read_file, disk, "/nope")
    unlink(disk, "/a/big.bin")
    equal(listdir(disk, "/a"), ["b"], label="listdir /a after unlink")
    expect_error(sub, "FileNotFound", lookup, disk, "/a/big.bin")
    unlink(disk, "/top.txt")
    unlink(disk, "/a/b/deep.txt")
    # Only the directories /a and /a/b remain: 2 inodes, and one block each.
    equal(free_inodes(disk), base_inodes - 2, label="free inodes after deleting every file")
    equal(free_blocks(disk), base_blocks - 2, label="free data blocks after deleting every file")


@check("remounting from the same bytes finds every file, and the bytes really are on the disk")
def test_persistence(sub):
    Disk = has(sub, "Disk")
    mkdir, write_file, read_file = has(sub, "mkdir"), has(sub, "write_file"), has(sub, "read_file")
    listdir, lookup, read_inode = has(sub, "listdir"), has(sub, "lookup"), has(sub, "read_inode")
    free_blocks, free_inodes, unlink = has(sub, "free_blocks"), has(sub, "free_inodes"), has(sub, "unlink")
    disk = fresh(sub)
    mkdir(disk, "/etc")
    files = {"/etc/motd": b"welcome", "/etc/big": b"0123456789" * 120, "/readme": b"R" * 512}
    for path, data in files.items():
        write_file(disk, path, data)
    unlink(disk, "/readme")
    image = disk.image()
    equal(len(image), 64 * 512, label="disk image size")
    other = Disk.from_image(image)  # a fresh Disk over copied bytes: nothing in memory carries over
    for path, data in files.items():
        if path == "/readme":
            continue
        equal(read_file(other, path), data, label=f"read_file({path!r}) after remount")
    equal(listdir(other, "/"), ["etc"], label="listdir / after remount")
    equal((free_blocks(other), free_inodes(other)), (free_blocks(disk), free_inodes(disk)), label="free counts after remount")
    # The raw bytes of /etc/motd sit in the block its inode points to.
    inode = read_inode(other, lookup(other, "/etc/motd"))
    block = inode.blocks[0]
    if not other.data[block * 512 : block * 512 + 7] == b"welcome":
        fail(f"inode says /etc/motd is in block {block}, but that block starts with {bytes(other.data[block*512:block*512+7])!r}")
    # Writing through the new Disk and remounting again keeps the change.
    write_file(other, "/etc/motd", b"changed")
    third = Disk.from_image(other.image())
    equal(read_file(third, "/etc/motd"), b"changed", label="second remount sees the change")
    equal(read_file(disk, "/etc/motd"), b"welcome", label="the original disk is unaffected")
