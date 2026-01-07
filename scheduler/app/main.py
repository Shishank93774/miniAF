import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError, ProgrammingError

from croniter import croniter

from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db
from common.logging.logger import StructuredLogger
from common.redis.client import redis_client

logger = StructuredLogger(
    name="scheduler",
    logfile="scheduler.log",
)

UTC = timezone.utc
ZOMBIE_TIMEOUT_SEC = 60  # heartbeat expiry
SCHEDULER_INTERVAL_SEC = 2  # scheduler cooldown

def add_job_run(db, job_id: int, scheduled_time: datetime):
    scheduled_time = scheduled_time.replace(microsecond=0)
    jr = JobRun(
        job_id=job_id,
        scheduled_time=scheduled_time,
        status=JobRunStatus.PENDING,
        attempt_number=0,
    )
    try:
        db.add(jr)
        db.commit()
    except IntegrityError:
        db.rollback()


def reap_zombie_runs(db):
    """
    Convert dead RUNNING jobs into RETRY or FAILED.
    Scheduler NEVER sets started_at / finished_at.
    """

    zombie_runs = (
        db.execute(
            select(JobRun)
            .where(
                JobRun.status == JobRunStatus.RUNNING,
                JobRun.last_heartbeat_at < datetime.now(UTC)- timedelta(seconds=ZOMBIE_TIMEOUT_SEC),
            )
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )

    for jr in zombie_runs:
        logger.log(
            event="zombie_detected",
            job_run_id=jr.id,
            job_id=jr.job_id,
            worker_id=jr.worker_id,
            last_heartbeat_at=jr.last_heartbeat_at,
        )

        job = db.execute(select(Job).where(Job.id == jr.job_id)).scalar_one()

        if jr.attempt_number < job.max_retries:
            jr.status = JobRunStatus.RETRY
            logger.log(
                event="zombie_recovered",
                job_run_id=jr.id,
                job_id=jr.job_id,
                new_status=jr.status,
            )
        else:
            jr.status = JobRunStatus.FAILED
            logger.log(
                event="zombie_failed",
                job_run_id=jr.id,
                job_id=jr.job_id,
                new_status=jr.status,
            )

        jr.worker_id = None
        redis_client.srem("running_job_runs", jr.id)

    db.commit()


wait_for_db()
logger.log(event="scheduler_started")

while True:
    active_workers = redis_client.keys("worker:*")
    running_jobs = redis_client.smembers("running_job_runs")

    logger.log(
        event="cluster_state",
        active_workers=len(active_workers),
        running_jobs=len(running_jobs),
    )

    db = SessionLocal()
    try:
        reap_zombie_runs(db)

        jobs = db.execute(select(Job).where(Job.is_active == True)).scalars().all()

        for job in jobs:
            last_run = (
                db.execute(
                    select(JobRun)
                    .where(JobRun.job_id == job.id)
                    .order_by(desc(JobRun.scheduled_time))
                    .limit(1)
                )
                .scalar_one_or_none()
            )

            base_time = last_run.scheduled_time if last_run else job.created_at
            next_run = croniter(job.schedule, base_time).get_next(datetime)

            if next_run <= datetime.now(UTC):
                add_job_run(db, job.id, next_run)
                logger.log(
                    event="job_scheduled",
                    job_id=job.id,
                    scheduled_time=next_run,
                )

    except ProgrammingError:
        db.rollback()
        time.sleep(5)
    finally:
        db.close()

    time.sleep(SCHEDULER_INTERVAL_SEC)
