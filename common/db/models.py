import enum
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime,
    Enum, ForeignKey, JSON, UniqueConstraint, CheckConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import text

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
    failure_probability = Column(Float, nullable=False)

    max_retries = Column(Integer, default=0, server_default=text("0"))
    retry_delay_sec = Column(Integer, default=5, server_default=text("5"))

    is_active = Column(Boolean, default=True, server_default=text("true"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    runs = relationship("JobRun", back_populates="job")

    __table_args__ = (
        CheckConstraint("max_retries >= 0", name="ck_job_max_retries"),
        CheckConstraint("retry_delay_sec >= 0", name="ck_job_retry_delay_sec"),
        CheckConstraint("execution_time_sec >= 0", name="ck_job_execution_time_sec"),
        CheckConstraint("failure_probability >= 0 and failure_probability <= 1", name="ck_job_failure_probability")
    )

    __repr__ = lambda self: f"Job(id={self.id}, name={self.name}, schedule={self.schedule}, execution_time_sec={self.execution_time_sec}, failure_probability={self.failure_probability}, max_retries={self.max_retries}, retry_delay_sec={self.retry_delay_sec}, is_active={self.is_active}, created_at={self.created_at}, updated_at={self.updated_at})"


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True)

    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    scheduled_time = Column(DateTime(timezone=True), nullable=False)

    status = Column(Enum(JobRunStatus), nullable=False)

    attempt_number = Column(Integer, default=0, server_default=text("0"))

    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    error_message = Column(String)
    worker_id = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="runs")

    __table_args__ = (
        UniqueConstraint("job_id", "scheduled_time", name="uq_job_schedule"),
    )

    __repr__ = lambda self: f"JobRun(id={self.id}, job_id={self.job_id}, scheduled_time={self.scheduled_time}, status={self.status}, attempt_number={self.attempt_number}, started_at={self.started_at}, finished_at={self.finished_at}, error_message={self.error_message}, worker_id={self.worker_id}, created_at={self.created_at})"
