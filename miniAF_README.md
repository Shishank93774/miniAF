# miniAF — A Minimal Airflow‑Like Scheduler (Learning Project)

miniAF is a **from‑scratch, educational implementation** of a distributed job scheduler inspired by Apache Airflow.
The goal of this project is **learning system design fundamentals**, not feature parity.

This README documents progress **up to Heartbeat + Zombie Job Reaper**.

---

## Current Progress ✅

**Implemented:**
- Scheduler
- Workers (scalable)
- Atomic job claiming
- Retries with delay
- Heartbeat mechanism
- Zombie job reaper
- Dockerized setup

---

## Core Tables

### jobs
Defines what should run and how.

### job_runs
Represents an execution attempt.

Important fields:
- status (PENDING, RUNNING, RETRY, SUCCESS, FAILED)
- attempt_number
- scheduled_time
- worker_id
- last_heartbeat_at

---

## Atomic Job Claiming

Workers claim jobs using PostgreSQL row locks:

```sql
SELECT *
FROM job_runs
WHERE status IN ('PENDING', 'RETRY')
  AND scheduled_time <= now()
ORDER BY scheduled_time
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

Only **Postgres decides the winner**, preventing race conditions.

---

## Heartbeat System ❤️

Workers periodically update:

```
job_run.last_heartbeat_at = now()
```

This happens while the job is executing.

---

## Zombie Job Reaper 🧟‍♂️

Scheduler detects jobs stuck in RUNNING:

```
status = RUNNING
AND last_heartbeat_at < now() - HEARTBEAT_TIMEOUT
```

Action taken:
- Retry if attempts left
- Else mark FAILED

---

## Retry Strategy

- Same job_run reused
- scheduled_time updated
- attempt_number incremented
- No new rows created

---

## Failure Scenarios Covered

- Worker crash
- Worker kill
- Multiple workers racing
- Stuck RUNNING jobs
- Duplicate execution prevention

---

## Docker

Scale workers:
```bash
docker-compose up --scale worker=2
```

---

## Philosophy

- Database > Application for coordination
- Crashes are normal
- Recovery must be automatic

---

## Next Steps

- Metrics & monitoring
- Watchdog service
- Graceful shutdown
- DAG support

---

This project intentionally evolves slowly to expose real‑world scheduler problems.
