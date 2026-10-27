---
title: The Python you need for this course
slug: 01-python-you-need
part: "Part 0 — Getting started"
summary: Learn the small slice of Python this course uses, and how the editor, Run, and Check work, by writing ten tiny functions.
minutes: 45
gpu: false
objectives:
  - Write functions that use integer division, remainder, strings, lists, and dicts.
  - Define a class with `__init__`, and raise and catch an exception.
  - Slice `bytes`, change a `bytearray` in place, and read a `dataclass`.
  - Use the editor, the Run button, the Check button, hints, and the solution.
exercise: 01-python-you-need
---

# The Python you need for this course

An operating system is a program. It is a large and careful one, but it is made of the same pieces as any other program: variables, functions, loops, and data. To understand it, you will build small working models of its parts. Those models are written in Python.

This lesson teaches the part of Python you need, and nothing more. You will not learn all of Python. You will learn the dozen ideas that the other twenty-five lessons use over and over. If you have never programmed, this lesson is enough to start. If you have, skim it, run the exercise, and move on.

You will also learn how this course works: where you type, what the buttons do, and what to do when a check fails. Every lesson has the same shape, so it pays to learn the shape once.

## What you already know

You need no operating systems knowledge for this lesson. You do need:

- A browser. Everything runs in the page, and you install nothing.
- Curiosity. When a line of code surprises you, change it and run it again.
- Patience with small mistakes. Every programmer sees a red error message many times a day.

## How this course works

Each lesson is a page you read on the left, with an editor on the right. The page explains an idea in plain words and shows a worked example. The editor holds a file called the *starter*, which has a set of functions with the bodies left empty. Your job is to fill them in.

Four buttons and panels matter:

- **Run** runs the bottom of your file, the part that starts with `if __name__ == "__main__":`. Use it to print things and look at them. Each starter prints a small example. Until you fill in the functions, Run shows a message that says you have not filled them in yet.
- **Check** runs a set of checks against your functions. Each check has a one-line description and passes or fails. A failing check tells you what it expected and what it got.
- **Hints** reveal one at a time, from the gentlest to the most specific. Open one only when you are stuck.
- **Solution** shows a reference answer. Try first. Reading a finished answer teaches far less than fighting with your own.

Work in small steps. Fill in one function, click Check, and watch a check turn green. The first checks in every lesson pass as soon as you get one function right, so you see progress early.

> [!TIP]
> When a check fails, read its message from the top. It names the call it tried, the value it expected, and the value your code returned. Most bugs are visible in that one line.

## Numbers and arithmetic

Python writes numbers the way you expect. It has two kinds you will use: *integers* (whole numbers such as `7` and `-3`) and *floats* (numbers with a decimal point such as `2.5`). An operating system counts things: bytes, pages, time ticks. Almost everything in this course is an integer.

Two operators matter more than the rest:

- `//` is *integer division*. It divides and throws away the fraction. `17 // 5` is `3`.
- `%` is the *remainder*, also called *modulo*. It gives what is left over. `17 % 5` is `2`.

They are a pair. `17 = 3 * 5 + 2`. The rest of the course leans on this pair, because "which page does byte 9000 fall in?" is division, and "where inside the page?" is the remainder.

```python
print(17 // 5)      # 3
print(17 % 5)       # 2
print(divmod(17, 5))  # (3, 2), both answers at once
print(7 / 2)        # 3.5, plain "/" always gives a float
print(2 ** 10)      # 1024, the power operator
```

A *bool* is either `True` or `False`. A comparison such as `n % 2 == 0` produces one. Mind the doubled `==`: one `=` stores a value, and two `==` ask whether two values are equal.

> [!WARNING]
> `/` and `//` differ. `7 / 2` is `3.5` and `7 // 2` is `3`. In this course, use `//` whenever you want a whole number, such as a page number or a count of bytes.

## Names, functions, and decisions

A *variable* is a name for a value. You create one by assigning it.

```python
seconds = 125
minutes = seconds // 60     # 2
```

A *function* is a named recipe. It takes inputs, called *parameters*, and hands back a result with `return`. You define one with `def`, and the indented lines under it are its body. Indentation is how Python knows where a body ends.

```python
def double(n):
    """Return n times two."""
    return n * 2

print(double(21))   # 42
```

The text in triple quotes is a *docstring*. It says what the function promises. Every function in this course's starter files has one, with a tiny example. Read it first: it is the contract your code must meet.

A function that has not been written yet holds `raise NotImplementedError`. That line stops the program with a message. You delete it and write the real body.

To decide between two paths, use `if`, `elif`, and `else`:

```python
def sign(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    else:
        return "positive"
```

## Loops

A *loop* repeats a block. A `for` loop visits each item of something you can walk through. A `while` loop repeats as long as a condition holds.

```python
total = 0
for n in [1, 2, 3, 4]:
    total += n          # same as: total = total + n
print(total)            # 10

count = 5
while count > 0:
    count -= 1          # must change, or the loop never ends
```

`range(3)` produces `0, 1, 2`. `range(2, 5)` produces `2, 3, 4`. The end is never included.

> [!WARNING]
> A `while` loop whose condition never becomes false runs forever. If your Run or Check hangs and then reports a time limit, look for a loop that forgets to change its variable.

## Strings

A *string* is text. You write it in quotes: `"cat"`. Strings have useful methods, which are functions attached to a value with a dot.

```python
text = "The cat The dog"
text.lower()        # "the cat the dog"
text.split()        # ["The", "cat", "The", "dog"]
"".join(["a", "b"]) # "ab"
str(10)             # "10"
```

`split()` with no arguments cuts a string at every run of spaces. `"".join(parts)` glues a list of strings back together with nothing between them. You can also index a string: `"cat"[0]` is `"c"`.

## Lists and tuples

A *list* is an ordered collection you can change. Write it in square brackets. Indexes start at `0`, and `-1` means the last item.

```python
items = [10, 20, 30]
items.append(40)      # [10, 20, 30, 40]
items[0]              # 10
items[-1]             # 40
items.pop()           # removes and returns 40
len(items)            # 3
items[:2]             # [10, 20], a *slice*: from the start up to, not including, index 2
items[1:]             # [20, 30]
```

A *tuple* is a list that you cannot change, written with round brackets: `(2, 5)`. Functions use tuples to return several values at once. `minutes, seconds = divmod(125, 60)` unpacks a pair into two names.

The built-in `reversed(...)` walks a list backwards. A common shape is to start with `result = []` and call `result.append(...)` inside a loop.

## Dictionaries

A *dict* maps keys to values, like a phone book maps names to numbers. Write it in curly brackets.

```python
ages = {"ana": 31, "bo": 27}
ages["ana"]              # 31
ages["cy"] = 40          # add a key
ages.get("dee", 0)       # 0, a default when the key is missing
"bo" in ages             # True
```

Looking up a missing key with `ages["dee"]` raises `KeyError`. The method `.get(key, default)` avoids that. Counting is the classic dict job, and you will do it in the exercise:

```python
counts = {}
for word in ["a", "b", "a"]:
    counts[word] = counts.get(word, 0) + 1
# {"a": 2, "b": 1}
```

An operating system is full of tables: process tables, page tables, file descriptor tables. Almost all of them become a dict or a list in this course.

## Classes

A *class* bundles data with the functions that work on it. An *object* is one instance of a class. Operating systems are made of such bundles: a process, a page table, a disk. You write a class with `class`, and its setup function is named `__init__`.

```python
class Counter:
    def __init__(self):
        self.value = 0          # data that belongs to this object

    def bump(self):
        self.value += 1         # a method: a function that uses self

c = Counter()
c.bump()
c.bump()
print(c.value)                  # 2
```

`self` is the object the method was called on. Python passes it for you: `c.bump()` runs `Counter.bump(c)`. Anything you want to remember between calls goes on `self`.

A method named `__len__` lets `len(obj)` work on your object. You will write one in the exercise.

> [!WARNING]
> Put the list that holds a class's items inside `__init__`, as `self.items = []`. A list created at the top of the class body is shared by every object, and one stack's pushes show up in another.

## Exceptions

An *exception* is Python's way to say "I cannot continue". When code `raise`s one, the function stops and the error travels up to whoever called it. Real operating systems report errors constantly, so you will raise and catch them often.

```python
class EmptyStackError(Exception):
    """Raised when there is nothing to pop."""

def first(items):
    if not items:
        raise EmptyStackError("no items")
    return items[0]

try:
    first([])
except EmptyStackError:
    print("caught it")
```

To make your own kind of error, write a class that inherits from `Exception`, as above. The class body can be only a docstring. A `try` block runs code that might fail, and `except` names the error to handle.

## Bytes and bytearrays

A *byte* is a whole number from 0 to 255. Memory, files, disks, and network packets are all long runs of bytes. Python has two types for them:

- `bytes` is a run of bytes you cannot change. Write it as `b"ABCD"` or `bytes([65, 66])`.
- `bytearray` is the same thing but changeable. It is how this course models memory and disks.

```python
data = b"ABCDhello"
data[0]            # 65, indexing a bytes gives an int
data[:4]           # b"ABCD", slicing gives bytes
data[4:]           # b"hello"

mem = bytearray(4)      # four zero bytes: bytearray(b"\x00\x00\x00\x00")
mem[1] = 255
mem[2:4] = b"\x07\x08"  # replace a slice
bytes(mem)              # b"\x00\xff\x07\x08"
```

The next lessons explain bytes in depth. Remember three facts: indexing gives an int from 0 to 255, slicing gives the same type you started with, and only a `bytearray` can be changed in place.

## Dataclasses

Many objects are only a bundle of named fields. A *dataclass* writes the boring `__init__` for you. Put `@dataclass` above a class and list the fields with their types.

```python
from dataclasses import dataclass

@dataclass
class Job:
    name: str
    length: int

job = Job("backup", 9)
print(job.name, job.length)    # backup 9
```

The types after the colon document what each field holds. Python does not enforce them. The starters give you dataclasses already written, and you read their fields with a dot.

## Try it on your own machine

You can run all of this outside the course. Python 3 is on most Linux and macOS machines.

1. Run `python3 --version` in a terminal. Look for `Python 3.` followed by a number. This course uses 3.12, but any recent 3 works for this lesson.
2. Run `python3` with no arguments to open an interactive prompt. Type `17 // 5` and `17 % 5` and press Enter after each. Look for `3` and `2`. Press Ctrl-D to leave.
3. Run `python3 -c "print(bytes([72, 105]))"`. Look for `b'Hi'`: two bytes that happen to be the letters H and i.
4. Run `python3 -c "print(bin(10), hex(255))"`. Look for `0b1010 0xff`. Python can write numbers in base 2 and base 16 for you. In the exercise you write `to_binary_string` yourself, so you understand what `bin` does.

## Build it step by step

Open the starter. The file defines ten functions and one class, in the order below. Fill them in from top to bottom and click Check after each one.

1. **`double(n)` and `is_even(n)`.** Each takes an int. `double` returns twice it. `is_even` returns a bool. The common mistake is writing `n % 2 = 0` with one `=`, or returning the string `"True"`. Use `==`, and return the comparison itself.
2. **`sum_of_evens(numbers)`.** It takes a list and returns an int. Start `total = 0`, loop with `for`, add each even item. The common mistake is to `return` inside the loop, which stops after the first item. Put `return total` after the loop, at the same indent as the `for`.
3. **`split_seconds(total)`.** It takes whole seconds and returns a pair `(minutes, seconds)`. Use `//` and `%`, or `divmod`. For 125 seconds, `125 // 60` is 2 and `125 % 60` is 5.
4. **`count_words(text)`.** It returns a dict from each word to its count, ignoring case. Lower-case the text first, `split()` it, and use the `counts.get(word, 0) + 1` pattern. The common mistake is forgetting to lower-case, so `"The"` and `"the"` count separately.
5. **`to_binary_string(n)`.** It takes a non-negative int and returns a string of `0` and `1`. Repeatedly take `n % 2`, then replace `n` with `n // 2`, until `n` reaches 0. For 10: the remainders are 0, 1, 0, 1, and 10 is `1010` when you read them backwards. Handle 0 first, because the loop would produce an empty string. Do not call `bin` or `format`.
6. **`Stack`.** Write `__init__`, `push`, `pop`, `peek`, and `__len__`. A stack hands back the last item you put in. Keep a list on `self`. Raise `EmptyStackError` from `pop` and `peek` when there is nothing there. The common mistake is forgetting `self.` in front of the list inside a method.
7. **`header_and_body(packet)`.** It takes `bytes` and returns a tuple of the first 4 bytes and the rest. Two slices do it.
8. **`zero_fill(buf, start, count)`.** It changes a `bytearray` in place and returns `None`. Loop over the indexes and assign `0`. The common mistake is to build a second bytearray and return it, when the check looks at the original.
9. **`total_length(jobs)` and `longest_job_name(jobs)`.** Both take a list of `Job` dataclass objects. Read `job.length` and `job.name`. For an empty list, `longest_job_name` returns `None`. On a tie, it returns the first one.

## Where this breaks

Python is forgiving, and the forgiveness hides real traps.

- **Python ints never overflow.** In real hardware, a number lives in 8, 32, or 64 bits and wraps around when it grows too large. Python grows the int instead. Lesson 03 shows you how to model wrapping by hand.
- **Slices never complain.** `b"abc"[2:100]` returns `b"c"` with no error. Real memory systems do complain when you reach past the end. When a function must reject a range, check the range yourself.
- **Mutable values are shared.** If two names point to one list or `bytearray`, a change through one name shows through the other. `list(x)` or `x[:]` makes a copy. Bugs from this appear in every lesson that saves and restores state.
- **Python is slow.** Real operating systems are written in C and assembly because they must be fast and must control memory exactly. Your models show the logic. They do not match the speed.

## Further reading

- [The Python Tutorial](https://docs.python.org/3/tutorial/) covers everything here, with more detail and more examples.
- [Built-in types: bytes and bytearray](https://docs.python.org/3/library/stdtypes.html#bytes-objects) lists every operation on the two byte types.
- [The dataclasses module](https://docs.python.org/3/library/dataclasses.html) explains what `@dataclass` writes for you.
- [Automate the Boring Stuff with Python](https://automatetheboringstuff.com/) is a free book for readers who have never programmed.

## The exercise

You fill in ten small functions and one class in a single file. Each one does a small job: arithmetic, counting words, writing a number in binary, a stack that raises an error, slicing bytes, changing a `bytearray`, and reading a list of `Job` objects.

The ten checks run in the order above: `double` and `is_even`, `sum_of_evens`, `split_seconds`, `count_words`, `to_binary_string`, `Stack` (twice: order and errors), `header_and_body`, `zero_fill`, and `total_length` with `longest_job_name`. Click Run to print an example of each function. Click Check as often as you like.
