import pytest
import pytest_asyncio
from httpx import AsyncClient, HTTPStatusError, ASGITransport
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import create_engine as raw_engine
from sqlalchemy import text
from unittest.mock import AsyncMock, patch
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


@pytest_asyncio.fixture
async def client(session):
    """
    Provide an async test client with the session override.
    """
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def token(client):
    """
    Obtain a valid token for testing protected endpoints.
    """
    response = await client.post("/token", data={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    return response.json()["access_token"]


# Core Functional Tests

# Had to create this as a custom class for the async testing
class MockResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        # Synchronous method to match httpx.Response behavior
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPStatusError("HTTP error", request=None, response=None)


@pytest.mark.asyncio
async def test_import_patients_success(client, session, token):
    mock_response_data = {
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

    async def mock_get(*args, **kwargs):
        return MockResponse(status_code=200, json_data=mock_response_data)

    # Patch httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/imports/patients/02718", headers=headers)
        assert response.status_code == 200
        assert response.json()["total_saved"] == 1

        # Validate the database logic
        patients = session.exec(select(Patient)).all()
        assert len(patients) == 1
        assert patients[0].patient_id == "1419"
        assert patients[0].first_name == "John"  # Ensure only the first name is stored



@pytest.mark.asyncio
async def test_import_observations_success(client, session, token):
    mock_response_data = {
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

    async def mock_get(*args, **kwargs):
        return MockResponse(status_code=200, json_data=mock_response_data)

    # Patch httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/imports/observations/1419", headers=headers)
        assert response.status_code == 200
        assert "saved_observation_id" in response.json()

        observations = session.exec(select(Observation)).all()
        assert len(observations) == 1
        assert observations[0].patient_id == "1419"



@pytest.mark.asyncio
async def test_search_patients_by_id(client, session, token):
    session.add(Patient(patient_id="1419", first_name="John", gender="male", birth_date="1990-01-01"))
    session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/patients/search?patient_id=1419", headers=headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_id"] == "1419"
    assert results[0]["first_name"] == "John"


@pytest.mark.asyncio
async def test_search_patients_no_filters(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/patients/search", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Either 'patient_id' or 'first_name' must be provided."


@pytest.mark.asyncio
async def test_search_observations_by_patient_id(client, session, token):
    session.add(Observation(patient_id="1419", resource_type="Observation", status="final"))
    session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/observations/search?patient_id=1419", headers=headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["patient_id"] == "1419"


@pytest.mark.asyncio
async def test_search_observations_no_matches(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/observations/search?patient_id=9999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching observations found."


# Edge Case Tests

@pytest.mark.asyncio
async def test_invalid_token(client):
    headers = {"Authorization": "Bearer invalid_token"}
    response = await client.get("/patients/search?patient_id=1419", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_no_token_provided(client):
    response = await client.get("/patients/search?patient_id=1419")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_invalid_credentials_for_token(client):
    response = await client.post("/token", data={"username": "wronguser", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_nonexistent_patient_search(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/patients/search?patient_id=nonexistent", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching patients found."


@pytest.mark.asyncio
async def test_nonexistent_observation_search(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/observations/search?patient_id=nonexistent", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No matching observations found."
