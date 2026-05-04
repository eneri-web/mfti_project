from fastapi import FastAPI

from app.database import Base, engine
from app.routers import assignments, auth, tasks, users

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TaskFlow API",
    description="Task management system with automatic executor assignment based on workload and qualification",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(assignments.router)


@app.get("/", tags=["root"])
def root():
    return {"message": "TaskFlow API is running", "docs": "/docs"}
