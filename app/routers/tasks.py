from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import get_current_active_user
from app.services.assignment_service import find_best_assignee

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = models.Task(**task_data.model_dump(), creator_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/", response_model=List[schemas.TaskOut])
def list_tasks(
    task_status: Optional[models.TaskStatus] = None,
    priority: Optional[models.TaskPriority] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    query = db.query(models.Task)
    if task_status:
        query = query.filter(models.Task.status == task_status)
    if priority:
        query = query.filter(models.Task.priority == priority)
    return query.all()


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    task_data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.id != task.creator_id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    for field, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.id != task.creator_id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    db.delete(task)
    db.commit()


@router.post("/{task_id}/auto-assign", response_model=schemas.AutoAssignResult)
def auto_assign_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != models.TaskStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending tasks can be auto-assigned")

    best_user, score = find_best_assignee(task, db)

    if not best_user:
        raise HTTPException(status_code=404, detail="No suitable assignee found")

    task.assignee_id = best_user.id
    task.status = models.TaskStatus.in_progress

    assignment = models.Assignment(
        task_id=task.id,
        user_id=best_user.id,
        notes=f"Auto-assigned. Score: {score:.2f}",
    )
    db.add(assignment)
    db.commit()
    db.refresh(task)

    return schemas.AutoAssignResult(
        task_id=task.id,
        assigned_to=schemas.UserOut.model_validate(best_user),
        score=score,
        message=f"Task assigned to {best_user.username} with score {score:.2f}",
    )
