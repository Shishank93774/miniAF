from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common.db.models import Job
from api.app.schemas import JobCreate, JobResponse
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

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
