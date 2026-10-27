"""Paging: split addresses, walk page tables, and count what the tables cost.

Reference solution.
"""

from dataclasses import dataclass


class PageFault(Exception):
    """Raised when a translation cannot proceed."""


@dataclass
class PTE:
    """A page-table entry: which frame, and what the program may do."""

    frame: int
    valid: bool = True
    read: bool = True
    write: bool = True


def split_address(vaddr, page_size):
    """Split a virtual address into (page number, offset)."""
    offset_bits = page_size.bit_length() - 1  # 4096 -> 12
    return vaddr >> offset_bits, vaddr & (page_size - 1)


def _check_entry(entry, write):
    """Raise PageFault unless `entry` allows this kind of access."""
    if entry is None or not entry.valid:
        raise PageFault("page is not mapped")
    if not entry.read:
        raise PageFault("page is not readable")
    if write and not entry.write:
        raise PageFault("page is not writable")


def translate(page_table, vaddr, page_size=4096, write=False):
    """Translate `vaddr` through a linear page table."""
    vpn, offset = split_address(vaddr, page_size)
    if vpn >= len(page_table):
        raise PageFault(f"vpn {vpn} is past the end of the table")
    entry = page_table[vpn]
    _check_entry(entry, write)
    return entry.frame * page_size + offset


def split_two_level(vaddr, page_size, entries_per_table):
    """Split an address into (directory index, table index, offset)."""
    vpn, offset = split_address(vaddr, page_size)
    return vpn // entries_per_table, vpn % entries_per_table, offset


def map_page(directory, vpn, pte, entries_per_table):
    """Store `pte` for `vpn`, creating the second-level table on demand."""
    d, t = vpn // entries_per_table, vpn % entries_per_table
    if directory[d] is None:
        directory[d] = [None] * entries_per_table
    directory[d][t] = pte


def translate_two_level(directory, vaddr, page_size, entries_per_table, write=False):
    """Translate `vaddr` through a two-level page table."""
    d, t, offset = split_two_level(vaddr, page_size, entries_per_table)
    if d >= len(directory) or directory[d] is None:
        raise PageFault(f"no second-level table for directory slot {d}")
    entry = directory[d][t]
    _check_entry(entry, write)
    return entry.frame * page_size + offset


def linear_table_bytes(address_bits, page_size, pte_size=4):
    """Bytes a linear page table needs to cover the whole address space."""
    pages = (1 << address_bits) // page_size
    return pages * pte_size


def two_level_table_bytes(directory, entries_per_table, pte_size=4):
    """Bytes a two-level table uses: the directory plus each allocated table."""
    tables = sum(1 for slot in directory if slot is not None)
    return (len(directory) + tables * entries_per_table) * pte_size


if __name__ == "__main__":
    PAGE = 4096
    table = [PTE(5), PTE(9, write=False), None, PTE(2, valid=False)]
    for vaddr, write in [(0x0123, False), (0x1FFF, False), (0x1000, True), (0x2000, False)]:
        try:
            paddr = translate(table, vaddr, PAGE, write=write)
            print(f"vaddr {vaddr:#06x} -> paddr {paddr:#07x}")
        except PageFault:
            kind = "write" if write else "read"
            print(f"vaddr {vaddr:#06x} ({kind}) -> PageFault")

    directory = [None] * 1024
    map_page(directory, 0x403, PTE(7), 1024)
    print("split 0x00403ABC:", split_two_level(0x00403ABC, PAGE, 1024))
    print("paddr:", hex(translate_two_level(directory, 0x00403ABC, PAGE, 1024)))
    print("linear table, 32-bit:", linear_table_bytes(32, PAGE), "bytes")
    print("two-level table now:", two_level_table_bytes(directory, 1024), "bytes")
