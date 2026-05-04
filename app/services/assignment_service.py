from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app import models

PRIORITY_WEIGHTS: dict = {
    models.TaskPriority.low: 1.0,
    models.TaskPriority.medium: 1.5,
    models.TaskPriority.high: 2.0,
    models.TaskPriority.critical: 3.0,
}


def calculate_workload(user: models.User, db: Session) -> float:
    active_tasks = (
        db.query(models.Task)
        .filter(
            models.Task.assignee_id == user.id,
            models.Task.status == models.TaskStatus.in_progress,
        )
        .all()
    )
    return sum(PRIORITY_WEIGHTS.get(task.priority, 1.5) for task in active_tasks)


def find_best_assignee(
    task: models.Task, db: Session
) -> Tuple[Optional[models.User], Optional[float]]:
    candidates = (
        db.query(models.User)
        .filter(
            models.User.is_active == True,
            models.User.role == models.UserRole.employee,
            models.User.qualification_level >= task.required_qualification,
        )
        .all()
    )

    if not candidates:
        return None, None

    best_user: Optional[models.User] = None
    best_score = float("inf")

    for user in candidates:
        workload = calculate_workload(user, db)
        qualification_bonus = user.qualification_level - task.required_qualification + 1
        score = workload / qualification_bonus

        if score < best_score:
            best_score = score
            best_user = user

    return best_user, best_score
