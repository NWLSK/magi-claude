"""General mode, web access and the unanimity threshold (7.1.0).

Three additions, and one promise that matters more than any of them: the code
modes behave exactly as they did. Most tests here pin a new behaviour; the ones
named ``unchanged`` pin that promise.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

import run_magi
from consensus import apply_requirement, determine_consensus
from models import MODE_DEFAULT_MODELS
from reporting import format_banner, format_report
from trio_executor import WEB_TOOLS, ClaudeTrio
from validate import load_agent_output

_TOOLS_DIR = str(Path(__file__).resolve().parent.parent / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import measure_lite_overhead as mlo  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MAGES = ("melchior", "balthasar", "caspar")


def _agent(name: str, verdict: str = "approve", **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "agent": name,
        "verdict": verdict,
        "confidence": 0.9,
        "summary": f"{name} summary",
        "reasoning": f"{name} reasoning",
        "findings": [],
        "recommendation": f"{name} recommendation",
    }
    base.update(extra)
    return base


def _trio(*verdicts: str) -> list[dict[str, Any]]:
    return [_agent(name, verdict) for name, verdict in zip(MAGES, verdicts)]


# --- mode, web default and threshold on the command line ------------------------------


class TestParseArgs:
    def test_general_is_a_mode_with_a_default_model(self):
        args = run_magi.parse_args(["general", "a question"])
        assert args.mode == "general"
        assert args.model == MODE_DEFAULT_MODELS["general"]

    def test_web_is_on_by_default_in_general_mode(self):
        assert run_magi.parse_args(["general", "q"]).web is True

    @pytest.mark.parametrize("mode", ["code-review", "design", "analysis"])
    def test_web_is_off_by_default_in_the_code_modes(self, mode):
        assert run_magi.parse_args([mode, "q"]).web is False

    def test_no_web_turns_it_off_in_general_mode(self):
        assert run_magi.parse_args(["general", "q", "--no-web"]).web is False

    def test_web_turns_it_on_in_a_code_mode(self):
        assert run_magi.parse_args(["analysis", "q", "--web"]).web is True

    def test_ollama_never_has_web_and_says_so_when_asked(self, capsys):
        args = run_magi.parse_args(["analysis", "q", "--ollama", "--web"])
        assert args.web is False
        assert "--web has no effect with --ollama" in capsys.readouterr().err

    def test_ollama_without_web_flag_is_silent(self, capsys):
        args = run_magi.parse_args(["general", "q", "--ollama"])
        assert args.web is False
        assert "--web" not in capsys.readouterr().err

    def test_threshold_defaults_to_majority(self):
        assert run_magi.parse_args(["general", "q"]).require == "majority"

    def test_threshold_accepts_unanimous_and_nothing_else(self):
        assert run_magi.parse_args(["general", "q", "--require", "unanimous"]).require == (
            "unanimous"
        )
        with pytest.raises(SystemExit):
            run_magi.parse_args(["general", "q", "--require", "most"])


# --- prompt directories --------------------------------------------------------------


class TestAgentsDir:
    def test_general_mode_reads_its_own_prompts(self):
        general = Path(run_magi._default_agents_dir("general"))
        assert general.name == "general"
        assert general.parent == Path(run_magi._default_agents_dir())
        for mage in MAGES:
            assert (general / f"{mage}.md").is_file()

    @pytest.mark.parametrize("mode", [None, "code-review", "design", "analysis"])
    def test_every_other_mode_reads_the_original_prompts_unchanged(self, mode):
        assert Path(run_magi._default_agents_dir(mode)).name == "agents"

    def test_the_dry_run_validates_both_sets(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            run_magi.check_prompts(run_magi._all_agents_dirs())
        assert exit_info.value.code == 0
        assert capsys.readouterr().out.count("OK:") == 2

    def test_the_dry_run_fails_if_either_set_is_broken(self, tmp_path, capsys):
        empty = tmp_path / "no-prompts-here"  # tmp_path itself is seeded with real prompts
        empty.mkdir()
        with pytest.raises(SystemExit) as exit_info:
            run_magi.check_prompts([run_magi._default_agents_dir(), str(empty)])
        assert exit_info.value.code == 1
        assert "[FATAL]" in capsys.readouterr().err

    def test_general_prompts_ask_for_an_answer_and_name_the_general_mode(self):
        for mage in MAGES:
            text = (Path(run_magi._default_agents_dir("general")) / f"{mage}.md").read_text(
                encoding="utf-8"
            )
            assert "MODE: general" in text
            assert '"answer"' in text


# --- the tools a mage is launched with -------------------------------------------------


def _envelope(agent: str) -> bytes:
    body = _agent(agent)
    return json.dumps(
        {"result": "<MAGI_VERDICT>\n" + json.dumps(body) + "\n</MAGI_VERDICT>"}
    ).encode("utf-8")


class _FakeProc:
    returncode = 0

    def __init__(self, stdout: bytes) -> None:
        self._stdout = stdout

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        return self._stdout, b""


def _run_trio(monkeypatch, tmp_path, trio: ClaudeTrio) -> list[tuple[str, ...]]:
    captured: list[tuple[str, ...]] = []

    async def fake_exec(*args: str, **kwargs: Any) -> _FakeProc:
        agent = next(m for m in MAGES if f"{m}.md" in " ".join(args))
        captured.append(args)
        return _FakeProc(_envelope(agent))

    monkeypatch.setattr("trio_executor.asyncio.create_subprocess_exec", fake_exec)
    for mage in MAGES:
        (tmp_path / f"{mage}.md").write_text("SYS", encoding="utf-8")
    asyncio.run(
        trio.run_trio("PROMPT", str(tmp_path), str(tmp_path), 900, dict.fromkeys(MAGES, "opus"), 1)
    )
    return captured


class TestToolFlags:
    def test_no_tools_launches_the_mages_with_the_original_argv_unchanged(
        self, monkeypatch, tmp_path
    ):
        for argv in _run_trio(monkeypatch, tmp_path, ClaudeTrio()):
            assert "--tools" not in argv
            assert "--allowedTools" not in argv
            assert argv[:6] == ("claude", "-p", "--output-format", "json", "--model", argv[5])
            assert argv[-1] == "-"

    def test_web_tools_are_the_only_tools_and_need_no_prompt(self, monkeypatch, tmp_path):
        for argv in _run_trio(monkeypatch, tmp_path, ClaudeTrio(tools=WEB_TOOLS)):
            assert argv[argv.index("--tools") + 1] == "WebSearch,WebFetch"
            assert argv[argv.index("--allowedTools") + 1] == "WebSearch,WebFetch"

    def test_the_variadic_tool_flags_never_swallow_the_stdin_marker(self, monkeypatch, tmp_path):
        """Both flags take a list; whatever follows a list must be another option."""
        for argv in _run_trio(monkeypatch, tmp_path, ClaudeTrio(tools=WEB_TOOLS)):
            for flag in ("--tools", "--allowedTools"):
                assert argv[argv.index(flag) + 2].startswith("--")
            assert argv[-1] == "-"

    def test_the_web_tools_cannot_touch_files_or_run_commands(self):
        assert set(WEB_TOOLS) == {"WebSearch", "WebFetch"}


# --- the optional answer field ----------------------------------------------------------


class TestAnswerField:
    @staticmethod
    def _load(tmp_path: Path, data: dict[str, Any]) -> dict[str, Any]:
        path = tmp_path / "agent.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return load_agent_output(str(path))

    def test_an_answer_is_kept(self, tmp_path):
        loaded = self._load(tmp_path, _agent("melchior", answer="The answer.\n\nWith a source."))
        assert loaded["answer"] == "The answer.\n\nWith a source."

    def test_an_output_without_an_answer_is_still_valid(self, tmp_path):
        assert "answer" not in self._load(tmp_path, _agent("melchior"))

    @pytest.mark.parametrize("bad", [None, 42, ["a"], {"a": 1}, "", "   "])
    def test_a_malformed_answer_is_dropped_and_the_seat_is_kept(self, tmp_path, bad):
        loaded = self._load(tmp_path, _agent("melchior", answer=bad))
        assert "answer" not in loaded
        assert loaded["verdict"] == "approve"

    def test_an_oversized_answer_is_cut_not_rejected(self, tmp_path):
        loaded = self._load(tmp_path, _agent("melchior", answer="x" * 60_000))
        assert len(loaded["answer"]) == 50_000


# --- the report ------------------------------------------------------------------------


class TestGeneralReport:
    def test_general_mode_uses_the_general_titles(self):
        agents = _trio("approve", "conditional", "reject")
        report = format_report(agents, determine_consensus(agents), mode="general")
        assert "Melchior (Scientist):" in report
        assert "Balthasar (Guardian):" in report
        assert "Caspar (Human):" in report
        assert "Pragmatist" not in report
        assert "Critic" not in report

    def test_every_boxed_line_keeps_the_banner_width(self):
        agents = _trio("approve", "conditional", "reject")
        banner = format_banner(
            {"agents": agents, "consensus": determine_consensus(agents), "mode": "general"}
        )
        assert {len(line) for line in banner.splitlines()} == {52}

    def test_council_answers_follow_the_recommended_actions(self):
        agents = [_agent(name, answer=f"{name} says so.") for name in MAGES]
        report = format_report(agents, determine_consensus(agents), mode="general")
        assert report.index("## Recommended Actions") < report.index("## Council Answers")
        assert "### Balthasar (Guardian)\nbalthasar says so." in report

    def test_council_answers_are_omitted_when_no_mage_gave_one(self):
        agents = _trio("approve", "approve", "approve")
        assert "## Council Answers" not in format_report(
            agents, determine_consensus(agents), mode="general"
        )

    def test_the_dissenting_mage_is_named_with_its_general_title(self):
        agents = _trio("approve", "approve", "reject")
        report = format_report(agents, determine_consensus(agents), mode="general")
        assert "## Dissenting Opinion\n**Caspar (Human)**: caspar summary" in report

    @pytest.mark.parametrize("mode", [None, "code-review", "design", "analysis"])
    def test_the_code_modes_render_unchanged(self, mode):
        """Same bytes as the two-argument call, and an answer never leaks into them."""
        agents = [_agent(name, answer="must not appear") for name in MAGES]
        consensus = determine_consensus(agents)
        rendered = format_report(agents, consensus, mode=mode)
        assert rendered == format_report(agents, consensus)
        assert "Balthasar (Pragmatist):" in rendered
        assert "Caspar (Critic):" in rendered
        assert "Council Answers" not in rendered
        assert "must not appear" not in rendered


# --- the unanimity threshold -------------------------------------------------------------


class TestRequirement:
    def test_majority_returns_the_consensus_untouched(self):
        agents = _trio("approve", "approve", "reject")
        consensus = determine_consensus(agents)
        assert apply_requirement(consensus, agents, "majority") is consensus

    def test_three_plain_approves_pass_unanimity(self):
        agents = _trio("approve", "approve", "approve")
        result = apply_requirement(determine_consensus(agents), agents, "unanimous")
        assert result["consensus"] == "STRONG GO"
        assert result["requirement"] == "unanimous"
        assert "veto" not in result

    def test_one_reject_vetoes(self):
        agents = _trio("approve", "approve", "reject")
        result = apply_requirement(determine_consensus(agents), agents, "unanimous")
        assert result["consensus"] == "HOLD -- VETO (2-1)"
        assert result["consensus_verdict"] == "reject"
        assert result["veto"] == ["caspar"]

    def test_a_conditional_is_not_a_plain_approve_and_vetoes(self):
        agents = _trio("approve", "conditional", "approve")
        result = apply_requirement(determine_consensus(agents), agents, "unanimous")
        assert result["consensus"] == "HOLD -- VETO (2-1)"
        assert result["veto"] == ["balthasar"]

    def test_a_missing_seat_vetoes_even_when_both_present_approve(self):
        agents = _trio("approve", "approve")
        result = apply_requirement(determine_consensus(agents), agents, "unanimous")
        assert result["consensus"] == "HOLD -- VETO (2 of 3 seated)"
        assert result["consensus_verdict"] == "reject"
        assert result["veto"] == []

    def test_a_veto_does_not_mutate_the_original_consensus(self):
        agents = _trio("approve", "approve", "reject")
        consensus = determine_consensus(agents)
        label = consensus["consensus"]
        apply_requirement(consensus, agents, "unanimous")
        assert consensus["consensus"] == label
        assert "veto" not in consensus

    def test_the_veto_label_fits_the_banner(self):
        agents = _trio("approve", "approve")
        consensus = apply_requirement(determine_consensus(agents), agents, "unanimous")
        banner = format_banner({"agents": agents, "consensus": consensus})
        assert "CONSENSUS: HOLD -- VETO (2 of 3 seated)" in banner
        assert {len(line) for line in banner.splitlines()} == {52}

    def test_an_unknown_threshold_is_an_error(self):
        agents = _trio("approve", "approve", "approve")
        with pytest.raises(ValueError):
            apply_requirement(determine_consensus(agents), agents, "most")


# --- main(), end to end with the model calls stubbed -------------------------------------


class _MainHarness:
    """Runs ``run_magi.main()`` with everything outside the function stubbed."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.orchestrator_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.agents: list[dict[str, Any]] = [_agent(n, answer=f"{n} answer") for n in MAGES]
        self.out_dir = tmp_path / "magi-run"

        monkeypatch.setattr(run_magi, "_enable_utf8_console_io", lambda: None)
        monkeypatch.setattr("run_magi.shutil.which", lambda name: "claude")
        monkeypatch.setattr(run_magi, "_resolve_project_root", lambda: str(tmp_path))
        monkeypatch.setattr(run_magi, "project_run_root", lambda root: str(tmp_path))
        monkeypatch.setattr(run_magi, "sweep_legacy_runs_once", lambda: None)
        monkeypatch.setattr(run_magi, "cleanup_old_runs", lambda keep, run_root=None: None)
        monkeypatch.setattr(run_magi, "write_lock", lambda d, max_age_seconds=None: None)
        monkeypatch.setattr(run_magi, "remove_lock", lambda d: None)
        monkeypatch.setattr(
            run_magi, "aggregate_cost", lambda d, agents: {"per_agent": {}, "total_usd": 1.0}
        )

        def fake_create(output_dir: object, run_root: object = None) -> str:
            self.out_dir.mkdir(exist_ok=True)
            return str(self.out_dir)

        monkeypatch.setattr(run_magi, "create_output_dir", fake_create)

        async def fake_orchestrator(*args: Any, **kwargs: Any) -> dict[str, Any]:
            self.orchestrator_calls.append((args, kwargs))
            return {"agents": self.agents, "consensus": {}}

        monkeypatch.setattr(run_magi, "run_orchestrator", fake_orchestrator)

    def run(self, *argv: str) -> dict[str, Any]:
        self.monkeypatch.setattr(sys, "argv", ["run_magi.py", *argv])
        run_magi.main()
        with open(os.path.join(self.out_dir, "magi-report.json"), encoding="utf-8") as handle:
            saved: dict[str, Any] = json.load(handle)
        return saved


@pytest.fixture
def harness(tmp_path, monkeypatch) -> _MainHarness:
    return _MainHarness(tmp_path, monkeypatch)


class TestMain:
    def test_general_mode_runs_the_general_prompts_with_web_tools(self, harness, capsys):
        saved = harness.run("general", "Should I move abroad?")

        args, kwargs = harness.orchestrator_calls[0]
        assert Path(args[0]).name == "general"
        assert args[1].startswith("MODE: general\n")
        assert kwargs["tools"] == WEB_TOOLS
        assert saved["mode"] == "general"
        assert saved["web"] is True

        out = capsys.readouterr().out
        assert "Web: search and page reading enabled" in out
        assert "Balthasar (Guardian):" in out
        assert "## Council Answers" in out
        assert "caspar answer" in out

    def test_general_mode_without_web_grants_no_tools(self, harness):
        saved = harness.run("general", "q", "--no-web")
        assert harness.orchestrator_calls[0][1]["tools"] == ()
        assert saved["web"] is False

    def test_a_code_mode_runs_unchanged(self, harness, capsys):
        saved = harness.run("analysis", "q")

        args, kwargs = harness.orchestrator_calls[0]
        assert Path(args[0]).name == "agents"
        assert kwargs["tools"] == ()
        assert saved["mode"] == "analysis"
        assert saved["web"] is False
        assert "requirement" not in saved["consensus"]

        out = capsys.readouterr().out
        assert "Balthasar (Pragmatist):" in out
        assert "Web:" not in out
        assert "Council Answers" not in out

    def test_a_code_mode_gets_web_only_when_asked(self, harness):
        harness.run("analysis", "q", "--web")
        assert harness.orchestrator_calls[0][1]["tools"] == WEB_TOOLS

    def test_unanimous_holds_a_two_to_one_result(self, harness, capsys):
        harness.agents = _trio("approve", "approve", "reject")
        saved = harness.run("general", "Delete the production database?", "--require", "unanimous")

        assert saved["consensus"]["consensus"] == "HOLD -- VETO (2-1)"
        assert saved["consensus"]["veto"] == ["caspar"]
        out = capsys.readouterr().out
        assert "Threshold: unanimous" in out
        assert "CONSENSUS: HOLD -- VETO (2-1)" in out

    def test_the_same_vote_passes_under_the_default_majority(self, harness):
        harness.agents = _trio("approve", "approve", "reject")
        saved = harness.run("general", "q")
        assert saved["consensus"]["consensus"] == "GO (2-1)"

    def test_general_with_ollama_runs_as_analysis_and_says_so(self, harness, monkeypatch):
        class _Executor:
            last_result = None

            def preflight(self) -> None:
                return None

        seen: dict[str, Any] = {}

        def fake_select(args: Any, timeout: int) -> _Executor:
            seen["mode"] = args.mode
            return _Executor()

        monkeypatch.setattr(run_magi, "_select_executor", fake_select)
        monkeypatch.setattr(run_magi, "resolve_magi_rs_timeout", lambda t: (16820, None))
        monkeypatch.setattr(run_magi, "unpriced_cost", lambda: {"per_agent": {}, "total_usd": None})
        stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", stderr)

        saved = harness.run("general", "q", "--ollama")

        assert seen["mode"] == "analysis"
        args, kwargs = harness.orchestrator_calls[0]
        assert Path(args[0]).name == "agents"
        assert args[1].startswith("MODE: analysis\n")
        assert kwargs["tools"] == ()
        assert saved["mode"] == "analysis"
        assert saved["requested_mode"] == "general"
        assert saved["web"] is False
        assert "general mode is not available with --ollama" in stderr.getvalue()


# --- the standalone lite skill -----------------------------------------------------------


class TestLiteSkill:
    SKILL = REPO / "standalone" / "magi-lite" / "SKILL.md"

    def test_it_lives_outside_the_plugin_skills_directory(self):
        """Inside ``skills/`` the plugin would load it as a second skill of its own."""
        assert self.SKILL.is_file()
        assert not (REPO / "skills" / "magi-lite").exists()

    def test_it_has_the_frontmatter_a_skill_needs(self):
        text = self.SKILL.read_text(encoding="utf-8")
        assert text.startswith("---\nname: magi-lite\ndescription:")
        assert text.count("\n---\n") == 1

    def test_it_is_a_single_file_with_no_scripts(self):
        assert [p.name for p in self.SKILL.parent.iterdir()] == ["SKILL.md"]

    def test_its_fixed_overhead_stays_under_the_ceiling(self):
        overhead = mlo.measure(self.SKILL.read_text(encoding="utf-8"))
        assert overhead.total <= mlo.DEFAULT_MAX_BREAK_EVEN_TOKENS

    def test_a_plain_exchange_at_break_even_costs_exactly_twice(self):
        overhead = mlo.measure(self.SKILL.read_text(encoding="utf-8"))
        assert overhead.ratio(overhead.total) == pytest.approx(2.0)
        assert overhead.ratio(overhead.total * 2) < 2.0

    def test_the_council_cap_in_the_tool_matches_the_skill_file(self):
        text = self.SKILL.read_text(encoding="utf-8")
        assert f"{mlo.COUNCIL_BLOCK_MAX_WORDS} words at most" in text

    def test_the_overhead_tool_passes_on_the_shipped_skill(self, capsys):
        assert mlo.main([]) == 0
        assert "OK" in capsys.readouterr().out

    def test_the_overhead_tool_fails_above_the_ceiling(self, capsys):
        assert mlo.main(["--max-break-even-tokens", "10"]) == 1
        assert "FAIL" in capsys.readouterr().err


class TestMainSkillFile:
    SKILL = REPO / "skills" / "magi" / "SKILL.md"

    def test_it_documents_the_general_mode_and_its_flags(self):
        text = self.SKILL.read_text(encoding="utf-8")
        for needle in ("`general`", "--web", "--no-web", "--require unanimous", "## Answer"):
            assert needle in text

    def test_the_rules_it_points_to_exist(self):
        assert "references/output-format.md" in self.SKILL.read_text(encoding="utf-8")
        assert (self.SKILL.parent / "references" / "output-format.md").is_file()

    def test_it_stays_well_under_its_former_size(self):
        """It was 17 KB, read in full on every invocation."""
        assert self.SKILL.stat().st_size < 9_000
