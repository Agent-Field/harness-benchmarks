#!/usr/bin/env python3
"""Score the codeaf run and the Harness Leaderboard's harnesses the same way.

    python3 scripts/score.py [path/to/leaderboard/trials.csv.gz]

Reads results/trials.csv. With the leaderboard's trials.csv.gz, it also scores every
harness the leaderboard ran with DeepSeek V4.1 Flash at high effort on
Terminal-Bench 2.1, and writes results/leaderboard-comparison.csv.

Every harness is scored by the same rules:
  - an attempt passes when its reward is 1; an attempt without a reward fails
  - mean of 3: per task, the share of its attempts that passed, averaged over the tasks
  - pass@3: share of tasks where at least one of the three attempts passed
  - all 3: share of tasks where every attempt passed
  - cost per task: the mean cost of one attempt, in USD
  - 95% interval of the mean of 3: bootstrap over the 87 tasks (10,000 resamples, seed 0)
"""
import collections
import csv
import gzip
import json
import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = 87
MODEL_SUFFIX = "DeepSeek-V4.1-Flash"


def score(attempts):
    """attempts: {task: [(passed, cost, seconds), ...]} -> summary dict."""
    tasks = sorted(attempts)
    per_task = [[a[0] for a in attempts[t][:3]] for t in tasks]
    every = [a for t in tasks for a in attempts[t][:3]]
    rate = [statistics.mean(p) for p in per_task] + [0.0] * (TASKS - len(tasks))
    rng = random.Random(0)
    boot = sorted(statistics.mean(rng.choices(rate, k=TASKS)) for _ in range(10000))
    return {
        "tasks": len(tasks),
        "attempts": len(every),
        "mean_of_3_pct": round(100 * sum(statistics.mean(p) for p in per_task) / TASKS, 1),
        "mean_of_3_ci95_pct": [round(100 * boot[250], 1), round(100 * boot[9749], 1)],
        "pass_at_3_pct": round(100 * sum(any(p) for p in per_task) / TASKS, 1),
        "all_3_pct": round(100 * sum(all(p) and len(p) == 3 for p in per_task) / TASKS, 1),
        "cost_per_task_usd": round(statistics.mean(a[1] for a in every), 4),
        "total_cost_usd": round(sum(a[1] for a in every), 2),
        "median_attempt_seconds": round(statistics.median(a[2] for a in every), 0),
    }


def codeaf(audited, unreviewed_pass=False):
    """With audited=True an attempt passes only on verdict `pass`: a rewarded attempt whose
    agent obtained the task's answer (verdict `answer_obtained`) fails, as on the leaderboard,
    and so does a rewarded attempt whose web fetches were not reviewed (verdict `not_reviewed`).
    unreviewed_pass=True counts `not_reviewed` attempts as passes instead."""
    attempts = collections.defaultdict(list)
    with open(ROOT / "results" / "trials.csv") as f:
        for r in csv.DictReader(f):
            ok = {"pass", "not_reviewed"} if unreviewed_pass else {"pass"}
            passed = r["verdict"] in ok if audited else float(r["reward"] or 0) >= 1
            attempts[r["task"]].append((passed, float(r["cost_usd"] or 0), float(r["agent_seconds"] or 0)))
    return score(attempts)


def leaderboard(path, audited):
    """Score the leaderboard's harnesses.

    The leaderboard drops attempts lost to its own infrastructure (verdict
    `infra-excluded`) and reruns them, so those rows are skipped here. With
    audited=False an attempt passes on its reward alone, the rule codeaf's run is
    scored by. With audited=True it passes only on the leaderboard's verdict, which
    also fails rewarded attempts its review rejected; this reproduces the
    published numbers.
    """
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    with gzip.open(path, "rt") as f:
        for r in csv.DictReader(f):
            if (r["benchmark"] != "terminal-bench-2.1" or r["effort"] != "high"
                    or not r["model"].endswith(MODEL_SUFFIX) or r["verdict"] == "infra-excluded"):
                continue
            passed = r["verdict"] == "pass" if audited else float(r["reward"] or 0) >= 1
            by[r["harness"]][r["task"]].append((
                int(r["attempt"] or 0), passed, float(r["cost_usd"] or 0), float(r["agent_s"] or 0),
            ))
    return {h: score({t: [a[1:] for a in sorted(v)] for t, v in tasks.items()}) for h, tasks in by.items()}


def main():
    ours, ours_raw = codeaf(audited=True), codeaf(audited=False)
    ours_hi = codeaf(audited=True, unreviewed_pass=True)
    (ROOT / "results" / "summary.json").write_text(json.dumps(
        {"codeaf senior-dev": {"audited": ours, "audited_unreviewed_counted_pass": ours_hi,
                               "reward_only": ours_raw}}, indent=2) + "\n")
    print("codeaf senior-dev audited", ours)
    print("codeaf senior-dev reward only", ours_raw)
    if len(sys.argv) > 1:
        audited = leaderboard(sys.argv[1], audited=True)
        raw = leaderboard(sys.argv[1], audited=False)
        audited["codeaf senior-dev"], raw["codeaf senior-dev"] = ours, ours_raw
        cols = ["mean_of_3_pct", "pass_at_3_pct", "all_3_pct", "cost_per_task_usd"]
        with open(ROOT / "results" / "leaderboard-comparison.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["harness", *cols, "ci95_low_pct", "ci95_high_pct", "tasks", "attempts",
                        "reward_only_mean_of_3_pct", "reward_only_pass_at_3_pct"])
            for h, s in sorted(audited.items(), key=lambda kv: (-kv[1]["mean_of_3_pct"], kv[1]["cost_per_task_usd"])):
                row = [h, *(s[c] for c in cols), *s["mean_of_3_ci95_pct"], s["tasks"], s["attempts"],
                       raw[h]["mean_of_3_pct"], raw[h]["pass_at_3_pct"]]
                w.writerow(row)
                print("  ".join(str(x) for x in row))


if __name__ == "__main__":
    main()
