from hatchet_sdk import Hatchet

# One client for the process. The worker registers workflows by object, so two workflows
# declared on two different Hatchet() instances cannot be served by the same worker.
hatchet = Hatchet()
