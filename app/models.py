from typing import Optional
from sqlmodel import Field, SQLModel


class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str
    first_name: str
    gender: str
    birth_date: str

class Observation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str
    resource_type: str
    status: str