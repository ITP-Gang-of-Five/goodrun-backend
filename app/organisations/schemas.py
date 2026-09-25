from datetime import datetime

from app.common.schemas import CamelModel


# an organisation's profile as seen by an admin (never includes the password)
class OrganisationOut(CamelModel):
    organisation_id: str
    name: str
    email: str
    created_at: datetime


# input for registering a new organisation account
class CreateOrganisationRequest(CamelModel):
    name: str
    email: str
    password: str


# every organisation, as returned by GET organisations/
class OrganisationsResponse(CamelModel):
    organisations: list[OrganisationOut]
