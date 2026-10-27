"""Warm-up exercise: the Python this course uses, in ten small functions.

Click Check to see which functions pass. Fill them in one at a time.
"""

from dataclasses import dataclass


class EmptyStackError(Exception):
    """Raised when you pop or peek at a stack that has nothing in it."""


@dataclass
class Job:
    """A named piece of work with a length in time units."""

    name: str
    length: int


def double(n):
    """Return n times two.  double(21) -> 42"""
    raise NotImplementedError


def is_even(n):
    """Return True when n is even, False otherwise.  is_even(7) -> False"""
    raise NotImplementedError


def sum_of_evens(numbers):
    """Add up the even numbers in a list.  sum_of_evens([1, 2, 3, 4]) -> 6"""
    raise NotImplementedError


def split_seconds(total):
    """Split a number of seconds into (minutes, seconds).

    split_seconds(125) -> (2, 5)
    """
    raise NotImplementedError


def count_words(text):
    """Count how often each word appears, ignoring case.

    count_words("the cat The dog") -> {"the": 2, "cat": 1, "dog": 1}
    """
    raise NotImplementedError


def to_binary_string(n):
    """Write a non-negative int in base 2, without using bin() or format().

    to_binary_string(10) -> "1010"
    to_binary_string(0) -> "0"
    """
    raise NotImplementedError


class Stack:
    """A last-in, first-out pile of items.

    s = Stack(); s.push(1); s.push(2); s.pop() -> 2; len(s) -> 1
    """

    def __init__(self):
        # TODO: create the list that holds the items.
        raise NotImplementedError

    def push(self, item):
        """Put item on top."""
        raise NotImplementedError

    def pop(self):
        """Remove and return the top item. Raise EmptyStackError if empty."""
        raise NotImplementedError

    def peek(self):
        """Return the top item without removing it. Raise EmptyStackError if empty."""
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError


def header_and_body(packet):
    """Split a bytes packet into its first 4 bytes and the rest.

    header_and_body(b"ABCDhello") -> (b"ABCD", b"hello")
    """
    raise NotImplementedError


def zero_fill(buf, start, count):
    """Set count bytes of a bytearray to 0, beginning at index start.

    Change buf in place and return None.
    """
    raise NotImplementedError


def total_length(jobs):
    """Return the sum of job.length over a list of Job objects."""
    raise NotImplementedError


def longest_job_name(jobs):
    """Return the name of the Job with the largest length, or None for no jobs.

    On a tie, return the first one in the list.
    """
    raise NotImplementedError


if __name__ == "__main__":
    print("double(21)            =", double(21))
    print("is_even(7)            =", is_even(7))
    print("sum_of_evens          =", sum_of_evens([1, 2, 3, 4, 10]))
    print("split_seconds(125)    =", split_seconds(125))
    print("count_words           =", count_words("the cat The dog"))
    print("to_binary_string(10)  =", to_binary_string(10))
    s = Stack()
    s.push("a")
    s.push("b")
    print("stack pop             =", s.pop(), "then", len(s), "item left")
    print("header_and_body       =", header_and_body(b"ABCDhello"))
    buf = bytearray(b"abcdef")
    zero_fill(buf, 2, 3)
    print("zero_fill             =", bytes(buf))
    jobs = [Job("a", 4), Job("b", 9), Job("c", 2)]
    print("total / longest       =", total_length(jobs), longest_job_name(jobs))
