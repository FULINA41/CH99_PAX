"""How a provision's rate relates to the rate in chapters 1 to 98, as the notes state it.

The schedule does settle this, and it settles it in three layers:

  1. A subchapter's own U.S. note 1 sets the default. Subchapter III: "any article described
     in the provisions of this subchapter ... is subject to duty at the rate set forth herein
     **in lieu of** the rate provided therefor in chapters 1 to 98." Subchapter I: "the duties
     provided for in this subchapter are **cumulative duties which apply in addition to** the
     duties, if any, otherwise imposed."
  2. A specific note overrides it -- 31 notes carry the language, most opening
     "**Notwithstanding U.S. note 1 to this subchapter** ... shall **also** be subject to the
     general rates of duty imposed under subheadings in chapters 1 to 97".
  3. A few notes state a relation between two named headings outright (note 19).

This module reads layers 1 and 2. It exists to **cross-check `rate_kind`**, which is derived
from the rate text alone: "The duty provided in the applicable subheading + 25%" reads as
additive, a bare "10%" as replace, and neither reading consults the note that governs it. Two
independent readings that agree are worth more than one that cannot be wrong. D-0058.
"""

import re

CUMULATIVE = re.compile(
    r"notwithstanding\s+U\.S\.\s+note\s+1\s+to\s+this\s+subchapter"
    r"|cumulative\s+dut(?:y|ies)"
    r"|shall\s+(?:also\s+be|be\s+cumulative\s+and\s+imposed\s+in\s+addition)"
    r"|in\s+addition\s+to\s+the\s+dut(?:y|ies)(?:,\s+if\s+any,)?\s+otherwise\s+imposed",
    re.IGNORECASE)

IN_LIEU = re.compile(r"in\s+lieu\s+of\s+the\s+rate", re.IGNORECASE)


def states_cumulation(body: str) -> str | None:
    """Read what a note says about how its duties combine with the ordinary rate.

    Args:
        body: The note's text.

    Returns:
        ``'cumulative'``, ``'in_lieu'``, or None when the note says neither. Cumulative wins
        a note that says both, because that is what "notwithstanding note 1" means: the note
        quotes the default in order to displace it.
    """
    if CUMULATIVE.search(body):
        return "cumulative"
    if IN_LIEU.search(body):
        return "in_lieu"
    return None


# A rate printed as "The duty provided in the applicable subheading + 25%" names the base in
# so many words. That is not a provision disagreeing with note 1 -- it is note 1's own "unless
# the context requires otherwise" clause operating, and 62 provisions are in that position.
# Only a rate that is SILENT about the base can disagree with the note that governs it.
NAMES_THE_BASE = re.compile(r"dut(?:y|ies)\s+provided\s+in", re.IGNORECASE)

# Recorded even though the duty engine knows what to do with it, because "the note decided"
# is only right if the note was read right, and these 18 are where that reading changes a
# number. They are the rows a reviewer should check first.
DISAGREEMENT = ("rate {rate_text!r} is silent about the base and reads as {rate_kind!r}; "
                "the governing note says {cumulation!r}, which decides")


def disagrees(cumulation: str, rate_kind: str, rate_text: str | None) -> bool:
    """Say whether the note and the rate text are two readings that cannot both be right.

    Args:
        cumulation: What the governing note said.
        rate_kind: What the rate text read as.
        rate_text: The rate as printed, which decides whether it names the base at all.

    Returns:
        True only when the rate is silent about the base and the note says the opposite of
        what the rate was read as. A rate naming the base is never in disagreement: it is
        stating the context note 1 defers to.
    """
    if rate_text and NAMES_THE_BASE.search(rate_text):
        return False
    if cumulation == "cumulative":
        return rate_kind in {"replace", "free"}
    if cumulation == "in_lieu":
        return rate_kind == "additive"
    return False
