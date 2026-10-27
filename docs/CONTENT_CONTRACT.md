# Content contract

Every lesson in this course is two things on disk: one Markdown file that the
reader reads, and one exercise directory that the reader's code is checked
against. This document is the exact contract both must satisfy. The loader in
`backend/app/curriculum.py` and the harness in `backend/app/runner/harness.py`
depend on it. The lesson list is in `docs/CURRICULUM.md`.

## Audience

Readers have no background in operating systems or computer architecture.
They may have written a little code in some language, but assume nothing
beyond what Part 0 teaches: Python functions, lists, dicts, classes, `bytes`,
and the idea of a loop. They have never heard of a register, a page table, a
file descriptor, or a mutex. They learn by building. Write for them:

- Start with the intuition in plain words. Before any detail, say what the
  mechanism does and why it exists, in one or two sentences a first-year
  student could repeat to a friend. Use an everyday analogy when one fits: a
  restaurant kitchen for scheduling, a hotel's room numbers for address
  translation, a library catalogue for inodes.
- Define every term the first time it appears, including ones that feel basic,
  such as "process", "kernel", "address", "byte", "interrupt", or "thread".
  Prefer an ordinary word to jargon when both mean the same thing, and when
  you must use jargon, say it in plain words first.
- Show, then tell. Each concept gets a small concrete example worked by hand
  with real numbers: three jobs on a timeline, a 16-bit address split into
  page and offset, a four-frame memory under a reference string. Show every
  intermediate value, so the reader can check their code against it.
- Draw pictures in text. Use fenced `text` blocks for ASCII diagrams of memory
  layouts, timelines (Gantt charts), queues, page tables, and on-disk layouts.
  Every diagram is introduced by a sentence.
- Connect to the real system. After a mechanism is clear, show where it lives
  in Linux: a command to run (`ps`, `top`, `cat /proc/self/maps`, `strace`,
  `ls -i`), a system call's name, or a real number (a 4 KiB page, a 4 ms
  timer tick). Readers should finish feeling they could poke at their own
  machine.
- Keep the conditions honest. When a claim depends on hardware or on the
  operating system, say which. When Linux does something differently from the
  textbook model, say so.
- Connect ideas to code. The reader should finish every section knowing which
  Python they will write.

Every claim on the page must be correct. Simpler wording must never change
what a result says.

## Prose style

Follow the Google developer documentation style guide:

- Address the reader as "you". Use active voice and present tense.
- One idea per sentence. Short sentences and short paragraphs.
- Sentence case for every heading. Start task headings with a bare infinitive.
- Serial commas. Em dashes with no surrounding spaces.
- Code, filenames, commands, and identifiers in code font. No `simply`,
  `just`, `easily`, `obviously`, `note that`, `e.g.`, `i.e.`, `etc.`
- Don't write timelessly-rotting words: `currently`, `now`, `new`, `latest`,
  `recently`, `state of the art`.
- Introduce every list, table, and code block with a complete sentence.

## Lesson file

Path: `content/lessons/NN-slug.md`, where `NN` is the two-digit order prefix and
`slug` matches the `slug` field.

The file starts with YAML front matter:

```yaml
---
title: Paging
slug: 14-paging
part: "Part 4 — Memory"
summary: One sentence, under 140 characters, that says what the lesson delivers.
minutes: 50
gpu: false
objectives:
  - Split a virtual address into a page number and an offset.
  - Translate an address through a linear page table and a two-level page table.
  - "Say what a page table costs: memory for the table, and an extra lookup per access."
prereqs:
  - 13-address-spaces
exercise: 14-paging
---
```

Every value that holds a colon must be wrapped in double quotes, or YAML reads
the item as a mapping rather than a string. `scripts/check_content.py` rejects
one. Every field is required except `prereqs`, which can be omitted. `gpu` is
always `false`. The `part` string must match `docs/CURRICULUM.md` exactly,
including the em dash. `minutes` is an honest reading and working estimate.

The body is Markdown with these conventions:

- One `#` heading, matching `title`, as the first line after the front matter.
- `##` for sections, `###` for subsections. Never skip a level.
- Math is rare in this course. When you need it, use KaTeX: `$inline$` and
  `$$display$$`, with each `$$` on its own line above and below the equation.
  A one-line `$$...$$` is rejected by `scripts/check_content.py`. Never put a
  literal dollar sign in prose; write "dollars" instead.
- Fenced code blocks tagged with a language (`python`, `text`, `bash`, `c`).
  Python blocks show the shape of an implementation, not a full solution to the
  exercise. Short C snippets are welcome to show what real systems code looks
  like, but the reader never has to write C.
- Tables for genuinely two-dimensional data.
- Callouts, written as a blockquote whose first line is a type marker:

  ```markdown
  > [!KEY]
  > A process is a running program plus everything the kernel tracks about it.
  ```

  | Marker | Label | Use it for |
  |---|---|---|
  | `[!KEY]` | Key idea | The one sentence to remember from a section. Two to four per lesson. |
  | `[!TIP]` | Tip | A practical shortcut or habit. At most two per lesson. |
  | `[!WARNING]` | Watch out | A trap the reader is about to fall into. At most two per lesson. |
  | `[!RECAP]` | Before you build | Three to five bullets, placed right before `## Build it step by step`. One per lesson. |

  `scripts/check_content.py` rejects any other marker, and a second recap.

Every lesson body includes, in this order:

1. An opening that says, in plain words, what problem the lesson solves and why
   it matters. Two or three short paragraphs. No heading.
2. `## What you already know` — a short list of the ideas the lesson builds on,
   each in one plain sentence. Keep it to five bullets. Lesson 01 says what
   the reader needs instead: a browser and curiosity.
3. The substance, in as many `##` sections as the material needs. Each section
   leads with intuition, then the mechanism, then a worked example with real
   numbers or a diagram.
4. `## Try it on your own machine` — two to five commands or tiny Python
   snippets the reader can run on a Linux or macOS terminal to see the idea on
   a real system, each with a sentence saying what to look for. Mark anything
   Linux-only.
5. `## Build it step by step` — a numbered walkthrough of the exercise, one
   step per function in the order the checks test them. Each step says what the
   function takes and returns, the Python it needs, and the mistake people most
   often make. It gives the shape of the code, never the full answer.
6. `## Where this breaks` — the ways the mechanism fails or costs too much in
   practice, and what real systems do about each one.
7. `## Further reading` — three to six references, each a Markdown link, with
   one sentence on what it adds. Prefer free sources: the relevant chapter of
   *Operating Systems: Three Easy Pieces* (https://pages.cs.wisc.edu/~remzi/OSTEP/,
   link the chapter PDF), Linux man pages on man7.org, MIT 6.1810 (xv6)
   materials, and classic papers. Only link URLs you are confident exist.
8. `## The exercise` — one or two paragraphs that say what the reader builds
   and what the checks verify. Name the functions by their exact identifiers.

Aim for 1800 to 3000 words of body. Short sentences and short paragraphs
matter more than the word count.

## Exercise directory

Path: `content/exercises/<id>/`, where `<id>` matches the lesson's `exercise`
field (and equals the slug). It holds exactly four files.

### `meta.json`

```json
{
  "id": "14-paging",
  "title": "Translate addresses through one- and two-level page tables",
  "brief": "Split addresses, walk page tables, and measure how much memory each table design costs.",
  "needs_gpu": false,
  "timeout": 30,
  "packages": [],
  "hints": [
    "With 4 KiB pages the offset is the low 12 bits: vaddr & 0xFFF. The page number is vaddr >> 12.",
    "An invalid entry raises PageFault before you ever look at its frame number."
  ]
}
```

`needs_gpu` is always `false`. `packages` is documentation only; the runtime is
Python 3.12 with the standard library and `numpy`. Exercises use the standard
library only. `timeout` is in seconds: 30 for most exercises, up to 60 for one
that starts real processes or threads. Give three to six hints, ordered from
gentlest to most specific.

### `starter.py`

What the reader sees when the lesson opens. It must:

- Import only from the Python standard library.
- Define every function and class the checks call, with the exact signature, a
  docstring that states the contract with a tiny example, and a body that
  raises `NotImplementedError`. Helper classes the reader is not asked to
  write (an exception type, a dataclass for a job, a provided `Disk`) are given
  in full, and repeated identically in `solution.py`.
- Carry a `if __name__ == "__main__":` block that builds a small example and
  prints something informative. The **Run** button executes this block, so it
  must work once the reader fills in the functions, and it must fail with a
  clear `NotImplementedError` before that.
- Never contain the answer, in a comment or anywhere else.

The **Run** button has the same time limit as the checks, so keep the
`__main__` block to a second or two of work.

### `solution.py`

A correct, idiomatic, well-commented reference implementation with the same
public surface as `starter.py`. It must pass every check in `tests.py`. Keep it
clean enough to read as the worked answer, because the reader can reveal it.

### `tests.py`

The checks. Import the helpers and register each check with `@check`:

```python
"""Checks for the paging exercise."""

from oscheck import check, equal, fail, has


@check("split_address separates page number and offset for 4 KiB pages")
def test_split(sub):
    split_address = has(sub, "split_address")
    equal(split_address(0x3ABC, page_size=4096), (3, 0xABC), label="split_address(0x3ABC)")


@check("translate raises PageFault for an invalid entry")
def test_fault(sub):
    translate = has(sub, "translate")
    PageFault = has(sub, "PageFault")
    try:
        translate({0: None}, 0x10, page_size=4096)
    except PageFault:
        return
    fail("translating through an invalid entry should raise PageFault")
```

The `oscheck` module is on the import path at run time. Its API:

| Name | Signature | Behaviour |
|---|---|---|
| `check` | `@check("description")` | Registers a check. The description is what the reader sees. |
| `equal` | `equal(got, want, label=None)` | Exact equality with a readable message. Use it for ints, strings, lists, tuples, dicts. |
| `almost` | `almost(got, want, tol, label=None)` | Scalar float comparison within `tol`. |
| `close` | `close(got, want, rtol=1e-5, atol=1e-8, label=None)` | Elementwise float comparison for lists of floats. |
| `fail` | `fail("message")` | Fails the check with that message. |
| `has` | `has(sub, "name")` | Returns the reader's function or class, or fails naming what is missing. |
| `timed` | `with timed("label"):` | Records elapsed seconds, reported to the reader. |

Rules for checks:

- Each check receives `sub`, the reader's module, as its only argument.
- Seed every random number generator: `random.Random(0)`. A check that passes
  intermittently is a bug. Real threads and processes must be checked on
  outcomes that hold under every interleaving, never on timing.
- Write six to ten checks per exercise, ordered from the smallest piece to the
  whole. The first check must pass as soon as the reader gets one function
  right, so the pane shows progress early.
- Check behaviour, not implementation. Compare against hand-computed answers
  (put the arithmetic in a comment) and against independent properties.
- Never import `solution` from `tests.py`.
- The whole suite runs the reference solution in under 5 seconds.
- Failure messages must say what was expected and what arrived. The reader
  cannot see your code.
- Every check works in a fresh temporary working directory. Create files only
  under `tempfile.mkdtemp()` or the current directory, and clean up.

### Rules for real processes, signals, and threads

The sandbox is a Linux container. The harness talks to the app through file
descriptor 1 as JSON lines, and a non-JSON line on it shows as noise. So:

- A forked child must always end with `os._exit(code)`, inside a
  `try`/`finally`, never by returning or raising. A child that returns falls
  back into the harness and runs the remaining checks a second time.
- A child that should produce output writes it to a pipe that the parent reads
  (or to a file), never to the inherited stdout. When a check `exec`s a real
  program such as `echo` or `cat`, `dup2` a pipe onto fd 1 in the child first.
  An exercise that teaches `exec` provides or asks for a function that captures
  the child's output.
- Always reap every child with `os.waitpid`. Leave no zombies or orphans.
- Use only programs present in `python:3.12-slim`: `sh`, `echo`, `cat`, `true`,
  `false`, `sleep`, `ls`, `wc`, `sort`, `head`, `tr`, `grep`, `sed`, and
  `python3` (`sys.executable`).
- Restore any signal handler or `alarm` a check installs before it returns.
- Threads must be joined with a timeout, and the check fails rather than hangs
  if a join times out.

## Verifying your work

From the repository root, run the harness on the solution and on the starter:

```bash
python3 "$PWD/backend/app/runner/harness.py" check "$PWD/content/exercises/<id>" "$PWD/content/exercises/<id>/solution.py"
python3 "$PWD/backend/app/runner/harness.py" check "$PWD/content/exercises/<id>" "$PWD/content/exercises/<id>/starter.py"
python3 "$PWD/backend/app/runner/harness.py" run "$PWD/content/exercises/<id>" "$PWD/content/exercises/<id>/solution.py"
python3 scripts/check_content.py
```

Pass absolute paths: the harness changes into the exercise directory. It must be run with `backend/app/runner` reachable for `import
oscheck`; it puts its own directory on `sys.path`. The solution must pass every
check; the starter must fail every check with `NotImplementedError`, not with an
import error; the run block of the solution must print its example. Run the
solution's checks five times to catch flaky process or thread checks.
