---
name: magi-lite
description: >
  Single-reply, low-cost MAGI council: weigh a request from three angles (facts, risk,
  human values) in one reply, then answer. Use when the user says "MAGI lite", "quick
  MAGI" or "lite council". If the full `magi` skill is also available, use that one
  unless the user says lite or quick. Not for trivial or purely factual questions.
---

# MAGI Lite

One reply, no sub-agents. If the full `magi` skill is available and the user did not say lite or quick, use it instead.

**Gate.** If the request has one obvious answer, answer normally and skip the council.

**Deliberate.** Form three positions, each as if the other two did not exist. Caspar first, so nothing anchors it.

- **Caspar (Human)**: what this person wants and values; the option nobody listed; where the sensible answer fails them.
- **Melchior (Scientist)**: what is true and how we know; the soundest method; honest odds.
- **Balthasar (Guardian)**: what could go wrong, who bears it, whether it can be undone; the safer route.

For code: correctness and design, security and failure handling, edge cases and users.

If web search is available and the answer turns on current facts, use it and cite sources.

**Reply in exactly this shape** (council block: 120 words at most):

```
**MAGI** · Melchior: <GO|CAVEAT|NO-GO> · Balthasar: <…> · Caspar: <…> → **<consensus>**
- Melchior: <one sentence>
- Balthasar: <one sentence>
- Caspar: <one sentence>
- Dissent: <the minority's reason>   (only if a mage disagrees)
```

Then the answer at normal length, no heading. Lead with what the consensus supports and carry the dissent's concern into it.

**Consensus.** Two or more GO/CAVEAT: `GO (3-0)` or `GO (2-1)`, written `GO WITH CAVEATS` if any CAVEAT. Otherwise `HOLD (1-2)` or `NO-GO (0-3)`. If the action is irreversible or the user asks for unanimity, anything short of three plain GO is `VETO`.

**Rules.** Never manufacture disagreement, never smooth it away. Do not repeat the lines in the answer. No banners or per-mage essays unless asked.
