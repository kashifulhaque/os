"""Checks for the process table exercise."""

from oscheck import check, equal, fail, has

STATES = ["new", "ready", "running", "blocked", "zombie", "terminated"]


def make_running(table, name, ppid=1):
    """Create a process and walk it to the running state."""
    pid = table.create(name, ppid=ppid)
    table.transition(pid, "ready")
    table.transition(pid, "running")
    return pid


def expect_raises(exc, func, *args, what=""):
    try:
        func(*args)
    except exc:
        return
    except Exception as other:  # noqa: BLE001
        fail(f"{what}: expected {exc.__name__}, got {type(other).__name__}: {other}")
    fail(f"{what}: expected {exc.__name__}, but nothing was raised")


@check("can_transition accepts exactly the seven arrows of the state machine")
def test_can_transition(sub):
    can_transition = has(sub, "can_transition")
    legal = {
        ("new", "ready"),
        ("ready", "running"),
        ("running", "ready"),
        ("running", "blocked"),
        ("running", "zombie"),
        ("blocked", "ready"),
        ("zombie", "terminated"),
    }
    # 6 states x 6 states = 36 pairs; 7 are legal.
    for old in STATES:
        for new in STATES:
            equal(can_transition(old, new), (old, new) in legal, label=f"can_transition({old!r}, {new!r})")


@check("create hands out pids 2, 3, 4 in state new, links parent and child, and rejects a missing parent")
def test_create(sub):
    table = has(sub, "ProcessTable")()
    equal(table.get(1).name, "init", label="pid 1 name")
    pids = [table.create("a"), table.create("b"), table.create("c")]
    equal(pids, [2, 3, 4], label="pids from three create calls")
    pcb = table.get(3)
    equal((pcb.name, pcb.ppid, pcb.state, pcb.exit_status), ("b", 1, "new", None), label="PCB of pid 3")
    test_parent_links(sub)


def test_parent_links(sub):
    ProcessTable = has(sub, "ProcessTable")
    NoSuchProcess = has(sub, "NoSuchProcess")
    table = ProcessTable()
    shell = table.create("shell")
    a = table.create("a", ppid=shell)
    b = table.create("b", ppid=shell)
    equal(table.get(shell).children, [a, b], label="children of shell")
    equal(table.get(a).ppid, shell, label="ppid of a")
    equal(table.get(1).children, [shell], label="children of init")
    expect_raises(NoSuchProcess, table.create, "x", 99, what="create with ppid=99")
    expect_raises(NoSuchProcess, table.get, 99, what="get(99)")


@check("create raises ProcessLimit when the table is full")
def test_limit(sub):
    ProcessTable = has(sub, "ProcessTable")
    ProcessLimit = has(sub, "ProcessLimit")
    table = ProcessTable(max_procs=3)
    # init + two children fill a table of three.
    table.create("a")
    table.create("b")
    expect_raises(ProcessLimit, table.create, "c", 1, what="third create in a 3-slot table")
    equal(len(table.procs), 3, label="entries in the table after the refusal")


@check("transition walks a process through new, ready, running, blocked, ready")
def test_transition_path(sub):
    table = has(sub, "ProcessTable")()
    pid = table.create("p")
    path = ["ready", "running", "blocked", "ready", "running", "ready"]
    for state in path:
        table.transition(pid, state)
        equal(table.get(pid).state, state, label=f"state after transition to {state!r}")


@check("transition rejects illegal moves, leaves the state unchanged, and allows one running process")
def test_illegal(sub):
    table = has(sub, "ProcessTable")()
    IllegalTransition = has(sub, "IllegalTransition")
    pid = table.create("p")
    expect_raises(IllegalTransition, table.transition, pid, "running", what="new -> running")
    equal(table.get(pid).state, "new", label="state after refused new -> running")
    table.transition(pid, "ready")
    table.transition(pid, "running")
    table.transition(pid, "blocked")
    expect_raises(IllegalTransition, table.transition, pid, "running", what="blocked -> running")
    equal(table.get(pid).state, "blocked", label="state after refused blocked -> running")
    # zombie and terminated are entered only through exit() and wait().
    expect_raises(IllegalTransition, table.transition, pid, "zombie", what="blocked -> zombie")
    table.transition(pid, "ready")
    table.transition(pid, "running")
    expect_raises(IllegalTransition, table.transition, pid, "zombie", what="direct running -> zombie")
    equal(table.get(pid).state, "running", label="state after refused direct zombie")
    test_one_cpu(sub)


def test_one_cpu(sub):
    table = has(sub, "ProcessTable")()
    IllegalTransition = has(sub, "IllegalTransition")
    first = make_running(table, "first")
    second = table.create("second")
    table.transition(second, "ready")
    expect_raises(IllegalTransition, table.transition, second, "running", what="second running with first running")
    table.transition(first, "ready")
    table.transition(second, "running")
    equal(table.get(second).state, "running", label="second after first yields")
    equal(table.count_by_state()["running"], 1, label="running count")


@check("exit makes a running process a zombie that keeps its exit status")
def test_exit(sub):
    table = has(sub, "ProcessTable")()
    IllegalTransition = has(sub, "IllegalTransition")
    pid = table.create("p")
    expect_raises(IllegalTransition, table.exit, pid, 0, what="exit of a process that is not running")
    table.transition(pid, "ready")
    table.transition(pid, "running")
    table.exit(pid, 7)
    pcb = table.get(pid)
    equal((pcb.state, pcb.exit_status), ("zombie", 7), label="state and status after exit(7)")
    equal(table.get(1).children, [pid], label="a zombie stays in its parent's children until reaped")
    expect_raises(IllegalTransition, table.exit, 1, 0, what="exit of init")


@check("wait reaps a zombie child, returns (pid, status), and frees the slot")
def test_wait(sub):
    table = has(sub, "ProcessTable")()
    NoChildren = has(sub, "NoChildren")
    shell = table.create("shell")
    expect_raises(NoChildren, table.wait, shell, None, what="wait with no children")
    a = table.create("a", ppid=shell)
    b = table.create("b", ppid=shell)
    for pid in (a, b):
        table.transition(pid, "ready")
    equal(table.wait(shell), None, label="wait while both children are alive")
    table.transition(b, "running")
    table.exit(b, 3)
    equal(table.wait(shell, a), None, label="wait for alive child a")
    equal(table.wait(shell), (b, 3), label="wait() picks the zombie child")
    equal(table.get(b).state, "terminated", label="state of b after reaping")
    equal(table.get(shell).children, [a], label="children after reaping b")
    expect_raises(NoChildren, table.wait, shell, b, what="wait for an already reaped child")
    equal(table.count_by_state()["zombie"], 0, label="zombies after reaping")


@check("a zombie holds a table slot until it is reaped")
def test_zombie_slot(sub):
    ProcessTable = has(sub, "ProcessTable")
    ProcessLimit = has(sub, "ProcessLimit")
    table = ProcessTable(max_procs=2)
    pid = make_running(table, "p")
    table.exit(pid, 0)
    expect_raises(ProcessLimit, table.create, "q", 1, what="create while a zombie fills the table")
    table.wait(1)
    equal(table.create("q"), 3, label="create after the zombie is reaped")


@check("when a parent exits, its children are adopted by init")
def test_orphans(sub):
    table = has(sub, "ProcessTable")()
    shell = make_running(table, "shell")
    a = table.create("a", ppid=shell)
    b = table.create("b", ppid=shell)
    table.exit(shell, 0)
    equal(table.get(a).ppid, 1, label="ppid of orphan a")
    equal(table.get(b).ppid, 1, label="ppid of orphan b")
    equal(sorted(table.get(1).children), sorted([shell, a, b]), label="children of init")
    equal(table.get(shell).children, [], label="children of the dead shell")
    # init can reap the shell zombie, then its adopted children when they exit.
    equal(table.wait(1, shell), (shell, 0), label="init reaps the shell")
    table.transition(a, "ready")
    table.transition(a, "running")
    table.exit(a, 5)
    equal(table.wait(1), (a, 5), label="init reaps adopted child a")


@check("descendants lists every process below a pid, and count_by_state counts them all")
def test_descendants(sub):
    table = has(sub, "ProcessTable")()
    shell = table.create("shell")
    a = table.create("a", ppid=shell)
    b = table.create("b", ppid=a)
    c = table.create("c", ppid=b)
    d = table.create("d", ppid=shell)
    equal(table.descendants(1), [shell, a, b, c, d], label="descendants of init")
    equal(table.descendants(a), [b, c], label="descendants of a")
    equal(table.descendants(c), [], label="descendants of a leaf")
    table.transition(a, "ready")
    counts = table.count_by_state()
    # init is ready, a is ready; shell, b, c, d are new.
    want = {"new": 4, "ready": 2, "running": 0, "blocked": 0, "zombie": 0, "terminated": 0}
    equal(counts, want, label="count_by_state")
