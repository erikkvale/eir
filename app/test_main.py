import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import create_engine as raw_engine
from sqlalchemy import text
from unittest.mock import patch
from app.main import app, get_session, Patient, Observation

MAIN_DATABASE_URL = "postgresql://postgres:postgres@db:5432/postgres"
TEST_DATABASE_URL = "postgresql://postgres:postgres@db:5432/test_eir_db"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Create and drop the test database.
    """
    engine = raw_engine(MAIN_DATABASE_URL)
    connection = engine.connect()
    connection.execution_options(isolation_level="AUTOCOMMIT")

    # Disconnect active connections before dropping the database
    connection.execute(
        text("SELECT pg_terminate_backend(pg_stat_activity.pid) "
             "FROM pg_stat_activity "
             "WHERE pg_stat_activity.datname = 'test_eir_db' "
             "  AND pid <> pg_backend_pid();")
    )
    
    # Drop and recreate the test database
    connection.execute(text("DROP DATABASE IF EXISTS test_eir_db;"))
    connection.execute(text("CREATE DATABASE test_eir_db;"))
    connection.close()

    yield 

    # Drop the test database after tests complete
    connection = engine.connect()
    connection.execution_options(isolation_level="AUTOCOMMIT")
    connection.execute(
        text("SELECT pg_terminate_backend(pg_stat_activity.pid) "
             "FROM pg_stat_activity "
             "WHERE pg_stat_activity.datname = 'test_eir_db' "
             "  AND pid <> pg_backend_pid();")
    )
    connection.execute(text("DROP DATABASE IF EXISTS test_eir_db;"))
    connection.close()


@pytest.fixture(name="session")
def session_fixture():
    """
    Provide a clean database session for each test.
    """
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session):
    """
    Provide a test client with the session override.
    """
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


@pytest.fixture
def token(client):
    """
    Obtain a valid token for testing protected endpoints.
    """
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_import_patients_success(client, session, token):
    mock_response = {
        "entry": [
            {
                "resource": {
                    "id": "1419",
                    "name": [{"given": ["John"], "family": "Doe"}],
                    "gender": "male",
                    "birthDate": "1990-01-01",
                }
            }
        ]
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/imports/patients/02718", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_saved"] == 1

        patients = session.exec(select(Patient)).all()
        assert len(patients) == 1
        assert patients[0].patient_id == "1419"


def test_import_observations_success(client, session, token):
    mock_response = {
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                }
            }
        ],
        "total": 1,
    }

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/imports/observations/1419", headers=headers)
        assert response.status_code == 200
        assert "saved_observation_id" in response.json()

        observations = session.exec(select(Observation)).all()
        assert len(observations) == 1
        assert observations[0].patient_id == "1419"


def test_search_patients_by_id(client, session, token):
    session.add(Patient(patient_id="1419", first_name="John", gender="male", birth_date="1990-01-01"))
    session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/patients/search?patient_id=1419", headers=headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_id"] == "1419"


def test_search_patients_no_filters(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/patients/search", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Either 'patient_id' or 'first_name' must be provided."


def test_search_observations_by_patient_id(client, session, token):
    session.add(Observation(patient_id="1419", resource_type="Observation", status="final"))
    session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/observations/search?patient_id=1419", headers=headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_id"] == "1419"


def test_search_observations_no_matches(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/observations/search?patient_id=9999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching observations found."


# Additional token tests

def test_invalid_token(client):
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/patients/search?patient_id=1419", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"

def test_no_token_provided(client):
    response = client.get("/patients/search?patient_id=1419")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_invalid_credentials_for_token(client):
    response = client.post("/token", data={"username": "wronguser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"

def test_nonexistent_patient_search(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/patients/search?patient_id=nonexistent", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching patients found."

def test_nonexistent_observation_search(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/observations/search?patient_id=nonexistent", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching observations found."





