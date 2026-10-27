"""Page replacement: FIFO, LRU, Clock, and OPT, plus Belady's anomaly.

Reference solution. A reference string is a list of page numbers. A reference
is a fault exactly when its page is not resident. Cold misses count.
"""

from collections import OrderedDict, deque


def fifo_faults(refs, frames):
    """Count faults when the page that arrived first is evicted first."""
    queue = deque()  # oldest arrival on the left
    resident = set()
    faults = 0
    for page in refs:
        if page in resident:
            continue  # a hit does not change FIFO order
        faults += 1
        if len(queue) == frames:
            resident.discard(queue.popleft())
        queue.append(page)
        resident.add(page)
    return faults


def lru_faults(refs, frames):
    """Count faults when the least recently used page is evicted."""
    resident = OrderedDict()  # least recently used first
    faults = 0
    for page in refs:
        if page in resident:
            resident.move_to_end(page)
            continue
        faults += 1
        if len(resident) == frames:
            resident.popitem(last=False)
        resident[page] = True
    return faults


def clock_faults(refs, frames):
    """Count faults under the Clock (second chance) policy with one reference bit."""
    pages = [None] * frames
    bits = [0] * frames
    hand = 0
    faults = 0
    for page in refs:
        if page in pages:
            bits[pages.index(page)] = 1  # a hit sets the reference bit
            continue
        faults += 1
        # Skip over pages that were used since the hand last passed, clearing them.
        while pages[hand] is not None and bits[hand] == 1:
            bits[hand] = 0
            hand = (hand + 1) % frames
        pages[hand] = page
        bits[hand] = 1  # a freshly loaded page counts as used
        hand = (hand + 1) % frames
    return faults


def opt_faults(refs, frames):
    """Count faults for the optimal policy: evict the page used farthest ahead."""
    resident = set()
    faults = 0
    for i, page in enumerate(refs):
        if page in resident:
            continue
        faults += 1
        if len(resident) == frames:
            def next_use(p):
                try:
                    return refs.index(p, i + 1)
                except ValueError:
                    return len(refs)  # never used again: the best victim
            resident.remove(max(resident, key=next_use))
        resident.add(page)
    return faults


def compare_policies(refs, frames):
    """Return {"FIFO": n, "LRU": n, "Clock": n, "OPT": n} for one reference string."""
    return {
        "FIFO": fifo_faults(refs, frames),
        "LRU": lru_faults(refs, frames),
        "Clock": clock_faults(refs, frames),
        "OPT": opt_faults(refs, frames),
    }


def find_belady(refs, max_frames, policy=fifo_faults):
    """Find the first frame count where one more frame causes more faults.

    Returns (f, faults_with_f, faults_with_f_plus_1), or None if adding frames
    never hurts for f from 1 up to max_frames - 1.
    """
    for f in range(1, max_frames):
        small = policy(refs, f)
        large = policy(refs, f + 1)
        if large > small:
            return (f, small, large)
    return None


if __name__ == "__main__":
    classic = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    for frames in (3, 4):
        print(f"{frames} frames:", compare_policies(classic, frames))
    print("Belady:", find_belady(classic, 6))
