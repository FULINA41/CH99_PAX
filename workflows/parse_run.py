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


if __name__ == "__main__":
    main()
