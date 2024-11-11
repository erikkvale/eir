
# Eir

## About

Eir is a modern FastAPI-based application designed to interact with FHIR (Fast Healthcare Interoperability Resources) APIs and store the results in a PostgreSQL database.

The name "Eir" originates from Norse mythology, where Eir is a goddess or valkyrie associated with healing and medical skill. Inspired by this, the application aims to bring healing efficiency to healthcare data management.

---

## Features Checklist

Here’s what has been implemented so far:

???+ bug

    No explicit relationship between patient and observation tables exists as interpreted from the assessment
    write-up. Single zip code (02718) and patient id (1419) were specified. Would like to clarify on review and may submit changes on another branch in prep for what I would assume should be related and so a patient's observations can be retrieved via foreign key.

- **Containerized Deployment**  
  ✅ Configured Docker Compose for deploying the FastAPI app and PostgreSQL database.
  
- **FastAPI Endpoints**  
  ✅ Built RESTful endpoints to:
    - Fetch and store patients by postal code.
    - Fetch and store the first observation for a patient.
    - Search for patients by ID or first name.
    - Search for observations by patient ID.
    
- **Database Setup**  
  ✅ Configured PostgreSQL with SQLModel for ORM-based database interaction.
  
- **Automated Testing**  
  ✅ Implemented pytest with a dedicated test database setup for comprehensive test coverage.
  
- **Makefile for Commands**  
  ✅ Simplified development and deployment with Makefile targets.
  
- **Documentation**  
  ✅ Beautiful and functional docs built using MkDocs-Material.

- **CI Pipeline with GitHub Actions**  
  ✅ Build and test  
  ✅ Docs deployment

---

## Quickstart Guide

### Prerequisites

!!! Info
    - Docker and Docker Compose installed.
    - Python 3.11+ (for local testing or development outside Docker).

### Running the Application

1. Clone the Repository  
  ```
  git clone https://github.com/erikkvale/eir.git && cd eir
  ```

2. Start the Application, use the following Makefile target to build and run the application:  
  ```
  make run-app
  ```

- Access the Application, once running, the FastAPI app will be available at `http://localhost:8080`.

#### Explore the API
FastAPI provides interactive API documentation:

 - Swagger UI: `http://localhost:8080/docs`
 - ReDoc: `http://localhost:8080/redoc`

---

## Running Tests

To run the test suite within the Docker Compose environment:
```bash
make run-tests
```
This will spin up the required containers, execute the tests, and shut everything down afterward.

---

## Local Documentation Development

Eir’s documentation is built with MkDocs-Material.

To serve the documentation locally:
```bash
make serve-docs
```

!!! note
    Running `make run-app` also serves up the document server, alongside the app and db, if you only need the documentation server use `serve-docs`

The documentation will be available at `http://localhost:8000`.

---

## Makefile Targets

| Target         | Description                              |
|----------------|------------------------------------------|
| `run-app`      | Build and run the application with Docker.   |
| `run-tests`    | Run the pytest suite in Docker containers. |
| `serve-docs`   | Serve the MkDocs-Material documentation.     |

---

## Related Links

- [MkDocs-Material Documentation](https://squidfunk.github.io/mkdocs-material/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FHIR API Specification](https://www.hl7.org/fhir/overview.html)

---

## Looking for Help?

If you encounter any issues or need assistance, feel free to check the issues section of the repository or contact the maintainers.
