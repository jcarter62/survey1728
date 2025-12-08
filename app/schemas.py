from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
from typing import Optional

class LoginForm(BaseModel):
    last_name: str = Field(..., min_length=2)
    member_number: str = Field(..., min_length=1)

    @validator("last_name")
    def normalize_last_name(cls, v):
        return v.strip()

class ActivityCreate(BaseModel):
    date: date
    category: str
    description: str
    hours: float = 0.0
    amount: float = 0.0
    notes: Optional[str] = None

    @validator("hours", "amount")
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Must be non-negative")
        return v

class ActivityUpdate(ActivityCreate):
    pass

class SubmissionCreate(BaseModel):
    period_start: date
    period_end: date

    @validator("period_end")
    def valid_range(cls, v, values):
        if "period_start" in values and v < values["period_start"]:
            raise ValueError("period_end must be after period_start")
        return v

class MemberOut(BaseModel):
    id: int
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    access_code: Optional[str]

    class Config:
        orm_mode = True

class EmailLogOut(BaseModel):
    id: int
    member_number: str
    to_address: EmailStr
    subject: str
    body: str
    sent_at: datetime

    class Config:
        orm_mode = True


