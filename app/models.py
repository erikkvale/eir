from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List

class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(index=True)  # External ID for reference
    first_name: str
    gender: str
    birth_date: str
    observations: List["Observation"] = Relationship(back_populates="patient")

class Observation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: Optional[int] = Field(default=None, foreign_key="patient.id")
    resource_type: str
    status: str
    patient: Optional[Patient] = Relationship(back_populates="observations")
