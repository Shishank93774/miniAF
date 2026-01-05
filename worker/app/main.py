import os
import random
import time

from datetime import datetime, timezone, timedelta
from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

UTC = timezone.utc

def get_worker_id():
    # Docker sets HOSTNAME automatically
    hostname = os.getenv("HOSTNAME")
    if hostname:
        return hostname

    # Local fallback
    return os.getenv("WORKER_ID", "local-worker")

WORKER_ID = get_worker_id()
TIME_TO_WAIT_SEC = 1

class JobFailureRandomException(Exception):
    pass


def claim_job(db):
    now = datetime.now(UTC)

    with db.begin():  # <-- starts a transaction
        job_run = (
            db.execute(
                select(JobRun)
                .where(
                    JobRun.status.in_([JobRunStatus.PENDING, JobRunStatus.RETRY]),
                    JobRun.scheduled_time <= now,
                )
                .order_by(JobRun.scheduled_time)
                .with_for_update(skip_locked=True)  # ⭐ KEY LINE
                .limit(1)
            )
            .scalar_one_or_none()
        )

        if job_run is None:
            return None

        job_run.status = JobRunStatus.RUNNING
        job_run.started_at = now
        job_run.worker_id = WORKER_ID

        return job_run  # commit happens automatically here


def execute_job_run(db, job, job_run):
    rnd = random.random()
    print("Random:", rnd, "Failure Probability:", job.failure_probability)

    if rnd < job.failure_probability:
        raise JobFailureRandomException()

    time.sleep(job.execution_time_sec)

    job_run.status = JobRunStatus.SUCCESS
    job_run.finished_at = datetime.now(UTC)
    db.commit()

    print("Job:", job.name, "completed successfully")


wait_for_db()

while True:
    db = SessionLocal()

    try:
        job_run = claim_job(db)

        if job_run is None:
            print("No pending job runs found, waiting...")
            time.sleep(10)
            continue

        job = db.execute(
            select(Job).where(Job.id == job_run.job_id)
        ).scalar_one()

        print("Executing job:", job.name)

        try:
            execute_job_run(db, job, job_run)

        except JobFailureRandomException:
            job_run.attempt_number += 1
            job_run.finished_at = datetime.now(UTC)

            if job_run.attempt_number <= job.max_retries:
                job_run.status = JobRunStatus.RETRY
                job_run.scheduled_time = datetime.now(UTC) + timedelta(seconds=job.retry_delay_sec)
                print("Retrying job:", job.name)
            else:
                job_run.status = JobRunStatus.FAILED
                print("Job failed permanently:", job.name)

            db.commit()

        print("\n")

    except ProgrammingError:
        db.rollback()
        print("DB not ready, retrying...")
        time.sleep(TIME_TO_WAIT_SEC)

    finally:
        db.close()

    time.sleep(TIME_TO_WAIT_SEC)
