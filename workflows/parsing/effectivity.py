import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
DATE = r"(?:[A-Z][a-z]{2,8}\.?)\s+\d{1,2},\s+\d{4}"

# Anchored on 'effective with respect to entries' and nothing looser. The same descriptions
# carry a transit exception -- "Except for goods loaded onto a vessel ... before 12:01 a.m.
# eastern daylight time on April 9, 2025" -- which is a carve-out for goods already at sea,
# not the date the provision starts. A pattern that merely looked for 'on or after <date>'
# would read one as the other on 9903.01.51 and 9903.02.43.
EFFECTIVE = re.compile(
    rf"effective\s+with\s+respect\s+to\s+entries\b[^.;\[]{{0,80}}?"
    rf"\bon\s+or\s+after\s+(?P<start>{DATE})"
    rf"(?:[,\s]+and\s+(?P<bound>through|before)\s+(?P<end>{DATE}))?",
    re.IGNORECASE,
)
COMPILER = re.compile(r"\[Compiler's note:\s*(?P<body>[^\]]*)\]", re.IGNORECASE)
# 'terminated as of February 7, 2026', 'terminated on November 10, 2025',
# 'expired at the close of Dec. 31, 2020'.
ENDED_ON = re.compile(rf"(?:terminated|expired)\b[^.;]{{0,30}}?({DATE})", re.IGNORECASE)

TERMINATED = re.compile(r"\bterminat|\bexpir", re.IGNORECASE)
SUSPENDED = re.compile(r"\bsuspend", re.IGNORECASE)


@dataclass
class Effectivity:
    effective_from: date | None = None
    effective_to: date | None = None
    status: str = "in_force"
    status_note: str | None = None


def parse_effectivity(text: str) -> Effectivity:
    """Read the dates and the compiler's asides that say when a provision is in force.

    Two signals, and only these two: the JSON export carries no effective or expiry field of
    any kind, and the PDF marks expiry by shading a row grey, which text extraction destroys.
    So a provision is treated as in force unless its own prose says otherwise (D-0043).

    Args:
        text: A provision's full description, ancestors included -- a superior text's
            'Duties suspended ...' aside genuinely governs the rows beneath it.

    Returns:
        The window it states, its status, and the compiler's asides verbatim so a reader can
        follow the Federal Register citation they usually carry.
    """
    found = Effectivity()

    window = EFFECTIVE.search(text)
    if window:
        found.effective_from = _as_date(window.group("start"))
        end = _as_date(window.group("end")) if window.group("end") else None
        # 'through the 31st' includes it; 'before the 1st' does not, and the last day in
        # force is the day before. Storing both as the last day in force means a caller can
        # compare with <= and never has to know which word was printed.
        if end and window.group("bound").lower() == "before":
            end -= timedelta(days=1)
        found.effective_to = end

    asides = [_tidy(m.group("body")) for m in COMPILER.finditer(text)]
    if asides:
        found.status_note = " ".join(asides)
        if TERMINATED.search(found.status_note):
            found.status = "terminated"
        elif SUSPENDED.search(found.status_note):
            found.status = "suspended"
        ended = ENDED_ON.search(found.status_note)
        if ended and not found.effective_to:
            found.effective_to = _as_date(ended.group(1))

    return found


def _as_date(printed: str) -> date | None:
    month, day, year = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", printed).groups()
    number = MONTHS.get(month.lower())
    return date(int(year), number, int(day)) if number else None


def _tidy(body: str) -> str:
    return re.sub(r"\s+", " ", body).strip()
