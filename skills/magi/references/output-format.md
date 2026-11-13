# MAGI output format — normative rules and the no-script paths

Read this file only when you have to render the report yourself: native sub-agent mode
after `synthesize.py`, or fallback mode. When `run_magi.py` ran, its stdout is already in
this format and you copy it verbatim.

## Agent verdict schema

Each agent wraps its verdict between two literal marker lines, each alone on its own line:

```
<MAGI_VERDICT>
{ ...the agent's JSON object... }
</MAGI_VERDICT>
```

The agent may reason before the markers; ignore that part. Before writing an agent's
output to `<agent>.json` for `synthesize.py`, extract only the JSON object between the
markers. Do not write the marker lines into the file: `synthesize.py` reads plain JSON.

```json
{
  "agent": "melchior | balthasar | caspar",
  "verdict": "approve | reject | conditional",
  "confidence": 0.0-1.0,
  "summary": "One-line verdict summary",
  "reasoning": "Detailed analysis from this agent's perspective",
  "findings": [
    {"severity": "critical | warning | info", "title": "Short title", "detail": "Explanation"}
  ],
  "recommendation": "What this agent recommends doing",
  "answer": "general mode only, optional: the agent's own full reply, in markdown"
}
```

## Consensus scoring

Weights: `approve = 1`, `conditional = 0.5`, `reject = -1`, averaged over the agents.

| Score | Condition | Consensus |
|-------|-----------|-----------|
| 1.0 | unanimous approve | **STRONG GO** |
| -1.0 | unanimous reject | **STRONG NO-GO** |
| > 0 | has conditionals | **GO WITH CAVEATS (N-M)** |
| > 0 | no conditionals | **GO (N-M)** |
| 0 | — | **HOLD -- TIE** |
| < 0 | — | **HOLD (N-M)** |

`(N-M)` is the majority-minority split: approves and conditionals count together on the
"go" side, rejects on the "no" side.

With `--require unanimous`, anything short of three plain approves becomes
**HOLD -- VETO (N-M)**, where N counts plain approves and M everything else. A missing
seat also vetoes: **HOLD -- VETO (2 of 3 seated)**.

## Format rules

**Banner:**
- Total width 52 columns. Border lines: `+` + 50 `=` + `+`.
- Title centered: `|` + `"MAGI SYSTEM -- VERDICT".center(50)` + `|`.
- Agent rows: `|  <label> <VERDICT> (<conf>%)` padded with spaces to 50 inner chars, then `|`.
- Labels pad to the longest label so all verdict words start at the same column.
  Code modes: `Melchior (Scientist):`, `Balthasar (Pragmatist):`, `Caspar (Critic):`.
  General mode: `Melchior (Scientist):`, `Balthasar (Guardian):`, `Caspar (Human):`.
- `<conf>` is an integer percentage (`85%`, never `0.85`).
- `<VERDICT>` is uppercase: `APPROVE`, `CONDITIONAL`, or `REJECT`.
- Consensus row: `|  CONSENSUS: <label>` left-justified to 50, then `|`.

**Key Findings** (omitted if there are no findings):
- One line per deduplicated finding, sorted critical, warning, info. No blank lines
  between findings, no indented detail line.
- Marker field, width 5, left-justified: `[!!!]`, `[!!] `, `[i]  `.
- One space, then the severity label, width 14, left-justified: `**[CRITICAL]**`,
  `**[WARNING]** `, `**[INFO]**    `.
- One space, then the title, which therefore starts at column 22.
- Suffix: ` _(from <agent1>, <agent2>)_` listing every reporting agent.

**Dissenting Opinion** (omitted if no dissent):
- One line per dissenting agent: `**Name (Title)**: <summary>`.
- The summary only, never the full `reasoning`. The full text stays in the JSON report.

**Conditions for Approval** (omitted if no conditionals):
- `- **Name**: <condition>` (name only, no title).

**Recommended Actions** (always present):
- `- **Name** (Title): <recommendation>`, one per agent, in stable order.

**Council Answers** (general mode only, omitted if no agent gave an `answer`):
- `## Council Answers`, then for each agent a blank line, `### Name (Title)`, and the
  agent's `answer` as written.

There is no `## Consensus Summary` section. Section order never changes; empty optional
sections are dropped, not reordered.

## Fallback mode (no sub-agents available)

If neither `claude -p` nor a sub-agent tool is available, write all three perspectives
yourself in one response.

1. **Caspar first**, then Melchior, then Balthasar, so the dissenting seat is written
   before the others can anchor it.
2. **Independence**: write each as if it had not seen the others. No cross-references.
3. Present three labeled sections, each holding that agent's full JSON object. These are
   scaffolding, not the answer.
4. After a `## Synthesis` heading, emit the canonical banner and sections exactly as
   specified above. In general mode, then write `## Answer` as described in `SKILL.md`.
5. Say in the reply that fallback mode was used: one model writing all three seats is
   prone to anchoring, so the independence is weaker than in a real run.

Example structure:

    ### Caspar (Critic)
    {caspar JSON}

    ### Melchior (Scientist)
    {melchior JSON}

    ### Balthasar (Pragmatist)
    {balthasar JSON}

    ## Synthesis

    (banner, then Key Findings, Dissenting Opinion, Conditions for Approval,
    Recommended Actions)
