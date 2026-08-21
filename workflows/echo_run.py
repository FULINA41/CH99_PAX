"""
Trigger the Echo workflow and print what comes back.

    uv run python -m echo_run "hello"

Needs the worker running in another terminal.
"""

import sys

from echo import EchoInput, EchoOutput, echo_workflow


def main() -> None:
    message = sys.argv[1] if len(sys.argv) > 1 else "hello"

    # Blocks until the run finishes. Use `wait_for_result=False` for a handle
    # you can poll instead.
    result = echo_workflow.run(EchoInput(message=message))

    # Results come back keyed by task name.
    output = EchoOutput.model_validate(result["echo"])
    print(f"message={output.message!r} length={output.length}")


if __name__ == "__main__":
    main()
