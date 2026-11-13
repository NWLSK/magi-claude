---
name: magi
description: >
  Three-mind council inspired by the MAGI supercomputers from Evangelion. Three
  independent agents (Melchior, Balthasar, Caspar) answer the same request from different
  angles, vote, and the dissent is kept. Works for any request: questions, decisions,
  plans, research (with web search), writing, and also code review and software design.
  Use it for requests with genuine uncertainty, real trade-offs or significant
  consequences. This is the full council: it launches three separate agents. Trigger
  phrases: "MAGI", "ask the MAGI", "full MAGI", "three perspectives",
  "multi-perspective analysis", "MAGI review". A plain "MAGI" means this skill; only
  "MAGI lite" or "quick MAGI" belongs to the separate magi-lite skill. NOT for trivial
  questions or anything with one obvious answer.
---

# MAGI System

Three agents answer independently, then a deterministic vote produces the consensus.

| Agent | Code modes | General mode |
|-------|------------|--------------|
| **Melchior** | Scientist: technical rigor, correctness | Scientist: logic, facts, evidence |
| **Balthasar** | Pragmatist: practicality, maintainability | Guardian: protection, risk, ethics |
| **Caspar** | Critic: risk, edge cases, failure modes | Human: the person's values, intuition, the unconventional angle |

## Step 1: Gate, then pick the mode

**Gate.** If the request is simple (one clear answer, an obvious fix, a quick lookup),
answer it directly and do not launch MAGI.

**Mode:**

- **`general`** — anything that is not about software: a question, a decision, a plan,
  research, advice, a piece of writing. The mages can search and read the web.
- **`code-review`** — the user provides code or a diff to evaluate.
- **`design`** — software architecture, approach selection, solution design.
- **`analysis`** — a technical problem, debugging, engineering trade-offs.

If it is not about software, use `general`. If it is and none of the three fits, use
`analysis`.

## Step 2: Run the orchestrator

    python skills/magi/scripts/run_magi.py <mode> <input_file_or_text> [options]

Pass a file path, or the request as quoted text. In `general` mode pass the user's
request in full, with any context they gave that the mages need; they see nothing else
from this conversation.

| Option | Use |
|--------|-----|
| `--model opus\|sonnet\|haiku` | Default `opus`. Change only if the user asks ("use sonnet"). An unsupported model: say which are valid and use `opus`. |
| `--web` / `--no-web` | Web search and page reading for the mages. On by default in `general`, off elsewhere. Pass `--web` in another mode only if the user asks for it; pass `--no-web` if they ask for no internet. |
| `--require unanimous` | For actions the user describes as irreversible or high-stakes (deleting data, a production migration, a large financial or legal commitment), or when they ask for unanimity. Anything short of three plain approves becomes `HOLD -- VETO`. |
| `--timeout <s>` | Per-agent timeout, default 900. |
| `--output-dir <dir>` | Where the per-agent files and `magi-report.json` go. |

The script launches the three agents in parallel, validates their output, votes and
prints the report. A run takes a few minutes; in `general` mode with web access, launch
it in the background and wait for completion if it may pass the Bash tool's time limit.

**Open-weight path (`--ollama`, only if the user asks for Ollama).** Runs three
open-weight models through the pinned `magi-rs` binary using the trio in the project's
`.magi/magi.toml`. It cannot be combined with `--model`, has no web access, and runs
`general` requests as `analysis`. Always launch it in the background. Before first use,
or if it fails, read [`docs/ollama-backend.md`](../../docs/ollama-backend.md); do not
edit or delete `.magi/` on your own.

**If Bash is unavailable**, use native sub-agents: launch three in parallel with the
Agent tool, each given the system prompt from `agents/<name>.md` (code modes) or
`agents/general/<name>.md` (general mode) and the same payload:

    MODE: <mode>
    CONTEXT: <the full request>

Then extract each verdict and run
`python skills/magi/scripts/synthesize.py <a.json> <b.json> <c.json> --mode <mode>`.
**If no sub-agents are available either**, use fallback mode. Both paths are specified in
[`references/output-format.md`](references/output-format.md); read it before using them.

## Step 3: Present the result

**The canonical report comes first, always.** Copy the report from `run_magi.py`'s
stdout verbatim, from the `MAGI SYSTEM -- VERDICT` banner to the end of
`## Recommended Actions`. Do not paraphrase, reorder, summarize or strip sections, and
put no preamble ahead of the banner.

#### Canonical output template

```
+==================================================+
|          MAGI SYSTEM -- VERDICT                  |
+==================================================+
|  Melchior (Scientist):   APPROVE (90%)           |
|  Balthasar (Pragmatist): CONDITIONAL (85%)       |
|  Caspar (Critic):        REJECT (78%)            |
+==================================================+
|  CONSENSUS: GO WITH CAVEATS (2-1)                |
+==================================================+

## Key Findings
[!!!] **[CRITICAL]** SQL injection in query builder _(from melchior, caspar)_
[!!]  **[WARNING]**  Missing retry logic for API calls _(from balthasar)_
[i]   **[INFO]**     Consider adding request timeout _(from caspar)_

## Dissenting Opinion
**Caspar (Critic)**: Risk of data loss outweighs shipping speed...

## Conditions for Approval
- **Balthasar**: Add integration tests before merge

## Recommended Actions
- **Melchior** (Scientist): Fix SQL injection, add parameterized queries
- **Balthasar** (Pragmatist): Ship after adding integration tests
- **Caspar** (Critic): Rework query layer before proceeding
```

Sections with nothing in them are omitted; the order never changes; there is no
`## Consensus Summary` section.

**Code modes (`code-review`, `design`, `analysis`):** the report is the whole answer.
Add nothing after `## Recommended Actions` unless the user asks a follow-up.

**General mode:** the script's output continues with `## Council Answers`, each mage's
own full reply. Do not copy that section into your reply. Instead, after
`## Recommended Actions`, act as the council's rapporteur and write:

    ## Answer

followed by one reply to the user, in your normal conversational voice, at the length
the request deserves. Build it from the three council answers:

- Lead with the answer or recommendation the consensus supports.
- Merge what the mages agree on; do not narrate who said what point by point.
- Keep the source links the mages cited, next to the claims they support. Add no source
  that is not in their answers.
- If a mage dissented or set a condition, say so plainly and give its reason. The
  minority view is often the most useful part; never smooth it away.
- If the consensus is a HOLD or a VETO, say that the council did not clear this and what
  would have to change.
- Where the mages contradict each other on a fact, say so instead of picking one silently.

If the user later asks what a particular mage said, quote its council answer from the
script output or from `magi-report.json`.
