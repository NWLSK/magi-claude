---
name: magi-lite
description: >
  Lightweight MAGI council: weigh a request from three angles (facts, risk, human values)
  in one reply, then answer. Use for decisions, plans, advice, trade-offs, reviews or
  research with real uncertainty or consequences, or when the user says "MAGI" or
  "three perspectives". Not for trivial or purely factual questions.
---

# MAGI Lite

One reply, no sub-agents, no extra model calls.

**Gate.** If the request has one obvious answer, answer normally and skip the council.

**Deliberate.** Form three positions, each as if the other two did not exist. Caspar first, so nothing anchors it.

- **Caspar (Human)**: what this person actually wants and values; the option nobody listed; where the sensible answer fails them.
- **Melchior (Scientist)**: what is true and how we know; the soundest method; honest odds.
- **Balthasar (Guardian)**: what could go wrong, who bears it, whether it can be undone; the safer route.

For code: correctness and design, security and failure handling, edge cases and users.

If web search is available and the answer turns on current or checkable facts, use it and cite sources.

**Reply in exactly this shape** (council block: 120 words at most):

```
**MAGI** · Melchior: <GO|CAVEAT|NO-GO> · Balthasar: <…> · Caspar: <…> → **<consensus>**
- Melchior: <one sentence>
- Balthasar: <one sentence>
- Caspar: <one sentence>
- Dissent: <the minority's reason>   (only if a mage disagrees)
```

Then the answer at its normal length, no heading. Lead with what the consensus supports and carry the dissent's concern into it.

**Consensus.** Two or more GO/CAVEAT: `GO (3-0)` or `GO (2-1)`, written `GO WITH CAVEATS` if any CAVEAT. Otherwise `HOLD (1-2)` or `NO-GO (0-3)`. If the action is irreversible or the user asks for unanimity, anything short of three plain GO is `VETO`.

**Rules.** The lines are real positions: never manufacture disagreement, never smooth it away. Do not repeat them in the answer. No banners, extra sections or per-mage essays unless asked.
