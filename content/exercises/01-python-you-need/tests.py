"""Checks for the Python warm-up exercise."""

from oscheck import check, equal, fail, has


@check("double and is_even work on small ints")
def test_basic(sub):
    double = has(sub, "double")
    is_even = has(sub, "is_even")
    equal(double(21), 42, label="double(21)")
    equal(double(0), 0, label="double(0)")
    equal(double(-3), -6, label="double(-3)")
    equal(is_even(10), True, label="is_even(10)")
    equal(is_even(7), False, label="is_even(7)")
    equal(is_even(0), True, label="is_even(0)")


@check("sum_of_evens adds only the even numbers")
def test_sum_evens(sub):
    sum_of_evens = has(sub, "sum_of_evens")
    # 2 + 4 + 10 = 16
    equal(sum_of_evens([1, 2, 3, 4, 10]), 16, label="sum_of_evens([1, 2, 3, 4, 10])")
    equal(sum_of_evens([]), 0, label="sum_of_evens([])")
    equal(sum_of_evens([7, 9]), 0, label="sum_of_evens([7, 9])")


@check("split_seconds uses integer division and remainder")
def test_split_seconds(sub):
    split_seconds = has(sub, "split_seconds")
    equal(split_seconds(125), (2, 5), label="split_seconds(125)")  # 125 = 2*60 + 5
    equal(split_seconds(59), (0, 59), label="split_seconds(59)")
    equal(split_seconds(3600), (60, 0), label="split_seconds(3600)")


@check("count_words counts words and ignores case")
def test_count_words(sub):
    count_words = has(sub, "count_words")
    equal(
        count_words("the cat The dog"),
        {"the": 2, "cat": 1, "dog": 1},
        label="count_words('the cat The dog')",
    )
    equal(count_words(""), {}, label="count_words('')")
    equal(count_words("a a a"), {"a": 3}, label="count_words('a a a')")


@check("to_binary_string writes numbers in base 2")
def test_binary(sub):
    to_binary_string = has(sub, "to_binary_string")
    equal(to_binary_string(0), "0", label="to_binary_string(0)")
    equal(to_binary_string(1), "1", label="to_binary_string(1)")
    equal(to_binary_string(10), "1010", label="to_binary_string(10)")  # 8 + 2
    equal(to_binary_string(255), "11111111", label="to_binary_string(255)")
    equal(to_binary_string(256), "100000000", label="to_binary_string(256)")


@check("Stack pushes and pops in last-in, first-out order")
def test_stack(sub):
    Stack = has(sub, "Stack")
    s = Stack()
    equal(len(s), 0, label="len of a new stack")
    s.push(1)
    s.push(2)
    s.push(3)
    equal(len(s), 3, label="len after three pushes")
    equal(s.pop(), 3, label="first pop")
    equal(s.peek(), 2, label="peek after one pop")
    equal(len(s), 2, label="peek must not remove the item; len")
    equal(s.pop(), 2, label="second pop")
    equal(s.pop(), 1, label="third pop")
    t = Stack()
    t.push("x")
    equal(len(s), 0, label="two stacks must not share their items; len of the first")


@check("Stack raises EmptyStackError when empty")
def test_stack_empty(sub):
    Stack = has(sub, "Stack")
    EmptyStackError = has(sub, "EmptyStackError")
    for name in ("pop", "peek"):
        s = Stack()
        try:
            getattr(s, name)()
        except EmptyStackError:
            continue
        except Exception as exc:  # noqa: BLE001
            fail(f"{name}() on an empty stack raised {type(exc).__name__}, expected EmptyStackError")
        fail(f"{name}() on an empty stack returned instead of raising EmptyStackError")


@check("header_and_body slices a bytes packet")
def test_header(sub):
    header_and_body = has(sub, "header_and_body")
    equal(header_and_body(b"ABCDhello"), (b"ABCD", b"hello"), label="header_and_body(b'ABCDhello')")
    equal(header_and_body(b"ABCD"), (b"ABCD", b""), label="header_and_body(b'ABCD')")
    got = header_and_body(bytes([1, 2, 3, 4, 5]))
    equal(got, (bytes([1, 2, 3, 4]), bytes([5])), label="header_and_body of raw bytes")


@check("zero_fill changes a bytearray in place")
def test_zero_fill(sub):
    zero_fill = has(sub, "zero_fill")
    buf = bytearray(b"abcdef")
    result = zero_fill(buf, 2, 3)
    equal(bytes(buf), b"ab\x00\x00\x00f", label="buffer after zero_fill(buf, 2, 3)")
    equal(result, None, label="zero_fill should return None")
    zero_fill(buf, 0, 0)
    equal(bytes(buf), b"ab\x00\x00\x00f", label="zero_fill with count 0 changes nothing")


@check("total_length and longest_job_name read a list of Jobs")
def test_jobs(sub):
    Job = has(sub, "Job")
    total_length = has(sub, "total_length")
    longest_job_name = has(sub, "longest_job_name")
    jobs = [Job("a", 4), Job("b", 9), Job("c", 2)]
    equal(total_length(jobs), 15, label="total_length")  # 4 + 9 + 2
    equal(total_length([]), 0, label="total_length([])")
    equal(longest_job_name(jobs), "b", label="longest_job_name")
    equal(longest_job_name([]), None, label="longest_job_name([])")
    tie = [Job("x", 5), Job("y", 5)]
    equal(longest_job_name(tie), "x", label="longest_job_name on a tie keeps the first")
