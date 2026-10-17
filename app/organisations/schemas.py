from datetime import datetime

from app.common.schemas import CamelModel
from app.common.validation import Email


# an organisation's profile as seen by an admin (never includes the password)
class OrganisationOut(CamelModel):
    organisation_id: str
    name: str | None
    email: str
    created_at: datetime
    onboarded: bool


# input for inviting a new organisation. they choose their own name and password when they
# first log in
class CreateOrganisationRequest(CamelModel):
    email: Email


# every organisation, as returned by GET organisations/
class OrganisationsResponse(CamelModel):
    organisations: list[OrganisationOut]
