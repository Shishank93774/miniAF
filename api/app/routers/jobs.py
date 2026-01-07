from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from common.db.models import Job, JobRun
from api.app.schemas import JobCreate, JobResponse, JobRunResponse, JobWithRecentRunsResponse
from api.app.deps import get_db


router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=JobResponse)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = Job(
        name=payload.name,
        schedule=payload.schedule,
        execution_time_sec=payload.execution_time_sec,
        failure_probability=payload.failure_probability,
        max_retries=payload.max_retries,
        retry_delay_sec=payload.retry_delay_sec,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job

@router.get("", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).all()

@router.get("/{job_id}", response_model=JobWithRecentRunsResponse)
def get_job_with_recent_runs(job_id: int, db: Session = Depends(get_db)):
    job = db.execute(
        select(Job).where(Job.id == job_id)
    ).scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_runs = db.execute(
        select(JobRun)
        .where(JobRun.job_id == job_id)
        .order_by(desc(JobRun.scheduled_time))
        .limit(10)
    ).scalars().all()

    return JobWithRecentRunsResponse(
        **job.__dict__,
        recent_runs=job_runs
    )

@router.get("/{job_id}/runs", response_model=list[JobRunResponse])
def list_job_runs(job_id: int, db: Session = Depends(get_db)):
    job_exists = db.execute(
        select(Job.id).where(Job.id == job_id)
    ).scalar_one_or_none()

    if not job_exists:
        raise HTTPException(status_code=404, detail="Job not found")

    job_runs = db.execute(
        select(JobRun)
        .where(JobRun.job_id == job_id)
        .order_by(desc(JobRun.scheduled_time))
    ).scalars().all()

    return job_runs
