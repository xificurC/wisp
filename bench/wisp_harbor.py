"""Harbor agent adapter: run the wisp single-file harness inside a task container.

Host requirements (read from the harbor process environment):
  WISP_LLM_URL            LiteLLM chat-completions endpoint (passed through)
  WISP_LLM_API_KEY        API key for the endpoint (passed through)
  WISP_BENCH_WISP_SRC     Path to the single-file wisp binary on the host
                          (default /home/pnagyux/code/wisp/wisp/wisp)
  WISP_BENCH_CA_BUNDLE    Host CA bundle to upload (default the system bundle)
  WISP_BENCH_MODELINFO    Model price table to upload
                          (default WISP_LLM_MODEL_INFO_FILE)

Container prerequisites installed by install(): python3, git,
ca-certificates. SSL_CERT_FILE points at the uploaded bundle because the
task images lack the company root CA the endpoint chains to.

The adapter runs `wisp new` + `wisp run` with WISP_SESSIONS_ROOT under
/logs/agent, so Harbor collects the whole session (wisp.jsonl, wisp.usage,
wisp.log) into the trial directory.

After the trial syncs the logs back, populate_context_post_run() converts
wisp.jsonl into an ATIF trajectory at <agent>/trajectory.json and copies the
final token and cost totals onto the Harbor AgentContext. Both steps matter
for `harbor view`: the viewer reads cost and per-step token metrics from the
trajectory, while the job and trial tables read totals from result.json.
"""

import json
import os
import shlex
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories import (
    Agent as TrajectoryAgent,
    FinalMetrics,
    Metrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)
from harbor.utils.trajectory_utils import format_trajectory_json

WISP_SRC = os.environ.get("WISP_BENCH_WISP_SRC", "/home/pnagyux/code/wisp/wisp/wisp")
CA_BUNDLE = os.environ.get("WISP_BENCH_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
WISP = "/installed-agent/wisp"
SESSIONS = "/logs/agent/wisp-sessions"
PASS_ENV = ("WISP_LLM_URL", "WISP_LLM_API_KEY")
DEFAULT_MODEL = os.environ.get("WISP_BENCH_MODEL", "")


def _modelinfo_host_path() -> str | None:
    candidate = os.environ.get(
        "WISP_BENCH_MODELINFO", os.environ.get("WISP_LLM_MODEL_INFO_FILE")
    )
    if candidate and Path(candidate).is_file():
        return candidate
    return None


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _turn_metrics(usage) -> Metrics | None:
    """Fold one wisp assistant turn's usage chunks into ATIF Metrics."""
    prompt = completion = cached = 0
    cost = 0.0
    priced = False
    tokens = False
    for chunk in _as_list(usage):
        if not isinstance(chunk, dict):
            continue
        prompt += int(chunk.get("prompt_tokens") or 0)
        completion += int(chunk.get("completion_tokens") or 0)
        details = chunk.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            cached += int(details.get("cached_tokens") or 0)
        if chunk.get("cost") is not None:
            cost += float(chunk["cost"])
            priced = True
        tokens = tokens or bool(prompt or completion)
    if not tokens and not priced:
        return None
    return Metrics(
        prompt_tokens=prompt,
        completion_tokens=completion,
        cached_tokens=cached,
        cost_usd=cost if priced else None,
    )


def _tool_call(part: dict, fallback_id: str) -> ToolCall:
    arguments = part.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            arguments = {"raw": arguments}
    if not isinstance(arguments, dict):
        arguments = {"raw": arguments}
    return ToolCall(
        tool_call_id=str(part.get("id") or fallback_id),
        function_name=str(part.get("name") or "unknown"),
        arguments=arguments,
    )


def build_steps(events: list[dict]) -> list[Step]:
    """Turn wisp.jsonl records into ATIF steps with tool observations attached."""
    steps: list[Step] = []
    owner: dict[str, int] = {}  # tool_call_id -> index of the step that made it
    for event in events:
        kind = event.get("type")
        if kind == "user":
            text = event.get("content")
            if isinstance(text, str) and text:
                steps.append(
                    Step(step_id=len(steps) + 1, source="user", message=text)
                )
        elif kind == "assistant":
            text: list[str] = []
            reasoning: list[str] = []
            calls: list[ToolCall] = []
            for part in _as_list(event.get("output")):
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text.append(str(part.get("text") or ""))
                elif part.get("type") == "reasoning":
                    reasoning.append(str(part.get("text") or ""))
                elif part.get("type") == "tool_call":
                    calls.append(
                        _tool_call(part, f"call-{len(steps) + 1}-{len(calls) + 1}")
                    )
            index = len(steps)
            steps.append(
                Step(
                    step_id=index + 1,
                    source="agent",
                    message="\n".join(t for t in text if t),
                    reasoning_content="\n\n".join(r for r in reasoning if r) or None,
                    tool_calls=calls or None,
                    metrics=_turn_metrics(event.get("usage")),
                )
            )
            for call in calls:
                owner[call.tool_call_id] = index
        elif kind == "tool":
            index = owner.get(str(event.get("call_id")))
            if index is None:
                continue
            result = ObservationResult(
                source_call_id=str(event.get("call_id")),
                content=str(event.get("content") or ""),
            )
            observation = steps[index].observation
            if observation is None:
                observation = Observation(results=[])
                steps[index].observation = observation
            observation.results.append(result)
    return steps


def final_metrics(steps: list[Step]) -> FinalMetrics:
    prompt = completion = cached = 0
    cost = 0.0
    priced = True
    for step in steps:
        metrics = step.metrics
        if metrics is None:
            continue
        prompt += metrics.prompt_tokens or 0
        completion += metrics.completion_tokens or 0
        cached += metrics.cached_tokens or 0
        if metrics.cost_usd is None:
            priced = False
        else:
            cost += metrics.cost_usd
    return FinalMetrics(
        total_prompt_tokens=prompt,
        total_completion_tokens=completion,
        total_cached_tokens=cached,
        total_cost_usd=cost if priced else None,
        total_steps=len(steps),
    )


def find_transcript(logs_dir: Path) -> Path | None:
    root = Path(logs_dir) / "wisp-sessions"
    transcripts = sorted(root.glob("*/wisp.jsonl"))
    if not transcripts:
        return None
    preferred = root / "wisp" / "wisp.jsonl"
    return preferred if preferred in transcripts else transcripts[-1]


class Wisp(BaseInstalledAgent):
    @staticmethod
    def name() -> str:
        return "wisp"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # In-container usage scrape, used only when the post-run log sync
        # yields no transcript to convert.
        self._usage_fallback: dict[str, float] = {}

    async def install(self, environment: BaseEnvironment) -> None:
        await self.exec_as_root(
            environment,
            command="export DEBIAN_FRONTEND=noninteractive; "
            "(command -v python3 >/dev/null && command -v git >/dev/null) || "
            "(apt-get update -qq && apt-get install -y -qq python3 git ca-certificates) >/dev/null 2>&1; "
            f"mkdir -p /installed-agent && chmod 755 /installed-agent",
        )
        modelinfo = _modelinfo_host_path()
        if modelinfo:
            await environment.upload_file(
                Path(modelinfo), "/installed-agent/modelinfo.json"
            )
        if Path(CA_BUNDLE).is_file():
            await environment.upload_file(Path(CA_BUNDLE), "/installed-agent/ca-bundle.crt")
        await environment.upload_file(Path(WISP_SRC), WISP)
        await self.exec_as_root(
            environment,
            command=f"chmod a+rx {WISP} && ln -sf {WISP} /usr/local/bin/wisp",
        )

    def get_version_command(self) -> str:
        return f"{WISP} --help | head -1"

    def convert_trajectory(self, logs_dir: Path) -> Trajectory | None:
        transcript = find_transcript(logs_dir)
        if transcript is None:
            return None
        events: list[dict] = []
        try:
            lines = transcript.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
        steps = build_steps(events)
        if not steps:
            return None
        return Trajectory(
            agent=TrajectoryAgent(
                name="wisp",
                version="unknown",
                model_name=self.model_name or DEFAULT_MODEL or "unknown",
            ),
            steps=steps,
            final_metrics=final_metrics(steps),
        )

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Convert the synced wisp transcript into ATIF and copy the totals."""
        try:
            trajectory = self.convert_trajectory(self.logs_dir)
        except Exception:
            self.logger.exception("Failed to convert wisp transcript to trajectory")
            trajectory = None

        if trajectory is not None:
            try:
                path = self.logs_dir / "trajectory.json"
                path.write_text(
                    format_trajectory_json(trajectory.to_json_dict()),
                    encoding="utf-8",
                )
                self.logger.debug(f"Wrote wisp trajectory to {path}")
            except OSError as exc:
                self.logger.debug(f"Failed to write {path}: {exc}")

            metrics = trajectory.final_metrics
            if metrics is not None:
                context.cost_usd = metrics.total_cost_usd
                context.n_input_tokens = metrics.total_prompt_tokens or 0
                context.n_cache_tokens = metrics.total_cached_tokens or 0
                context.n_output_tokens = metrics.total_completion_tokens or 0
                return

        fallback = self._usage_fallback
        if fallback.get("turns"):
            context.n_input_tokens = int(fallback["input"])
            context.n_cache_tokens = int(fallback["cached"])
            context.n_output_tokens = int(fallback["output"])
            context.cost_usd = fallback.get("cost") or None
            context.metadata = {"wisp": fallback}

    @with_prompt_template
    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        env = {key: os.environ[key] for key in PASS_ENV if key in os.environ}
        if _modelinfo_host_path():
            env["WISP_LLM_MODEL_INFO_FILE"] = "/installed-agent/modelinfo.json"
        if Path(CA_BUNDLE).is_file():
            env["SSL_CERT_FILE"] = "/installed-agent/ca-bundle.crt"
        model = self.model_name or DEFAULT_MODEL
        if not model:
            raise ValueError(
                "no model: pass harbor -m MODEL or set WISP_BENCH_MODEL"
            )
        await self.exec_as_agent(environment, command="mkdir -p /logs/agent")
        await self.exec_as_agent(
            environment,
            command=f"printf %s {shlex.quote(instruction)} > /tmp/problem.txt",
        )
        await self.exec_as_agent(
            environment,
            command=(
                f"export WISP_SESSIONS_ROOT={SESSIONS}; "
                f"session=$(wisp new --name wisp -m {shlex.quote(model)} "
                "--env-in-system-prompt -s <(wisp build-system-prompt --wisp)) || exit $?; "
                'cd /app 2>/dev/null || cd "$HOME"; '
                'wisp run -d "$session" < /tmp/problem.txt > /logs/agent/wisp.stream '
                "2> /logs/agent/wisp-stderr.log"
            ),
            env=env,
        )
        # Keep a fallback in case the host never receives the transcript.
        totals = {"input": 0, "cached": 0, "output": 0, "turns": 0, "cost": 0.0}
        usage = await self.exec_as_agent(
            environment, command=f"cat {SESSIONS}/wisp/wisp.usage 2>/dev/null || true"
        )
        for line in (usage.stdout or "").splitlines():
            try:
                chunk = json.loads(line.removeprefix("data: "))
            except ValueError:
                continue
            use = chunk.get("usage") or chunk
            if not isinstance(use, dict):
                continue
            totals["input"] += int(use.get("prompt_tokens") or 0)
            totals["output"] += int(use.get("completion_tokens") or 0)
            totals["cached"] += int(
                (use.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            )
            totals["cost"] += float(use.get("cost") or 0)
            totals["turns"] += 1
        self._usage_fallback = totals
