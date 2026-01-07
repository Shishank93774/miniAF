from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from common.db.models import JobRunStatus


class JobCreate(BaseModel):
    name: str = Field(..., min_length=1)
    schedule: str = Field(..., min_length=1)
    execution_time_sec: int = Field(..., gt=0)
    failure_probability: float = Field(..., ge=0.0, le=1.0)
    max_retries: int = Field(0, ge=0)
    retry_delay_sec: int = Field(0, ge=0)


class JobRunResponse(BaseModel):
    id: int
    job_id: int
    status: JobRunStatus
    scheduled_time: datetime
    attempt_number: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    worker_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    name: str
    schedule: str
    execution_time_sec: int
    failure_probability: float
    max_retries: int
    retry_delay_sec: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobWithRecentRunsResponse(JobResponse):
    recent_runs: List[JobRunResponse]