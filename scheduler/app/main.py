import time
from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError, ProgrammingError
from croniter import croniter
from datetime import datetime, timezone

UTC = timezone.utc

def add_job_run_to_db(db, job_id, scheduled_time):
    job_run = JobRun(job_id=job_id, scheduled_time=scheduled_time, status=JobRunStatus.PENDING, attempt_number=0)
    try:
        db.add(job_run)
        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception as e:
        print(f"Error adding job run to database: {e}")


wait_for_db()
while True:
    db = SessionLocal()

    try:
        jobs = db.execute(select(Job).where(Job.is_active == True)).scalars().all()
    except ProgrammingError as e:
        print("DB schema not ready yet, retrying...")
        db.rollback()
        time.sleep(5)
        continue

    try:
        query = select(Job).where(Job.is_active == True)
        result = db.execute(query)

        jobs = result.scalars().all()
        print("Printing Jobs:")
        for job in jobs:
            last_run_query = select(JobRun).where(JobRun.job_id == job.id).order_by(desc(JobRun.scheduled_time)).limit(1)
            last_run_job = db.execute(last_run_query).scalar_one_or_none()

            if last_run_job is None:
                base_run_time = job.created_at
            else:
                base_run_time = last_run_job.scheduled_time
            next_run_time = croniter(job.schedule, base_run_time).get_next(datetime)
            next_run_time_utc = next_run_time.astimezone(UTC)

            if next_run_time_utc <= datetime.now(tz=UTC):
                print("Job:", job.name, "\nNext Run:", next_run_time, "is due.")
                add_job_run_to_db(db, job.id, next_run_time)
            else:
                print("Job:", job.name, "\nNext Run:", next_run_time, "is not due.")

    except Exception as e:
        print(f"Error connecting to database: {e}")
    finally:
        db.close()

    time.sleep(10)
