"""Page replacement: FIFO, LRU, Clock, and OPT, plus Belady's anomaly.

A reference string is a list of page numbers, such as [1, 2, 3, 1]. Memory has
`frames` slots, and starts empty.

A reference is a *fault* exactly when its page is not in memory at that moment.
The first touch of every page is a fault (a cold miss), and so is every load
into a still-empty frame. Each function returns the number of faults.
"""


def fifo_faults(refs, frames):
    """Count faults when the page that arrived first is evicted first.

    Example: fifo_faults([1, 2, 3, 1], 3) == 3
    """
    raise NotImplementedError("fifo_faults")


def lru_faults(refs, frames):
    """Count faults when the least recently used page is evicted.

    Example: lru_faults([1, 2, 1, 3, 2], 2) == 4
    """
    raise NotImplementedError("lru_faults")


def clock_faults(refs, frames):
    """Count faults under the Clock (second chance) policy with one reference bit.

    Rules:
    * Memory is a ring of `frames` slots, each holding a page and a reference
      bit. A hand points at one slot and starts at slot 0.
    * A hit sets that page's reference bit to 1. The hand does not move.
    * On a fault, look at the slot under the hand. If it is empty, or its bit
      is 0, load the page there. If its bit is 1, clear it to 0 and move the
      hand to the next slot. Repeat until a page is loaded.
    * A newly loaded page gets reference bit 1, and the hand then moves to the
      slot after it.
    """
    raise NotImplementedError("clock_faults")


def opt_faults(refs, frames):
    """Count faults for the optimal policy (Belady's OPT).

    On a fault with memory full, evict the resident page whose next use is
    farthest in the future. A page that is never used again is the best victim.
    """
    raise NotImplementedError("opt_faults")


def compare_policies(refs, frames):
    """Return {"FIFO": n, "LRU": n, "Clock": n, "OPT": n} for one reference string."""
    raise NotImplementedError("compare_policies")


def find_belady(refs, max_frames, policy=fifo_faults):
    """Find the first frame count where one more frame causes more faults.

    Try f = 1, 2, ..., max_frames - 1. Return (f, faults_with_f,
    faults_with_f_plus_1) for the first f where the second number is larger,
    or None if no f shows the anomaly.
    """
    raise NotImplementedError("find_belady")


if __name__ == "__main__":
    classic = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    for frames in (3, 4):
        print(f"{frames} frames:", compare_policies(classic, frames))
    print("Belady:", find_belady(classic, 6))
