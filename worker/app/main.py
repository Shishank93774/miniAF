import os
import time
import random
import threading
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db

UTC = timezone.utc
HEARTBEAT_INTERVAL_SEC = 5
POLL_INTERVAL_SEC = 2


def get_worker_id():
    return os.getenv("HOSTNAME") or os.getenv("WORKER_ID", "local-worker")


WORKER_ID = get_worker_id()


class JobFailureRandomException(Exception):
    pass


def heartbeat_loop(job_run_id: int, stop_event: threading.Event):
    """Periodically updates heartbeat for a running job_run."""
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            db.execute(
                select(JobRun)
                .where(JobRun.id == job_run_id)
                .with_for_update()
            ).scalar_one().last_heartbeat_at = datetime.now(UTC)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        stop_event.wait(HEARTBEAT_INTERVAL_SEC)


def claim_job(db):
    now = datetime.now(UTC)

    with db.begin():
        job_run = (
            db.execute(
                select(JobRun)
                .where(
                    JobRun.status.in_([JobRunStatus.PENDING, JobRunStatus.RETRY]),
                    JobRun.scheduled_time <= now,
                )
                .order_by(JobRun.scheduled_time)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            .scalar_one_or_none()
        )

        if not job_run:
            return None

        job_run.status = JobRunStatus.RUNNING
        job_run.started_at = now
        job_run.last_heartbeat_at = now
        job_run.worker_id = WORKER_ID

        return job_run


def execute_job(db, job: Job, job_run: JobRun):
    rnd = random.random()
    print(f"[{WORKER_ID}] Executing {job.name} | rnd={rnd}")

    if rnd < job.failure_probability:
        raise JobFailureRandomException()

    time.sleep(job.execution_time_sec)


wait_for_db()
print(f"[{WORKER_ID}] Worker started")

while True:
    db = SessionLocal()
    try:
        job_run = claim_job(db)

        if not job_run:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        job = db.execute(
            select(Job).where(Job.id == job_run.job_id)
        ).scalar_one()

        stop_event = threading.Event()
        hb_thread = threading.Thread(
            target=heartbeat_loop,
            args=(job_run.id, stop_event),
            daemon=True,
        )
        hb_thread.start()

        try:
            execute_job(db, job, job_run)

            job_run.status = JobRunStatus.SUCCESS
            job_run.finished_at = datetime.now(UTC)
            db.commit()

            print(f"[{WORKER_ID}] Job {job.name} SUCCESS")

        except JobFailureRandomException:
            job_run.attempt_number += 1
            job_run.finished_at = datetime.now(UTC)

            if job_run.attempt_number <= job.max_retries:
                job_run.status = JobRunStatus.RETRY
                job_run.scheduled_time = datetime.now(UTC) + timedelta(
                    seconds=job.retry_delay_sec
                )
                print(f"[{WORKER_ID}] Job {job.name} RETRY")
            else:
                job_run.status = JobRunStatus.FAILED
                print(f"[{WORKER_ID}] Job {job.name} FAILED")

            db.commit()

        finally:
            stop_event.set()

    except ProgrammingError:
        db.rollback()
        time.sleep(2)
    finally:
        db.close()
