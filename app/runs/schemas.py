from datetime import datetime

from app.common.schemas import CamelModel, UserRef
from app.orders.schemas import OrderOut
from app.storage import RunStatus, RunStepType


#one stop on a run's route, which is either a pickup or a drop off of one order
class RunStepOut(CamelModel):
    order_id: str
    type: RunStepType
    completed_at: datetime | None


class RunOut(CamelModel):
    run_id: str
    status: RunStatus
    volunteer: UserRef | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    orders: list[OrderOut]
    #the route in the order the volunteer pplanned it
    steps: list[RunStepOut]


class RunsResponse(CamelModel):
    runs: list[RunOut]


class RunStepIn(CamelModel):
    order_id: str
    type: RunStepType


class CreateRunRequest(CamelModel):
    route: list[RunStepIn]


class RunIdResponse(CamelModel):
    run_id: str
