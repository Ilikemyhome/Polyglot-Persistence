from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    create_engine, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session, selectinload
)
from sqlalchemy.future import select
from pymongo import MongoClient
from pymongo.collection import Collection
from bson import ObjectId
from bson.errors import InvalidId

# Define a Settings class that automatically reads from the .env file
class Settings(BaseSettings):
    postgres_url: str
    mongo_uri: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Initialize settings
settings = Settings()

# --- CONFIGURATION & CONNECTIONS ---
# Change these URLs to match your local PostgreSQL and MongoDB instances
sql_engine = create_engine(settings.postgres_url, echo=False)
mongo_client = MongoClient(settings.mongo_uri)
# SQL Setup

SqlSessionLocal = sessionmaker(bind=sql_engine, autoflush=False, autocommit=False)

class SqlBase(DeclarativeBase):
    pass

class ProjectSQL(SqlBase):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    tasks: Mapped[list["TaskSQL"]] = relationship("TaskSQL", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)

class TaskSQL(SqlBase):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    
    project: Mapped["ProjectSQL"] = relationship("ProjectSQL", back_populates="tasks")

def get_sql_db():
    db = SqlSessionLocal()
    try:
        yield db
    finally:
        db.close()

# NoSQL Setup (MongoDB)
mongo_client = MongoClient(settings.mongo_uri)
mongo_db = mongo_client["polyglot_tasks"]

def get_mongo_collection() -> Collection:
    return mongo_db["projects"]


# --- PYDANTIC SCHEMAS ---
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="pending", max_length=50)

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tasks: list[TaskCreate] = []

class TaskOutSQL(BaseModel):
    id: int
    project_id: int
    title: str
    status: str
    model_config = {"from_attributes": True}

class ProjectOutSQL(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    tasks: list[TaskOutSQL] = []
    model_config = {"from_attributes": True}

class TaskOutNoSQL(BaseModel):
    task_id: str
    title: str
    status: str

class ProjectOutNoSQL(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tasks: list[TaskOutNoSQL] = []


# --- FASTAPI APP ---
app = FastAPI(title="Polyglot Persistence Task Manager", version="1.0.0")

@app.on_event("startup")
def startup_event():
    SqlBase.metadata.create_all(bind=sql_engine)


# --- SQL (POSTGRESQL) ENDPOINTS ---
@app.post("/sql/projects", status_code=status.HTTP_201_CREATED, response_model=ProjectOutSQL)
def create_sql_project(payload: ProjectCreate, db: Session = Depends(get_sql_db)):
    project = ProjectSQL(name=payload.name, description=payload.description)
    for t in payload.tasks:
        project.tasks.append(TaskSQL(title=t.title, status=t.status))
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@app.get("/sql/projects", response_model=list[ProjectOutSQL])
def list_sql_projects(db: Session = Depends(get_sql_db)):
    stmt = select(ProjectSQL).options(selectinload(ProjectSQL.tasks))
    return db.scalars(stmt).all()

@app.get("/sql/projects/{project_id}", response_model=ProjectOutSQL)
def get_sql_project_by_id(project_id: int, db: Session = Depends(get_sql_db)):
    # Query the project and eagerly load its tasks using selectinload
    stmt = select(ProjectSQL).options(selectinload(ProjectSQL.tasks)).where(ProjectSQL.id == project_id)
    project = db.scalars(stmt).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return project

@app.put("/sql/projects/{project_id}", response_model=ProjectOutSQL)
def update_sql_project(project_id: int, payload: ProjectCreate, db: Session = Depends(get_sql_db)):
    project = db.get(ProjectSQL, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.name = payload.name
    project.description = payload.description
    db.commit()
    db.refresh(project)
    return project

@app.delete("/sql/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sql_project(project_id: int, db: Session = Depends(get_sql_db)):
    project = db.get(ProjectSQL, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)  # Triggers ON DELETE CASCADE for child tasks
    db.commit()
    return None

@app.post("/sql/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def add_task_to_sql_project(project_id: int, payload: TaskCreate, db: Session = Depends(get_sql_db)):
    # First, verify if the project actually exists
    project = db.get(ProjectSQL, project_id)
    if not project:
        raise HTTPException(status_code=400, detail="Foreign key violation: Project does not exist")
        
    # If it exists, create and add the task
    task = TaskSQL(title=payload.title, status=payload.status, project_id=project_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"message": "Task added successfully", "task_id": task.id, "project_id": project_id}


# --- NoSQL (MONGODB) ENDPOINTS ---
@app.post("/nosql/projects", status_code=status.HTTP_201_CREATED, response_model=ProjectOutNoSQL)
def create_nosql_project(payload: ProjectCreate, col: Collection = Depends(get_mongo_collection)):
    embedded_tasks = [
        {"task_id": f"t_{i}", "title": t.title, "status": t.status} 
        for i, t in enumerate(payload.tasks)
    ]
    doc = {
        "name": payload.name,
        "description": payload.description,
        "tasks": embedded_tasks
    }
    result = col.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return ProjectOutNoSQL(**doc)

@app.get("/nosql/projects", response_model=list[ProjectOutNoSQL])
def list_nosql_projects(col: Collection = Depends(get_mongo_collection)):
    projects = []
    for doc in col.find():
        doc["id"] = str(doc["_id"])
        projects.append(ProjectOutNoSQL(**doc))
    return projects

@app.put("/nosql/projects/{project_id}", response_model=ProjectOutNoSQL)
def update_nosql_project(project_id: str, payload: ProjectCreate, col: Collection = Depends(get_mongo_collection)):
    try:
        oid = ObjectId(project_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
        
    updated_data = {
        "name": payload.name,
        "description": payload.description,
        "tasks": [{"task_id": f"t_{i}", "title": t.title, "status": t.status} for i, t in enumerate(payload.tasks)]
    }
    
    res = col.find_one_and_update(
        {"_id": oid},
        {"$set": updated_data},
        return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Project not found")
        
    res["id"] = str(res["_id"])
    return ProjectOutNoSQL(**res)

@app.delete("/nosql/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nosql_project(project_id: str, col: Collection = Depends(get_mongo_collection)):
    try:
        oid = ObjectId(project_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
        
    res = col.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return None