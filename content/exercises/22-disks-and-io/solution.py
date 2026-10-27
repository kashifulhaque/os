"""Disk access time and disk schedulers."""

from __future__ import annotations


# --- Part 1: how long does one disk access take? ---------------------------


def rotational_latency_ms(rpm: float) -> float:
    """Average rotational latency in milliseconds: half of one full rotation.

    One rotation takes 60000 / rpm ms. On average the sector you want is
    half a rotation away.

    >>> round(rotational_latency_ms(7200), 2)
    4.17
    """
    full_rotation_ms = 60_000.0 / rpm
    return full_rotation_ms / 2


def transfer_time_ms(nbytes: int, mb_per_s: float) -> float:
    """Milliseconds to move `nbytes` at `mb_per_s` megabytes per second.

    A megabyte here is 1,000,000 bytes, the way disk makers count.

    >>> transfer_time_ms(1_000_000, 100)
    10.0
    """
    bytes_per_ms = mb_per_s * 1_000_000 / 1000
    return nbytes / bytes_per_ms


def access_time_ms(seek_ms: float, rpm: float, nbytes: int, mb_per_s: float) -> float:
    """Average time for one access: seek + rotational latency + transfer.

    >>> round(access_time_ms(4.0, 7200, 4096, 125), 3)
    8.199
    """
    return seek_ms + rotational_latency_ms(rpm) + transfer_time_ms(nbytes, mb_per_s)


def io_rate_mb_s(nbytes: int, time_ms: float) -> float:
    """Achieved rate in megabytes per second (1 MB = 1,000,000 bytes).

    >>> io_rate_mb_s(1_000_000, 10)
    100.0
    """
    return (nbytes / 1_000_000) / (time_ms / 1000)


# --- Part 2: disk schedulers ------------------------------------------------


def total_movement(start: int, path: list[int]) -> int:
    """Total tracks the head crosses, starting at `start` and visiting `path` in order.

    >>> total_movement(10, [15, 5])
    15
    """
    moved = 0
    here = start
    for track in path:
        moved += abs(track - here)
        here = track
    return moved


def fcfs(start: int, requests: list[int]) -> list[int]:
    """First come, first served: visit the requests in arrival order.

    >>> fcfs(50, [90, 10, 60])
    [90, 10, 60]
    """
    return list(requests)


def sstf(start: int, requests: list[int]) -> list[int]:
    """Shortest seek time first: always go to the closest pending track.

    Ties in distance go to the lower track number. Duplicate requests are
    served one at a time.

    >>> sstf(50, [40, 60, 90])
    [40, 60, 90]
    """
    pending = list(requests)
    here = start
    order = []
    while pending:
        # Key (distance, track): the tuple compare breaks ties toward the lower track.
        best = min(pending, key=lambda t: (abs(t - here), t))
        pending.remove(best)
        order.append(best)
        here = best
    return order


def scan(start: int, requests: list[int], direction: str, max_track: int) -> list[int]:
    """The elevator: sweep one way, turn around at the disk edge, sweep back.

    Returns the head path, excluding `start`. `direction` is "up" (toward
    max_track) or "down" (toward track 0). A request at `start` is served
    first, at no cost. If requests remain behind the head, the head goes on
    to the edge (max_track going up, 0 going down) unless it is already
    there, adds that edge to the path, then serves the rest in the opposite
    direction. If nothing remains behind, the head stops at its last request
    and never visits the edge.

    >>> scan(50, [60, 40, 90], "up", 99)
    [60, 90, 99, 40]
    """
    if direction == "up":
        ahead = sorted(t for t in requests if t >= start)
        behind = sorted((t for t in requests if t < start), reverse=True)
        edge = max_track
    elif direction == "down":
        ahead = sorted((t for t in requests if t <= start), reverse=True)
        behind = sorted(t for t in requests if t > start)
        edge = 0
    else:
        raise ValueError("direction must be 'up' or 'down'")
    path = list(ahead)
    if behind:
        last = path[-1] if path else start
        if last != edge:
            path.append(edge)
        path.extend(behind)
    return path


def c_look(start: int, requests: list[int]) -> list[int]:
    """Circular LOOK: sweep up to the highest request, jump to the lowest, sweep up.

    Returns the visit order. A request at `start` is served first. The jump
    from the highest request to the lowest remaining one is a real seek and
    counts in total_movement.

    >>> c_look(50, [60, 40, 90, 10])
    [60, 90, 10, 40]
    """
    ahead = sorted(t for t in requests if t >= start)
    wrapped = sorted(t for t in requests if t < start)
    return ahead + wrapped


if __name__ == "__main__":
    print("7200 RPM, 4 ms seek, 4 KiB at 125 MB/s:")
    print(f"  rotational latency: {rotational_latency_ms(7200):.2f} ms")
    t = access_time_ms(4.0, 7200, 4096, 125)
    print(f"  random 4 KiB access: {t:.2f} ms -> {io_rate_mb_s(4096, t):.2f} MB/s")
    queue = [98, 183, 37, 122, 14, 124, 65, 67]
    print(f"head at 53, queue {queue}, tracks 0..199")
    paths = {
        "FCFS": fcfs(53, queue),
        "SSTF": sstf(53, queue),
        "SCAN up": scan(53, queue, "up", 199),
        "C-LOOK": c_look(53, queue),
    }
    for name, path in paths.items():
        print(f"  {name:8} moves {total_movement(53, path):4}  path {path}")
