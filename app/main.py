import os
import httpx
from typing import Optional, List
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
async def login(username: str = Form(...), password: str = Form(...)):
    """
    Login endpoint to generate JWT tokens.
    """
    if username == "testuser" and password == "testpassword":
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.post("/imports/patients/{postal_code}", response_model=dict)
async def fetch_and_store_patients_by_postal_code(
    postal_code: str,
    session: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Fetch patient data from the external API and store them in the database.
    Then, fetch the first observation for each patient and store it.
    """
    # Fetch patients from the FHIR API
    patient_url = f"https://hapi.fhir.org/baseR5/Patient?address-postalcode={postal_code}"
    async with httpx.AsyncClient() as client:
        response = await client.get(patient_url)
        response.raise_for_status()
        patients_data = response.json()

    saved_patient_ids = []
    for entry in patients_data.get("entry", []):
        resource = entry.get("resource", {})
        patient_id = resource.get("id")
        given_names = resource.get("name", [{}])[0].get("given", [])
        first_name = given_names[0] if given_names else ""
        gender = resource.get("gender")
        birth_date = resource.get("birthDate")

        # Avoid duplicate patient entries
        existing_patient = session.exec(
            select(Patient).where(Patient.patient_id == patient_id)
        ).first()

        if not existing_patient:
            patient = Patient(
                patient_id=patient_id,
                first_name=first_name.strip(),
                gender=gender,
                birth_date=birth_date,
            )
            session.add(patient)
            session.commit()  # Save to get the patient ID for relationships
            session.refresh(patient)
            saved_patient_ids.append(patient.id)

    # Fetch and store observations for each new patient
    for patient_id in saved_patient_ids:
        await fetch_and_store_first_observation(patient_id, session)

    return {
        "message": f"Patients from postal code {postal_code} processed successfully.",
        "total_saved": len(saved_patient_ids),
        "saved_patient_ids": saved_patient_ids,
    }


async def fetch_and_store_first_observation(patient_id: int, session: Session):
    """
    Fetch the first observation data for a given patient from the external API and store it.
    If no observation is found, insert an empty observation record.
    """
    patient = session.get(Patient, patient_id)
    if not patient:
        print(f"Patient with ID {patient_id} not found in the database.")
        return {"message": f"Patient with ID {patient_id} not found."}

    # Fetch observations for the patient
    observation_url = "https://hapi.fhir.org/baseR5/Observation"
    params = {"subject": f"Patient/{patient.patient_id}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(observation_url, params=params)
        response.raise_for_status()
        observations_data = response.json()

    print(f"FHIR API response for patient {patient.patient_id}: {observations_data}")

    # Default values for the observation
    resource_type = "unknown"
    status = "empty"

    # Check if observations exist
    if observations_data.get("total", 0) > 0 and "entry" in observations_data:
        # Process the first observation if available
        first_entry = observations_data["entry"][0]
        resource = first_entry.get("resource", {})
        resource_type = resource.get("resourceType", "unknown")
        status = resource.get("status", "unknown")
    else:
        print(f"No observations found for patient {patient.patient_id}. Inserting default observation.")

    # Insert the observation (either real or default)
    observation = Observation(
        patient_id=patient.id,  # Link observation to the patient
        resource_type=resource_type,
        status=status,
    )
    session.add(observation)
    session.commit()
    session.refresh(observation)
    print(f"Stored observation for patient {patient.patient_id}: {observation}")




@app.get("/patients/search", response_model=List[Patient])
async def search_patients(
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
async def search_observations(
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
