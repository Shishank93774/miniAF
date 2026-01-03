import enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Enum, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base

class JobRunStatus(enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    schedule = Column(String, nullable=False)

    execution_time_sec = Column(Integer, nullable=False)
    failure_probability = Column(Integer, nullable=False)

    max_retries = Column(Integer, default=0)
    retry_delay_sec = Column(Integer, default=5)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    runs = relationship("JobRun", back_populates="job")


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True)

    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    scheduled_time = Column(DateTime(timezone=True), nullable=False)

    status = Column(Enum(JobRunStatus), nullable=False)

    attempt_number = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    error_message = Column(String)
    worker_id = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="runs")

    __table_args__ = (
        UniqueConstraint("job_id", "scheduled_time", name="uq_job_schedule"),
    )
