"""Harbor adapter: codeaf's senior-dev program (the specialist), not plain `codeaf do`.

One trial = one `codeaf senior-dev run` inside the task container:
  * a static linux/amd64 (or arm64) codeaf binary uploaded to /installed-agent,
  * every model role (--high coder, --low summaries) pinned to the run's model,
    thinking --variant set from the run's effort,
  * --in-place: no commits into the graded tree; codeaf's HOME and session
    store live under /logs/agent (outside the task's working tree, copied out
    for autopsy),
  * model calls go to the host meter (harness/meter.py) with a dummy key; the
    meter pins the provider, enforces effort and records usage + cost.
No step, token or cost cap: the task's own time limit is the only bound, as on
the Harness Leaderboard.
"""

from __future__ import annotations

import json
import os
import shlex
import tomllib
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

HERE = Path(__file__).resolve().parent
BIN_DIR = Path(os.environ.get("CODEAF_BIN_DIR", HERE.parent / "bin"))
METER_PORT = int(os.environ.get("METER_PORT", "18788"))
METER_LOG = Path(os.environ.get("METER_LOG", "calls.jsonl"))
CA_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")
LOGS = "/logs/agent"

# The container's default gateway is the host running the meter. Pure POSIX sh +
# /proc, because task images may lack ip/awk/bash.
GATEWAY_SH = (
    'gw=""; while read -r ifc dst g rest; do if [ "$dst" = "00000000" ]; then '
    'gw=$(printf "%d.%d.%d.%d" 0x$(echo $g|cut -c7-8) 0x$(echo $g|cut -c5-6) 0x$(echo $g|cut -c3-4) 0x$(echo $g|cut -c1-2)); break; fi; '
    'done < /proc/net/route; [ -n "$gw" ] || gw=172.17.0.1'
)


# MERGE-BACK: in a git
# repository senior-dev works in a copy and leaves its result on a branch of its own,
# never touching the checkout ("its work is on the branch B in R ... `git -C R merge B`
# brings it in"). Graders read the checkout, so the adapter runs exactly the merge codeaf
# prints. A conflict is aborted and left as is. Logged to land.txt.
LAND_SH = (
    f'line=$(grep -o "its work is on the branch [^ ]* in [^,]*" {LOGS}/senior-dev.stderr.txt | tail -n 1); '
    'if [ -n "$line" ]; then br=$(echo "$line" | sed "s/^its work is on the branch \\([^ ]*\\) in .*/\\1/"); '
    'repo=$(echo "$line" | sed "s/^its work is on the branch [^ ]* in //"); '
    # When the checkout had uncommitted changes, the branch already begins with them and
    # codeaf says to `git stash` first; merging over the dirty tree kept the old files.
    f'{{ echo "branch=$br repo=$repo"; G="git -C $repo -c user.email=codeaf@bench -c user.name=codeaf"; stashed=0; '
    'if [ -n "$($G status --porcelain 2>/dev/null)" ]; then $G stash push -u -m codeaf-land 2>&1 && stashed=1; fi; echo "stashed=$stashed"; '
    '$G merge --no-edit "$br" 2>&1 '
    f'|| {{ echo MERGE-FAILED; $G merge --abort 2>&1; [ $stashed = 1 ] && $G stash pop 2>&1; }}; }} > {LOGS}/land.txt 2>&1; '
    f'else echo "no branch to land" > {LOGS}/land.txt; fi; '
)


class CodeafSeniorDev(BaseInstalledAgent):
    @staticmethod
    def name() -> str:
        return "codeaf-senior-dev"

    def get_version_command(self) -> str | None:
        return "/installed-agent/codeaf --version"

    def parse_version(self, stdout: str) -> str:
        return stdout.strip().splitlines()[-1].strip()

    async def install(self, environment: BaseEnvironment) -> None:
        arch = await environment.exec(command="uname -m", user="root")
        machine = (arch.stdout or "").strip()
        binary = BIN_DIR / ("codeaf-arm64" if machine in ("aarch64", "arm64") else "codeaf-amd64")
        await environment.upload_file(binary, "/installed-agent/codeaf")
        if CA_BUNDLE.exists():
            await environment.upload_file(CA_BUNDLE, "/installed-agent/ca.pem")
        await self.exec_as_root(environment, command="chmod 755 /installed-agent/codeaf; chmod 644 /installed-agent/ca.pem 2>/dev/null; "
                                f"mkdir -p {LOGS} && chmod 777 {LOGS}")

    def _trial(self) -> str:
        return self.logs_dir.parent.name

    def _wall_hours(self) -> float | None:
        """The task's own agent time limit, less a margin, as senior-dev's wall budget.

        senior-dev already reserves part of a bounded budget to land its work; told
        nothing, it never knows the deadline and Harbor kills it before it submits.
        """
        try:
            config = json.loads((self.logs_dir.parent / "config.json").read_text())
            task = tomllib.loads((Path(config["task"]["path"]) / "task.toml").read_text())
            seconds = float(task["agent"]["timeout_sec"]) * float(config.get("agent_timeout_multiplier") or 1.0)
        except (OSError, KeyError, ValueError, TypeError):
            return None
        return round(seconds * 0.9 / 3600, 4)

    def _model(self) -> str:
        model = self.model_name or "deepseek/deepseek-v4.1-flash"
        return model if model.startswith("openrouter/") else f"openrouter/{model}"

    @with_prompt_template
    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        effort = os.environ.get("EFFORT", "high")
        model = self._model()
        (self.logs_dir / "instruction.md").write_text(instruction)
        wall = self._wall_hours()
        # --max-hours, not SENIOR_DEV_MAX_WALL_H: the CLI fills senior-dev's 3 h default ceiling
        # into a flag when none is given, and a flag outranks the variable.
        wall_flag = f"--max-hours {wall} " if wall and os.environ.get("CODEAF_WALL", "1") != "0" else ""
        cmd = (
            f"{GATEWAY_SH}; "
            # CODEAF_HOME, not HOME: the agent's own installs (pip --user, R's user
            # library, ~/.cache) must land where the grader, with the normal HOME, finds them.
            f"export CODEAF_HOME={LOGS}/codeaf-home OPENROUTER_API_KEY=sk-or-v1-meter "
            f"CODEAF_BASE_URL=http://$gw:{METER_PORT}/t/{self._trial()}/api/v1 "
            f"SSL_CERT_FILE=/installed-agent/ca.pem SENIOR_DEV_KEEP_SHELL_PROCESSES=1; mkdir -p $CODEAF_HOME; "
            f'echo "meter=$CODEAF_BASE_URL dir=$(pwd) home=$HOME max_hours={wall_flag or 'none'}" > {LOGS}/codeaf-env.txt; '
            f'/installed-agent/codeaf senior-dev run --json {wall_flag}--dir "$(pwd)" --in-place '
            f"--state-dir {LOGS}/codeaf-state --high {model} --low {model} --asked --variant {effort} "
            f"-- {shlex.quote(instruction)} > {LOGS}/senior-dev.jsonl 2> {LOGS}/senior-dev.stderr.txt; "
            f"rc=$?; echo $rc > {LOGS}/exit-code.txt; "
            f"{LAND_SH if os.environ.get('CODEAF_LAND', '1') != '0' else ''}"
            "exit 0"
        )
        await self.exec_as_agent(environment, command=cmd)

    def populate_context_post_run(self, context: AgentContext) -> None:
        trial = self._trial()
        n_in = n_out = n_cache = 0
        cost = 0.0
        calls = 0
        if METER_LOG.exists():
            for line in METER_LOG.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("trial") != trial or "usage" not in row:
                    continue
                u = row["usage"]
                calls += 1
                n_in += int(u.get("prompt_tokens") or 0)
                n_out += int(u.get("completion_tokens") or 0)
                n_cache += int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
                cost += float(row.get("cost_usd") or 0.0)
        context.n_input_tokens = n_in
        context.n_output_tokens = n_out
        context.n_cache_tokens = n_cache
        context.cost_usd = cost
        (self.logs_dir / "meter-summary.json").write_text(json.dumps(
            {"trial": trial, "calls": calls, "input_tokens": n_in, "output_tokens": n_out, "cached_tokens": n_cache, "cost_usd": cost}))
