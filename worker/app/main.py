import os
import time
import json
import random
import threading
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db
from common.logging.logger import StructuredLogger
from common.redis.client import redis_client

logger = StructuredLogger(
    name="worker",
    logfile="worker.log",
)

def get_worker_id():
    return os.getenv("HOSTNAME") or os.getenv("WORKER_ID", "local-worker")

UTC = timezone.utc
HEARTBEAT_INTERVAL_SEC = 5
POLL_INTERVAL_SEC = 2
WORKER_TTL_SEC = 15
WORKER_ID = get_worker_id()


class JobFailureRandomException(Exception):
    pass


def refresh_worker_presence(current_job_run_id=None):
    redis_client.setex(
        f"worker:{WORKER_ID}",
        WORKER_TTL_SEC,
        json.dumps(
            {
                "worker_id": WORKER_ID,
                "last_seen": datetime.now(UTC).isoformat(),
                "current_job_run_id": current_job_run_id,
            }
        ),
    )

def heartbeat_loop(job_run_id: int, stop_event: threading.Event):
    """Periodically updates heartbeat for a running job_run."""
    while not stop_event.is_set():
        refresh_worker_presence(job_run_id)

        db = SessionLocal()
        try:
            db.execute(
                select(JobRun)
                .where(JobRun.id == job_run_id)
                .with_for_update()
            ).scalar_one().\
            last_heartbeat_at = datetime.now(UTC).replace(microsecond=0)

            db.commit()

            logger.log(
                event="heartbeat",
                job_run_id=job_run.id,
                worker_id=WORKER_ID,
            )
        except Exception:
            db.rollback()
        finally:
            db.close()

        stop_event.wait(HEARTBEAT_INTERVAL_SEC)


def claim_job(db):

    with db.begin():
        job_run = (
            db.execute(
                select(JobRun)
                .where(
                    JobRun.status.in_([JobRunStatus.PENDING, JobRunStatus.RETRY]),
                    JobRun.scheduled_time <= datetime.now(UTC),
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
        job_run.started_at = datetime.now(UTC).replace(microsecond=0)
        job_run.last_heartbeat_at = datetime.now(UTC).replace(microsecond=0)
        job_run.worker_id = WORKER_ID

        redis_client.sadd("running_job_runs", job_run.id)

        logger.log(
            event="job_claimed",
            job_run_id=job_run.id,
            job_id=job_run.job_id,
            worker_id=WORKER_ID,
            status=job_run.status,
            attempt_number=job_run.attempt_number,
        )

        return job_run


def execute_job(db, job: Job, job_run: JobRun):
    logger.log(
        event="job_started",
        job_run_id=job_run.id,
        job_id=job.id,
        worker_id=WORKER_ID,
        attempt_number=job_run.attempt_number,
    )

    rnd = random.random()

    if rnd < job.failure_probability:
        raise JobFailureRandomException()

    time.sleep(job.execution_time_sec)


wait_for_db()
refresh_worker_presence()
logger.log(event="worker_booted", worker_id=WORKER_ID)

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
            job_run.finished_at = datetime.now(UTC).replace(microsecond=0)
            db.commit()

            logger.log(
                event="job_success",
                job_run_id=job_run.id,
                job_id=job.id,
                worker_id=WORKER_ID,
                duration_sec=job.execution_time_sec,
            )

        except JobFailureRandomException:
            job_run.attempt_number += 1
            job_run.finished_at = datetime.now(UTC).replace(microsecond=0)

            if job_run.attempt_number <= job.max_retries:
                job_run.status = JobRunStatus.RETRY
                job_run.scheduled_time = datetime.now(UTC).replace(microsecond=0) + timedelta(
                    seconds=job.retry_delay_sec
                )
                logger.log(
                    event="job_retry",
                    job_run_id=job_run.id,
                    job_id=job.id,
                    worker_id=WORKER_ID,
                    attempt_number=job_run.attempt_number,
                    next_run_at=job_run.scheduled_time,
                )
            else:
                job_run.status = JobRunStatus.FAILED
                logger.log(
                    event="job_failed",
                    job_run_id=job_run.id,
                    job_id=job.id,
                    worker_id=WORKER_ID,
                    attempts=job_run.attempt_number,
                    reason="max_retries_exceeded",
                )

            db.commit()

        finally:
            stop_event.set()
            redis_client.srem("running_job_runs", job_run.id)
            refresh_worker_presence()

    except ProgrammingError:
        db.rollback()
        time.sleep(POLL_INTERVAL_SEC)
    finally:
        db.close()
