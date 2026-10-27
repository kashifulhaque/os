"""Paging: split addresses, walk page tables, and count what the tables cost.

Fill in the functions in order. A virtual address is an integer. A page table
is a list indexed by virtual page number (vpn). Each slot holds a `PTE` or
`None`. A two-level table is a *directory* (a list) whose slots hold either
`None` or a second-level list of `PTE`s.
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
    """Split a virtual address into (page number, offset).

    `page_size` is a power of two.

    Example: split_address(0x3ABC, 4096) == (3, 0xABC)
    """
    raise NotImplementedError("split_address")


def translate(page_table, vaddr, page_size=4096, write=False):
    """Translate `vaddr` through a linear page table.

    Raise PageFault when the vpn is past the end of the table, the slot is
    None, the entry is not valid, the entry forbids reading, or `write` is
    True and the entry forbids writing. Otherwise return
    entry.frame * page_size + offset.

    Example: with page_table = [PTE(5)], translate(page_table, 0x123) == 0x5123
    """
    raise NotImplementedError("translate")


def split_two_level(vaddr, page_size, entries_per_table):
    """Split an address into (directory index, table index, offset).

    Example (4 KiB pages, 1024 entries per table):
    split_two_level(0x00403ABC, 4096, 1024) == (1, 3, 0xABC)
    """
    raise NotImplementedError("split_two_level")


def map_page(directory, vpn, pte, entries_per_table):
    """Store `pte` for page number `vpn`, creating the second-level table if needed.

    A new second-level table is a list of `entries_per_table` Nones.
    The directory is a list that already has its final length.
    """
    raise NotImplementedError("map_page")


def translate_two_level(directory, vaddr, page_size, entries_per_table, write=False):
    """Translate `vaddr` through a two-level page table.

    Raise PageFault for a directory index past the end, a directory slot that
    is None, or any of the entry problems `translate` checks. Otherwise return
    the physical address.
    """
    raise NotImplementedError("translate_two_level")


def linear_table_bytes(address_bits, page_size, pte_size=4):
    """Bytes a linear page table needs to cover the whole address space.

    Example: 32-bit addresses, 4 KiB pages, 4-byte entries -> 4 MiB.
    """
    raise NotImplementedError("linear_table_bytes")


def two_level_table_bytes(directory, entries_per_table, pte_size=4):
    """Bytes a two-level table uses right now.

    That is the directory (one entry per slot) plus one full table of
    `entries_per_table` entries for every directory slot that is not None.
    """
    raise NotImplementedError("two_level_table_bytes")


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
