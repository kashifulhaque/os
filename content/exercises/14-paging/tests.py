"""Checks for the paging exercise."""

import random

from oscheck import check, equal, fail, has


def _faults(sub, fn, *args, **kwargs):
    """Call fn and return True if it raised PageFault; fail on a value."""
    PageFault = has(sub, "PageFault")
    try:
        got = fn(*args, **kwargs)
    except PageFault:
        return True
    fail(f"expected PageFault, but the call returned {got!r}")


@check("split_address separates page number and offset")
def test_split(sub):
    split_address = has(sub, "split_address")
    # 0x3ABC with 4 KiB pages: 0x3ABC >> 12 = 3, 0x3ABC & 0xFFF = 0xABC.
    equal(split_address(0x3ABC, 4096), (3, 0xABC), label="split_address(0x3ABC, 4096)")
    equal(split_address(0, 4096), (0, 0), label="split_address(0, 4096)")
    equal(split_address(0xFFFF, 4096), (0xF, 0xFFF), label="split_address(0xFFFF, 4096)")
    # 256-byte pages: offset is the low 8 bits.
    equal(split_address(0x1234, 256), (0x12, 0x34), label="split_address(0x1234, 256)")
    equal(split_address(0x1234, 1024), (4, 0x234), label="split_address(0x1234, 1024)")


@check("split_address and page_number * page_size + offset round-trip")
def test_roundtrip(sub):
    split_address = has(sub, "split_address")
    rng = random.Random(0)
    for page_size in (256, 4096, 65536):
        for _ in range(50):
            vaddr = rng.randrange(1 << 32)
            vpn, off = split_address(vaddr, page_size)
            if not 0 <= off < page_size or vpn * page_size + off != vaddr:
                fail(f"split_address({vaddr:#x}, {page_size}) returned {(vpn, off)}, which does not rebuild the address")


@check("translate maps an address through a linear table")
def test_translate(sub):
    translate, PTE = has(sub, "translate"), has(sub, "PTE")
    table = [PTE(5), PTE(9), PTE(0)]
    # vpn 0, offset 0x123 -> frame 5: 5 * 4096 + 0x123 = 0x5123.
    equal(translate(table, 0x0123, 4096), 0x5123, label="translate(0x0123)")
    # vpn 1, offset 0xFFF -> frame 9: 9 * 4096 + 0xFFF = 0x9FFF.
    equal(translate(table, 0x1FFF, 4096), 0x9FFF, label="translate(0x1FFF)")
    # vpn 2 -> frame 0: physical address equals the offset.
    equal(translate(table, 0x2010, 4096), 0x10, label="translate(0x2010)")
    # Another page size: 256-byte pages, vpn 1 offset 0x34 -> frame 9: 9 * 256 + 0x34 = 0x934.
    equal(translate(table, 0x134, 256), 0x934, label="translate(0x134, page_size=256)")


@check("translate raises PageFault for unmapped, invalid, and out-of-range pages")
def test_faults(sub):
    translate, PTE = has(sub, "translate"), has(sub, "PTE")
    table = [PTE(5), None, PTE(3, valid=False)]
    _faults(sub, translate, table, 0x1000, 4096)   # vpn 1 is None
    _faults(sub, translate, table, 0x2000, 4096)   # vpn 2 has valid False
    _faults(sub, translate, table, 0x3000, 4096)   # vpn 3 is past the end
    _faults(sub, translate, table, 0xFFFFF000, 4096)


@check("translate enforces read and write permission bits")
def test_permissions(sub):
    translate, PTE = has(sub, "translate"), has(sub, "PTE")
    table = [PTE(1, write=False), PTE(2, read=False, write=False), PTE(3)]
    equal(translate(table, 0x10, 4096), 0x1010, label="read of a read-only page")
    _faults(sub, translate, table, 0x10, 4096, write=True)      # write to read-only
    _faults(sub, translate, table, 0x1010, 4096)                # read of no-read page
    equal(translate(table, 0x2010, 4096, write=True), 0x3010, label="write to a read-write page")


@check("split_two_level splits into directory index, table index, and offset")
def test_split_two_level(sub):
    split_two_level = has(sub, "split_two_level")
    # 0x00403ABC: vpn = 0x403 = 1027; 1027 // 1024 = 1, 1027 % 1024 = 3; offset 0xABC.
    equal(split_two_level(0x00403ABC, 4096, 1024), (1, 3, 0xABC), label="0x00403ABC")
    equal(split_two_level(0, 4096, 1024), (0, 0, 0), label="0")
    # Top of a 32-bit space: dir 1023, table 1023, offset 0xFFF.
    equal(split_two_level(0xFFFFFFFF, 4096, 1024), (1023, 1023, 0xFFF), label="0xFFFFFFFF")
    # Small example: 256-byte pages, 4 entries per table. 0x0B34: vpn 0xB = 11 -> (2, 3), offset 0x34.
    equal(split_two_level(0x0B34, 256, 4), (2, 3, 0x34), label="0x0B34 with 4 entries per table")


@check("map_page builds second-level tables on demand and translate_two_level walks them")
def test_two_level(sub):
    map_page, PTE = has(sub, "map_page"), has(sub, "PTE")
    translate_two_level = has(sub, "translate_two_level")
    directory = [None] * 8
    map_page(directory, 0x13, PTE(7), 4)   # vpn 19: dir 4, table 3
    if directory[4] is None or len(directory[4]) != 4:
        fail(f"map_page should create a 4-entry table in directory[4], got {directory[4]!r}")
    if any(slot is not None for i, slot in enumerate(directory) if i != 4):
        fail("map_page should create only the one second-level table it needs")
    # 256-byte pages: address of vpn 19 offset 0x2A is 19 * 256 + 0x2A = 0x132A; frame 7 -> 7 * 256 + 0x2A = 0x72A.
    equal(translate_two_level(directory, 0x132A, 256, 4), 0x72A, label="translate_two_level(0x132A)")
    map_page(directory, 0x12, PTE(2), 4)   # same second-level table, slot 2
    equal(translate_two_level(directory, 0x1200, 256, 4), 0x200, label="translate_two_level(0x1200)")
    equal(sum(1 for s in directory if s is not None), 1, label="number of second-level tables")


@check("translate_two_level raises PageFault on every kind of miss and permission error")
def test_two_level_faults(sub):
    map_page, PTE = has(sub, "map_page"), has(sub, "PTE")
    translate_two_level = has(sub, "translate_two_level")
    directory = [None] * 8
    map_page(directory, 0x13, PTE(7, write=False), 4)
    map_page(directory, 0x12, PTE(2, valid=False), 4)
    _faults(sub, translate_two_level, directory, 0x0000, 256, 4)          # dir 0 is None
    _faults(sub, translate_two_level, directory, 0x1100, 256, 4)          # dir 4, table 1 is None
    _faults(sub, translate_two_level, directory, 0x1200, 256, 4)          # entry invalid
    _faults(sub, translate_two_level, directory, 0x13FF, 256, 4, write=True)  # read-only
    _faults(sub, translate_two_level, directory, 0x10000, 256, 4)         # dir 16 is past the end
    equal(translate_two_level(directory, 0x13FF, 256, 4), 0x7FF, label="read of the read-only page")


@check("linear_table_bytes computes the cost of a full linear page table")
def test_linear_bytes(sub):
    linear_table_bytes = has(sub, "linear_table_bytes")
    # 2**32 / 4096 = 2**20 entries * 4 bytes = 4 MiB.
    equal(linear_table_bytes(32, 4096, 4), 4 * 1024 * 1024, label="32-bit, 4 KiB, 4-byte entries")
    equal(linear_table_bytes(32, 4096), 4 * 1024 * 1024, label="default pte_size is 4")
    # 2**48 / 4096 = 2**36 entries * 8 bytes = 2**39 bytes = 512 GiB.
    equal(linear_table_bytes(48, 4096, 8), 2 ** 39, label="48-bit, 4 KiB, 8-byte entries")
    # 2**16 / 256 = 256 entries * 2 bytes = 512.
    equal(linear_table_bytes(16, 256, 2), 512, label="16-bit, 256-byte pages, 2-byte entries")


@check("two_level_table_bytes counts the directory plus the tables that exist")
def test_two_level_bytes(sub):
    map_page, PTE = has(sub, "map_page"), has(sub, "PTE")
    two_level_table_bytes = has(sub, "two_level_table_bytes")
    directory = [None] * 1024
    # Empty: 1024 directory entries * 4 bytes = 4096.
    equal(two_level_table_bytes(directory, 1024, 4), 4096, label="empty directory")
    map_page(directory, 0x403, PTE(1), 1024)
    # One table: (1024 + 1024) * 4 = 8192.
    equal(two_level_table_bytes(directory, 1024, 4), 8192, label="one second-level table")
    map_page(directory, 0x404, PTE(2), 1024)   # same table
    equal(two_level_table_bytes(directory, 1024, 4), 8192, label="two pages in the same table")
    map_page(directory, 0x1000, PTE(3), 1024)  # vpn 4096: directory slot 4
    # Two tables: (1024 + 2 * 1024) * 4 = 12288.
    equal(two_level_table_bytes(directory, 1024, 4), 12288, label="two second-level tables")
    # With 8-byte entries and a tiny directory: (4 + 1 * 8) * 8 = 96.
    small = [None] * 4
    map_page(small, 5, PTE(1), 8)
    equal(two_level_table_bytes(small, 8, 8), 96, label="4-slot directory, 8-entry table, 8-byte entries")
