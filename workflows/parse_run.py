import argparse
import sys

from parse import ParseInput, parse_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse the staged HTS payloads.")
    parser.add_argument("--release", help="parse a specific release, e.g. 2026HTSRev16")
    args = parser.parse_args()

    ref = parse_workflow.run(ParseInput(release=args.release), wait_for_result=False)

    try:
        result = ref.result()
    except Exception as exc:  # noqa: BLE001 - printed, not traced back at the user
        print(f"run failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _report(result["summarize"])


def _report(summary: dict) -> None:
    print(f"release  {summary['release']}")
    print(f"source   {summary['directory']}/")
    for key, fetch_id in sorted(summary["sources"].items()):
        print(f"  {key:<12} source_fetch #{fetch_id}")

    programmes = summary["programmes"]
    print(f"\nprogramme {programmes['programmes']:>7} editorial trade programmes labelling "
          f"{programmes['rules_labelled']:,} of {programmes['subchapter_iii_rules']:,} "
          f"subchapter III provisions")

    base = summary["hts_base"]
    print(f"\nhts_base  {base['rows']:>7,} rows")
    print(f"          {base['inherited']:>7,} Column 1 rates inherited from an ancestor")
    print(f"          {base['col2_inherited']:>7,} Column 2 rates inherited from an ancestor")
    print(f"          {base['prose_rates']:>7,} rates that cannot be computed")
    print(f"          {base['issues']:>7,} parse_issue rows")

    ch = summary["chapter99"]
    print(f"\nrule      {ch['rules']:>7,} rows   " +
          "  ".join(f"{n:,} {name}" for name, n in sorted(ch["scopes"].items())))
    print(f"          {ch['references']:>7,} code references")
    print(f"          {ch['excludes']:>7,} exclusion edges")
    print(f"          {ch['countries']:>7,} country links")
    print(f"          {ch['identifiers']:>7,} CAS numbers")
    print(f"          {ch['note_citations']:>7,} note citations (unresolved until step 4)")
    print(f"          {ch['issues']:>7,} parse_issue rows")

    nt = summary["notes"]
    print(f"\nnote      {nt['notes']:>7,} records across {nt['subchapters']} subchapters   " +
          "  ".join(f"{n:,} {name}" for name, n in sorted(nt["kinds"].items())))
    print(f"          {nt['subheadings']:>7,} codes listed by a note")
    print(f"          {nt['issues']:>7,} parse_issue rows")

    rs = summary["resolved"]
    print(f"\nresolved  {rs['rule_matches']:>7,} provision -> base matches (cited directly)")
    print(f"          {rs['note_matches']:>7,} note -> base matches (a note's list, once per note)")
    print(f"          {rs['notes_linked']:>7,} citations linked to a note")
    print(f"          {rs['rescoped']:>7,} provisions rescoped once their note was read")
    print("          scope now  " +
          "  ".join(f"{n:,} {name}" for name, n in sorted(rs["scopes"].items())))
    print(f"          {rs['issues']:>7,} parse_issue rows")


if __name__ == "__main__":
    main()
