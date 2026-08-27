# Submission

<!--
Fill this in as you go, not at the end. The headings below are the six things
the README asks for; delete this comment and write under each one.
-->

## 1. How to run it

<!--
The command for each part, in order, from a fresh clone and an empty database.
We will follow these literally, so include the setup steps you'd otherwise do
from memory. Say what we should see when each one works.
-->

## 2. The data model, and why

<!--
The section we read most carefully. Walk us through how you decided to
represent Chapter 99's relationship to the rest of the schedule.
-->

## 3. Part 3: what you built, and why that

<!--
What you decided was worth understanding about this data, what you left out,
and how your storage layer is shaped to serve it.
-->

## 4. What you'd do with another week

<!--
Known bugs, shortcuts, the thing that's held together with tape. Be blunt.
-->

## 5. Assumptions

<!--
Where the data was ambiguous and you had to pick. What you picked, and why.
-->

Where the sources were ambiguous, the reading is recorded in `docs/DECISIONS.md` and the
provision that forced it is cited there. The ones that change an answer on screen:

| Assumption | Why | Where |
| --- | --- | --- |
| Chapter 99 rates replace the ordinary rate unless a note says otherwise | U.S. note 1 to subchapter III says *"in lieu of"*; 31 notes override with *"Notwithstanding U.S. note 1"*. The note is read per provision, not assumed | D-0058 |
| A provision that names countries reaches no others | The schedule states the origin in prose only. Provisions naming a bloc (*"a member state of the European Union"*) are expanded to members | D-0056 |
| A provision with no date is in force | Expiry is marked by grey shading in the PDF, which text extraction destroys. Only dates written into the description are read | D-0043 |
| Column 2 applies to Cuba, North Korea, Russia, Belarus | General Note 3(b) is in none of the three sources. This list is **editorial**, and the UI says so | D-0054 |
| "Section 301" / "Section 232" are our labels | The schedule never names a statute — across 350 U.S. notes the only one mentioned is *section 201*. The mapping is one small editorial table | D-0045 |
| Exclusions are reported, not applied | Whether an exclusion covers a shipment depends on the goods, not the code. They are listed and counted; they never move the number | D-0069 |

Two things the site therefore does not claim. It does not give **one** rate when the
sources do not determine one — competing replacements are shown as a range, and `api/audit.py`
checks that property over 20,000 queries. And it does not classify goods: search matches the
schedule's wording, not your shipment.

**Release.** All figures in this repository were measured against **2026HTSRev17**, the
release current on 2026-08-27. The HTSUS is revised several times a year and `data/` is
gitignored, so a later clone fetches whatever is current then and counts will differ.
`source_fetch` records the release every row came from, and the UI footer shows it.

## 6. Where you used AI tools

<!--
Including anything you shipped without fully verifying.
-->
