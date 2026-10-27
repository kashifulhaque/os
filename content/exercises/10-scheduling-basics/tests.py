"""Checks for the scheduling basics exercise."""

from oscheck import almost, check, equal, fail, has


def J(sub, name, arrival, burst):
    return has(sub, "Job")(name, arrival, burst)


def textbook_jobs(sub):
    return [J(sub, "A", 0, 8), J(sub, "B", 1, 4), J(sub, "C", 2, 9), J(sub, "D", 3, 5)]


@check("fcfs runs jobs in arrival order, back to back")
def test_fcfs(sub):
    fcfs = has(sub, "fcfs")
    # A: 0 + 8 = 8.  B: 8 + 4 = 12.  C: 12 + 9 = 21.  D: 21 + 5 = 26.
    equal(fcfs(textbook_jobs(sub)), [("A", 0, 8), ("B", 8, 12), ("C", 12, 21), ("D", 21, 26)])


@check("fcfs skips idle time, breaks ties by name, and leaves the input list alone")
def test_fcfs_idle_ties(sub):
    fcfs = has(sub, "fcfs")
    # A is done at 2; the CPU idles until B arrives at 5, so B runs 5 to 7.
    jobs = [J(sub, "B", 5, 2), J(sub, "A", 0, 2)]
    equal(fcfs(jobs), [("A", 0, 2), ("B", 5, 7)], label="idle gap")
    equal([j.name for j in jobs], ["B", "A"], label="input order must not change")
    # Both arrive at 0 with equal bursts: name order, so A then B.
    tied = [J(sub, "B", 0, 3), J(sub, "A", 0, 3)]
    equal(fcfs(tied), [("A", 0, 3), ("B", 3, 6)], label="tie on arrival")


@check("sjf picks the shortest arrived job and never preempts")
def test_sjf(sub):
    sjf = has(sub, "sjf")
    # t=0: only A has arrived, so A runs 0-8 even though B, D are shorter.
    # t=8: B(4), C(9), D(5) are ready. B runs 8-12.
    # t=12: C(9), D(5). D runs 12-17. Then C runs 17-26.
    equal(sjf(textbook_jobs(sub)), [("A", 0, 8), ("B", 8, 12), ("D", 12, 17), ("C", 17, 26)])


@check("sjf breaks burst ties by arrival and then name, and jumps over idle gaps")
def test_sjf_ties(sub):
    sjf = has(sub, "sjf")
    # At t=0 only A is ready (A 0-2). At t=2, B(arrival 1, burst 3), C(arrival 1,
    # burst 3), D(arrival 2, burst 3) all tie on burst: arrival 1 beats 2, then
    # name B < C. So B 2-5, C 5-8, D 8-11. Then E arrives at 20: idle 11-20.
    jobs = [J(sub, "D", 2, 3), J(sub, "C", 1, 3), J(sub, "B", 1, 3),
            J(sub, "A", 0, 2), J(sub, "E", 20, 1)]
    equal(sjf(jobs), [("A", 0, 2), ("B", 2, 5), ("C", 5, 8), ("D", 8, 11), ("E", 20, 21)])


@check("srtf preempts when a job with less remaining time arrives")
def test_srtf(sub):
    srtf = has(sub, "srtf")
    # t=0 A (rem 8) runs. t=1 B arrives (4 < 7), B runs through t=5; C(9) at 2
    # and D(5) at 3 never beat B's remaining 3 and 2.
    # t=5: A rem 7, C 9, D 5 -> D runs 5-10. t=10: A rem 7 runs 10-17. C runs 17-26.
    equal(srtf(textbook_jobs(sub)),
          [("A", 0, 1), ("B", 1, 5), ("D", 5, 10), ("A", 10, 17), ("C", 17, 26)])


@check("srtf keeps the earlier arrival on a remaining-time tie, and skips idle time")
def test_srtf_ties(sub):
    srtf = has(sub, "srtf")
    # t=1: A has 2 left, B arrives needing 2. Tie on 2, A arrived first, so A
    # continues: A 0-3, then B 3-5. After a gap, C arrives at 8: C 8-9.
    jobs = [J(sub, "B", 1, 2), J(sub, "A", 0, 3), J(sub, "C", 8, 1)]
    equal(srtf(jobs), [("A", 0, 3), ("B", 3, 5), ("C", 8, 9)])


@check("metrics computes turnaround, waiting, and response from a timeline")
def test_metrics(sub):
    metrics = has(sub, "metrics")
    jobs = textbook_jobs(sub)
    timeline = [("A", 0, 1), ("B", 1, 5), ("D", 5, 10), ("A", 10, 17), ("C", 17, 26)]
    # A: completion 17, turnaround 17-0=17, waiting 17-8=9, response 0-0=0.
    # B: completion 5,  turnaround 5-1=4,   waiting 4-4=0,  response 1-1=0.
    # C: completion 26, turnaround 26-2=24, waiting 24-9=15, response 17-2=15.
    # D: completion 10, turnaround 10-3=7,  waiting 7-5=2,  response 5-3=2.
    want = {
        "A": {"turnaround": 17, "waiting": 9, "response": 0},
        "B": {"turnaround": 4, "waiting": 0, "response": 0},
        "C": {"turnaround": 24, "waiting": 15, "response": 15},
        "D": {"turnaround": 7, "waiting": 2, "response": 2},
    }
    equal(metrics(jobs, timeline), want)


@check("average_metrics averages each measure over the jobs")
def test_average(sub):
    average_metrics = has(sub, "average_metrics")
    per_job = {
        "A": {"turnaround": 17, "waiting": 9, "response": 0},
        "B": {"turnaround": 4, "waiting": 0, "response": 0},
        "C": {"turnaround": 24, "waiting": 15, "response": 15},
        "D": {"turnaround": 7, "waiting": 2, "response": 2},
    }
    got = average_metrics(per_job)
    # turnaround (17+4+24+7)/4 = 52/4 = 13.  waiting (9+0+15+2)/4 = 26/4 = 6.5.
    # response (0+0+15+2)/4 = 17/4 = 4.25.
    almost(got["turnaround"], 13.0, 1e-9, label="average turnaround")
    almost(got["waiting"], 6.5, 1e-9, label="average waiting")
    almost(got["response"], 4.25, 1e-9, label="average response")


@check("the convoy effect: SJF and SRTF cut average turnaround from 110 to 50")
def test_convoy(sub):
    fcfs, sjf, srtf = has(sub, "fcfs"), has(sub, "sjf"), has(sub, "srtf")
    metrics, average_metrics = has(sub, "metrics"), has(sub, "average_metrics")
    jobs = [J(sub, "A", 0, 100), J(sub, "B", 0, 10), J(sub, "C", 0, 10)]
    # FCFS: A ends 100, B 110, C 120 -> (100+110+120)/3 = 110.
    # SJF:  B ends 10, C 20, A 120   -> (10+20+120)/3 = 50.
    got = {}
    for policy in (fcfs, sjf, srtf):
        line = policy(jobs)
        if not line:
            fail(f"{policy.__name__} returned an empty timeline")
        got[policy.__name__] = average_metrics(metrics(jobs, line))["turnaround"]
    almost(got["fcfs"], 110.0, 1e-9, label="FCFS average turnaround")
    almost(got["sjf"], 50.0, 1e-9, label="SJF average turnaround")
    almost(got["srtf"], 50.0, 1e-9, label="SRTF average turnaround")
