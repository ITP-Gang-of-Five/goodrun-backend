from datetime import datetime

from app.common.schemas import CamelModel, UserRef
from app.orders.schemas import OrderOut
from app.storage import RunStatus


class RunOut(CamelModel):
    run_id: str
    status: RunStatus
    volunteer: UserRef | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    orders: list[OrderOut]


class RunsResponse(CamelModel):
    runs: list[RunOut]


class CreateRunRequest(CamelModel):
    order_ids: list[str]


class RunIdResponse(CamelModel):
    run_id: str
