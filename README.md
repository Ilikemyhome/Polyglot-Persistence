# Polyglot Persistence Assignment: PostgreSQL vs. MongoDB

This project implements a **Task Management Domain (Projects & Tasks)** using a **Polyglot Persistence** architecture, comparing a relational SQL database (**PostgreSQL**) with a document-based NoSQL database (**MongoDB**), powered by a **FastAPI** backend.

---

## 1. Domain Description & Schemas

### Domain Overview
The application manages **Projects**, where each project can contain multiple **Tasks**. 
* **Relational Model (PostgreSQL):** Uses normalized 3NF tables with foreign key constraints and `ON DELETE CASCADE` rules to enforce referential integrity.
* **NoSQL Model (MongoDB):** Uses a denormalized document model where tasks are embedded directly as an array inside the parent project document to enable single-query reads.

---

### PostgreSQL (SQL) Schema & ASCII ER Diagram

+-----------------------+       +------------------------------------+
|       PROJECTS        |       |               TASKS                |
+-----------------------+       +------------------------------------+
| PK id (SERIAL)        |<------+ FK project_id (INTEGER)            |
|    name (VARCHAR)     |       | PK id (SERIAL)                     |
|    description (TEXT) |       |    title (VARCHAR)                 |
+-----------------------+       |    status (VARCHAR)                |
                                +------------------------------------+

## Setup & Installation

1. Make sure uv is intalled and added to your path

pip install uv

2. Sync Dependencies

uv sync

3. Configure Environment Variables

Create a .env file in the root directory of the project and add your connection strings:

database_url=postgresql+psycopg://postgres:postgres@localhost:5432/polyglot_tasks
mongo_uri=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority


(Ensure .env is listed in your .gitignore file so credentials are never committed to version control).

4. Initialize the PostgreSQL Database

Log into PostgreSQL (psql -U postgres -W) and create the database:

CREATE DATABASE polyglot_tasks;


(Tables and indexes will be created automatically upon server startup, or can be applied directly via schema.sql).

uv sync Running the Application

Start the FastAPI development server using Uvicorn:

uv run uvicorn polyglot_persistence.main:app --reload


Once running, open your browser and navigate to the interactive Swagger UI:

Swagger UI: http://127.0.0.1:8000/docs

## Web Project Testing & QA Checklist (Swagger UI)

Use the interactive endpoints at http://127.0.0.1:8000/docs to verify CRUD operations, referential integrity, and document embedding.

Part 1: Relational (PostgreSQL) QA Tests

1. Create & Read (Joined Dataset)

Endpoint: POST /sql/projects

Payload:

{
  "name": "E-Commerce Platform Launch",
  "description": "Relational database schema verification",
  "tasks": [
    {
      "title": "Configure PostgreSQL indexes",
      "status": "completed"
    },
    {
      "title": "Verify foreign key constraints",
      "status": "in_progress"
    }
  ]
}


Verification: Copy the returned id and execute GET /sql/projects  to confirm PostgreSQL joins the parent project and child tasks cleanly.

2. Negative Constraint Test (Orphaned Record Protection)

Endpoint: POST /sql/projects/{project_id}/tasks (if implemented) or attempt to insert a task referencing a non-existent project_id such as 999999.

Payload:

{
  "title": "Orphan Task Test",
  "status": "pending"
}


Expected Result: PostgreSQL rejects the request with a 400 Bad Request / foreign key integrity violation error, confirming orphaned records cannot exist.

3. Delete & Cascade Cleanup

Endpoint: DELETE /sql/projects/{project_id}

Verification: Execute with your valid project id. Receive a 204 No Content status and verify via GET /sql/projects that both the parent project and all associated child tasks were removed via ON DELETE CASCADE.

Part 2: NoSQL (MongoDB) QA Tests

1. Create & Read (Single-Query Document)

Endpoint: POST /nosql/projects

Payload:

{
  "name": "Q4 Marketing Campaign",
  "description": "MongoDB denormalized document test",
  "tasks": [
    {
      "title": "Design social media assets",
      "status": "pending"
    },
    {
      "title": "Launch analytics dashboard",
      "status": "in_progress"
    }
  ]
}


Verification: Execute GET /nosql/projects and verify that the entire project and its embedded task array are retrieved in a single query round-trip without joins.

2. Document Deletion

Endpoint: DELETE /nosql/projects/{project_id}

Verification: Paste the MongoDB string id (ObjectId), execute, and confirm a 204 No Content response with clean state removal.

## AI Disclosure & Prompt Appendix
AI Tools Used: Gemini 

Promp used 
Act as a senior database architect. I am designing a backend feature for a Task Management System with Projects and Tasks.

I need to implement polyglot persistence to compare relational (SQL) and non-relational (NoSQL) modeling:

Relational Schema (PostgreSQL):

Create normalized (3NF) tables for projects and tasks with primary keys, foreign keys (project_id), and ON DELETE CASCADE referential integrity.

NoSQL Schema (MongoDB):

Design an idiomatic document model for the exact same domain.

Optimize for reading a complete project with its associated tasks in a single query using an embedded tasks array inside the project document.

Working Application / CRUD Service (FastAPI / Python):

Implement basic CRUD endpoints for both databases using SQLAlchemy and PyMongo:

Create a record/document with nested tasks

Read by ID and list all records (including SQL JOINs and MongoDB single-query retrieval)

Delete a record (testing SQL ON DELETE CASCADE)

A negative constraint test route to catch orphaned records and return a 400 Bad Request foreign key violation.

Environment configuration using pydantic-settings and a root-level .env file for database and MongoDB connection strings.

Provide the SQL DDL statements, NoSQL schema/JSON structure, database connection logic, and FastAPI CRUD controller code.

Summary of AI vs. Manual Validation:

Correctly Produced: Pydantic settings integration, SQLAlchemy model setups, PyMongo CRUD route logic, and Swagger payloads.

Manual Adjustments: Fixed local connection strings and port configurations for MongoDB Atlas and local PostgreSQL credentials.
