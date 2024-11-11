import os
import requests
import requests
from typing import Optional, Generator, List
from fastapi import FastAPI, Depends, HTTPException, Form
from sqlmodel import select, Session, SQLModel, and_
from contextlib import asynccontextmanager
from app.models import Patient, Observation
from app.database import get_session, engine
from app.auth.dependencies import get_current_user
from app.auth.jwt_handler import create_access_token

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Dropping and recreating database tables...")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("Database tables recreated.")
    yield
    print("App shutting down.")


app = FastAPI(lifespan=lifespan)

# AuthN
@app.post("/token")
def login(username: str = Form(...), password: str = Form(...)):
    """
    Login endpoint to generate JWT tokens.
    """
    if username == "testuser" and password == "testpassword":
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.post("/imports/patients/{postal_code}", response_model=dict)
def fetch_and_store_patients_by_postal_code(
    postal_code: str, 
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Fetch patient data from the external API and store it in the database
    """
    url = f"https://hapi.fhir.org/baseR5/Patient?address-postalcode={postal_code}"
    params = {"address-postalcode": postal_code}
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    saved_patient_ids = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})

        patient_id = resource.get("id")
        name = " ".join(resource.get("name", [{}])[0].get("given", [])) + " " + resource.get("name", [{}])[0].get("family", "")
        gender = resource.get("gender")
        birth_date = resource.get("birthDate")

        patient = Patient(
            patient_id=patient_id,
            first_name=name,
            gender=gender,
            birth_date=birth_date,
        )
        session.add(patient)
        saved_patient_ids.append(patient.patient_id) # Flagging this as if there is a failure on commit, order of operations check

    session.commit()

    return {
        "message": f"Patients from postal code {postal_code} processed successfully.",
        "total_saved": len(saved_patient_ids),
        "saved_patient_ids": saved_patient_ids
    }
 

@app.post("/imports/observations/{patient_id}", response_model=dict)
def fetch_and_store_first_observation(
    patient_id: str, 
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Fetch the first observation data for a given patient from the external API and store the resourceType and status.
    """
    url = f"https://hapi.fhir.org/baseR5/Observation"
    params = {"subject": f"Patient/{patient_id}"}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data.get("total", 0) == 0 or "entry" not in data:
        return {"message": f"No observations found for patient {patient_id}."}

    # Process only the first entry
    first_entry = data["entry"][0]
    resource = first_entry.get("resource", {})

    observation_id = resource.get("id", "")
    resource_type = resource.get("resourceType", "unknown")
    status = resource.get("status", "unknown")

    observation = Observation(
        patient_id=patient_id,
        resource_type=resource_type,
        status=status,
    )
    session.add(observation)
    session.commit()
    session.refresh(observation)

    return {
        "message": f"First observation for patient {patient_id} processed successfully.",
        "saved_observation_id": observation.id,
    }



@app.get("/patients/search", response_model=List[Patient])
def search_patients(
    patient_id: Optional[str] = None,
    first_name: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Search for patients by `patient_id` and/or `first_name`.
    If both are provided, results must match both filters.
    """
    if not patient_id and not first_name:
        raise HTTPException(status_code=400, detail="Either 'patient_id' or 'first_name' must be provided.")

    query = select(Patient)
    if patient_id and first_name:
        query = query.where(and_(Patient.patient_id == patient_id, Patient.first_name == first_name))
    elif patient_id:
        query = query.where(Patient.patient_id == patient_id)
    elif first_name:
        query = query.where(Patient.first_name == first_name)

    patients = session.exec(query).all()
    if not patients:
        raise HTTPException(status_code=404, detail="No matching patients found.")

    return patients


@app.get("/observations/search", response_model=List[Observation])
def search_observations(
    patient_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Search for observations by `patient_id`.
    If no `patient_id` is provided, return all observations.
    """
    query = select(Observation)
    if patient_id:
        query = query.where(Observation.patient_id == patient_id)

    observations = session.exec(query).all()
    if not observations:
        raise HTTPException(status_code=404, detail="No matching observations found.")

    return observations

