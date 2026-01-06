import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError, ProgrammingError

from croniter import croniter

from common.db.session import SessionLocal
from common.db.models import Job, JobRun, JobRunStatus
from common.db.utils import wait_for_db

UTC = timezone.utc
ZOMBIE_TIMEOUT_SEC = 30
SCHEDULER_INTERVAL_SEC = 10


def add_job_run(db, job_id, scheduled_time):
    job_run = JobRun(
        job_id=job_id,
        scheduled_time=scheduled_time,
        status=JobRunStatus.PENDING,
        attempt_number=0,
    )
    try:
        db.add(job_run)
        db.commit()
    except IntegrityError:
        db.rollback()


wait_for_db()
print("[scheduler] Started")

while True:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # 1. Zombie detection
        zombie_runs = (
            db.execute(
                select(JobRun)
                .where(
                    JobRun.status == JobRunStatus.RUNNING,
                    JobRun.last_heartbeat_at
                    < now - timedelta(seconds=ZOMBIE_TIMEOUT_SEC),
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )

        for jr in zombie_runs:
            job = db.execute(
                select(Job).where(Job.id == jr.job_id)
            ).scalar_one()

            jr.attempt_number += 1
            jr.finished_at = now
            jr.worker_id = None

            if jr.attempt_number <= job.max_retries:
                jr.status = JobRunStatus.RETRY
                jr.scheduled_time = now + timedelta(
                    seconds=job.retry_delay_sec
                )
                print(f"[scheduler] Zombie RETRY job_run={jr.id}")
            else:
                jr.status = JobRunStatus.FAILED
                print(f"[scheduler] Zombie FAILED job_run={jr.id}")

        db.commit()

        # 2. Cron scheduling
        jobs = db.execute(
            select(Job).where(Job.is_active == True)
        ).scalars().all()

        for job in jobs:
            last_run = db.execute(
                select(JobRun)
                .where(JobRun.job_id == job.id)
                .order_by(desc(JobRun.scheduled_time))
                .limit(1)
            ).scalar_one_or_none()

            base_time = last_run.scheduled_time if last_run else job.created_at
            next_run = croniter(job.schedule, base_time).get_next(datetime)
            next_run = next_run.astimezone(UTC)

            if next_run <= now:
                add_job_run(db, job.id, next_run)
                print(f"[scheduler] Scheduled {job.name}")

    except ProgrammingError:
        db.rollback()
        time.sleep(3)
    finally:
        db.close()

    time.sleep(SCHEDULER_INTERVAL_SEC)
