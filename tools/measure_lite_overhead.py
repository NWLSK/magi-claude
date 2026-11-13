#!/usr/bin/env python3
"""Check the token budget of the standalone ``magi-lite`` skill.

The lite skill promises to cost at most twice what a plain answer to the same
request would. Its overhead is fixed: the skill file, read once per use, plus the
council block it adds to the reply. So the promise holds exactly when the plain
exchange (request + answer) is at least as large as that overhead, and this tool
reports that break-even size and fails when it grows past a ceiling.

Token counts are estimated at four characters per token, the same approximation
``input_size.py`` uses. It is an estimate, not a tokenizer: the ceiling leaves
room for that.

Usage:
    python tools/measure_lite_overhead.py [--max-break-even-tokens 700]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

CHARS_PER_TOKEN: int = 4
#: The council block's word cap, as stated in the skill file itself.
COUNCIL_BLOCK_MAX_WORDS: int = 120
#: English averages a little over five characters per word, plus the space.
CHARS_PER_WORD: int = 6
#: A plain exchange this size or larger keeps the skill within 2x. About a
#: 450-word answer to a short request; requests smaller than that are the ones
#: the skill's own gate tells the model to answer without the council.
DEFAULT_MAX_BREAK_EVEN_TOKENS: int = 700

SKILL_PATH = Path(__file__).resolve().parent.parent / "standalone" / "magi-lite" / "SKILL.md"


@dataclass(frozen=True)
class LiteOverhead:
    """The fixed token cost the lite skill adds to one exchange."""

    skill_tokens: int
    council_tokens: int

    @property
    def total(self) -> int:
        """Skill file plus council block: the break-even size of a plain exchange."""
        return self.skill_tokens + self.council_tokens

    def ratio(self, plain_tokens: int) -> float:
        """Cost with the skill, relative to a plain exchange of *plain_tokens*.

        Args:
            plain_tokens: Tokens of the request plus the plain answer. Must be > 0.

        Returns:
            ``(plain + overhead) / plain``.
        """
        if plain_tokens <= 0:
            raise ValueError("plain_tokens must be positive")
        return (plain_tokens + self.total) / plain_tokens


def estimate_tokens(text: str) -> int:
    """Estimate the token count of *text* at four characters per token, rounded up."""
    return -(-len(text) // CHARS_PER_TOKEN)


def measure(skill_text: str) -> LiteOverhead:
    """Compute the lite skill's fixed overhead from its file contents.

    Args:
        skill_text: The full text of ``standalone/magi-lite/SKILL.md``.

    Returns:
        The overhead, in estimated tokens.
    """
    council_chars = COUNCIL_BLOCK_MAX_WORDS * CHARS_PER_WORD
    return LiteOverhead(
        skill_tokens=estimate_tokens(skill_text),
        council_tokens=-(-council_chars // CHARS_PER_TOKEN),
    )


def main(argv: list[str] | None = None) -> int:
    """Print the overhead and exit non-zero when it exceeds the ceiling."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-break-even-tokens", type=int, default=DEFAULT_MAX_BREAK_EVEN_TOKENS)
    args = parser.parse_args(argv)

    overhead = measure(SKILL_PATH.read_text(encoding="utf-8"))
    print(f"skill file:     ~{overhead.skill_tokens} tokens")
    print(
        f"council block:  ~{overhead.council_tokens} tokens (cap {COUNCIL_BLOCK_MAX_WORDS} words)"
    )
    print(f"overhead:       ~{overhead.total} tokens")
    print(f"within 2x when the plain exchange is >= ~{overhead.total} tokens")
    for plain in (500, 1000, 2000, 4000):
        print(f"  plain {plain:>5} tokens -> {overhead.ratio(plain):.2f}x")
    if overhead.total > args.max_break_even_tokens:
        print(
            f"FAIL: overhead ~{overhead.total} exceeds the ceiling of "
            f"{args.max_break_even_tokens} tokens; shorten the skill file",
            file=sys.stderr,
        )
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
