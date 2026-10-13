from pydantic import BaseModel, Field


class OutageCreate(BaseModel):
    area: str
    cause: str | None = None
    eta: str | None = None
    status: str = Field(default="reported")  # a crew can report straight to 'confirmed' if seen live


class OutageUpdate(BaseModel):
    status: str | None = None
    cause: str | None = None
    eta: str | None = None


class PendingReportCreate(BaseModel):
    phone: str
    area: str
    consent_to_sms: bool = True
    ttl_hours: float = 24  # override in demos to see expiry without waiting a day
