"""
A workflow that takes an input and returns an output. That's all it does.

It exists to prove your worker is connected and running tasks, and to show the
shape of a Hatchet workflow. Delete it once you have a real one.

    python -m echo_run "some text"
"""

from hatchet_sdk import Context, Hatchet
from pydantic import BaseModel

hatchet = Hatchet()


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    message: str
    length: int


echo_workflow = hatchet.workflow(
    name="Echo",
    input_validator=EchoInput,
)


# The return type hint is what gives you a validated, typed result on the
# other end — without it you get a plain dict back.
@echo_workflow.task()
def echo(input: EchoInput, ctx: Context) -> EchoOutput:
    ctx.log(f"received: {input.message}")
    return EchoOutput(message=input.message, length=len(input.message))
