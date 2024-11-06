import requests

from typing import Union

from fastapi import FastAPI


app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.get("/patients/{postal_code}")
def get_patients_by_postal_code(postal_code: str):
    url = f"https://hapi.fhir.org/baseR5/Patient?address-postalcode={postal_code}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
