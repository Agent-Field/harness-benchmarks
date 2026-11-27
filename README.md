# Harness benchmarks

These are benchmark runs of codeaf's agents. Each run is set up and scored to compare directly
with a published harness leaderboard. Each folder holds one benchmark: what was run and how, the
results of every attempt, and the scripts that recompute every number.

| Benchmark | Agent | Model | Rank | Pass rate (mean of 3) | Cost per attempt |
|---|---|---|---:|---:|---:|
| [Terminal-Bench 2.1](terminal-bench-2.1) | codeaf senior-dev | DeepSeek-V4.1-Flash, high effort | 1 of 13 | 82.0% | $0.026 |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="terminal-bench-2.1/results/charts/cost-vs-score-dark.svg">
  <img alt="Terminal-Bench 2.1: pass rate against cost per attempt for 13 harnesses. codeaf senior-dev has the highest pass rate at the lowest cost." src="terminal-bench-2.1/results/charts/cost-vs-score-light.svg" width="880">
</picture>

## Terminal-Bench 2.1 ranking

DeepSeek-V4.1-Flash at high reasoning effort, 87 tasks, 3 attempts per task, every harness scored by the
[Harness Leaderboard](https://huggingface.co/spaces/joelniklaus/harness-leaderboard)'s rules. The other
rows are the leaderboard's published results.

| # | Harness | Mean of 3 | 95% interval | pass@3 | All 3 | Cost per attempt | Cost vs codeaf |
|---:|---|---:|---:|---:|---:|---:|---:|
| **1** | **codeaf senior-dev** | **82.0%** | 75.1–88.5% | **89.7%** | **72.4%** | **$0.026** | **1.0×** |
| 2 | kimi-code | 78.2% | 70.5–85.4% | 88.5% | 66.7% | $0.047 | 1.9× |
| 3 | grok-build | 77.8% | 70.1–85.1% | 87.4% | 66.7% | $0.047 | 1.8× |
| 4 | codex | 74.7% | 67.0–82.0% | 86.2% | 59.8% | $0.032 | 1.3× |
| 4 | opencode | 74.7% | 66.7–82.4% | 87.4% | 64.4% | $0.033 | 1.3× |
| 4 | claude-code | 74.7% | 67.0–82.0% | 87.4% | 60.9% | $0.043 | 1.7× |
| 4 | fx | 74.7% | 66.7–82.4% | 83.9% | 62.1% | $0.054 | 2.1× |
| 8 | deepseek-harness | 74.3% | 66.3–82.0% | 85.1% | 62.1% | $0.041 | 1.6× |
| 9 | pi | 73.2% | 65.1–80.8% | 85.1% | 58.6% | $0.028 | 1.1× |
| 10 | qwen-code | 72.8% | 64.8–80.5% | 85.1% | 60.9% | $0.048 | 1.9× |
| 11 | mini-swe-agent | 72.4% | 64.4–80.1% | 85.1% | 56.3% | $0.051 | 2.0× |
| 12 | openclaw | 65.5% | 56.7–74.3% | 73.6% | 54.0% | $0.047 | 1.9× |
| 13 | hermes | 64.8% | 56.3–73.2% | 79.3% | 48.3% | $0.043 | 1.7× |

Mean of 3 is, per task, the share of its three attempts that passed, averaged over the 87 tasks.
The 95% interval comes from resampling the tasks; with one three-attempt run per harness, the order of
the top three is not settled. Method, scoring rules and per-attempt data are in
[terminal-bench-2.1](terminal-bench-2.1).
