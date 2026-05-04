from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models import TaskPriority, TaskStatus, UserRole


class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: UserRole = UserRole.employee
    qualification_level: int = 1

    @field_validator("qualification_level")
    @classmethod
    def validate_qualification(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("qualification_level must be between 1 and 5")
        return v


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    qualification_level: Optional[int] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    required_qualification: int = 1
    deadline: Optional[datetime] = None

    @field_validator("required_qualification")
    @classmethod
    def validate_required_qualification(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("required_qualification must be between 1 and 5")
        return v


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    required_qualification: Optional[int] = None
    deadline: Optional[datetime] = None
    assignee_id: Optional[int] = None


class TaskOut(TaskBase):
    id: int
    status: TaskStatus
    created_at: datetime
    creator_id: int
    assignee_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentOut(BaseModel):
    id: int
    task_id: int
    user_id: int
    assigned_at: datetime
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class AutoAssignResult(BaseModel):
    task_id: int
    assigned_to: UserOut
    score: float
    message: str
