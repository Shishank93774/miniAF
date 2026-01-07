# miniAF — A Minimal Airflow-like Job Scheduler (Learning Project)

miniAF is a **learning-first**, from-scratch implementation of a job scheduler inspired by Apache Airflow.  
The goal is **not feature parity**, but to deeply understand **scheduling, concurrency, reliability, and failure handling** in distributed systems.

This project is intentionally built **step by step**, documenting design decisions, mistakes, and improvements along the way.

---

## Tech Stack

- Python 3.11
- FastAPI (API layer)
- PostgreSQL (state & coordination)
- SQLAlchemy ORM
- Docker & Docker Compose
- croniter (cron scheduling)
- Redis (planned, not yet used)

---

## High-Level Architecture

Worker(s) ───▶ API ───▶ PostgreSQL ◀─── Scheduler


- **API**: Create / manage jobs
- **Scheduler**: Decides *when* jobs should run
- **Worker(s)**: Execute jobs
- **Postgres**: Source of truth for state & coordination

---

## Phase 1 — Core Models & API

**Goal:** Define the domain correctly.

### Implemented
- `Job`
  - name
  - cron schedule
  - execution_time_sec
  - failure_probability
  - max_retries
  - retry_delay_sec
  - is_active
- `JobRun`
  - scheduled_time
  - status (PENDING, RUNNING, SUCCESS, FAILED, RETRY)
  - attempt_number
  - timestamps
  - worker_id
- REST API using FastAPI
- SQLAlchemy models
- DB schema auto-creation on startup

### Learnings
- DB defaults vs ORM defaults
- Enum handling in Postgres
- Why schema creation must be centralized

---

## Phase 2 — Scheduler (Job → JobRun)

**Goal:** Convert cron jobs into concrete executions.

### Implemented
- Scheduler process
- Reads active jobs
- Uses `croniter` to compute next run
- Inserts `JobRun` records
- Idempotency via `(job_id, scheduled_time)` unique constraint
- Timezone normalization (moved to UTC later)

### Problems Faced
- Timezone mismatches
- Duplicate JobRuns
- Scheduler running before schema exists

### Fixes
- UTC everywhere
- DB-level uniqueness
- Startup retries

---

## Phase 3 — Dockerization

**Goal:** Make services reproducible.

### Implemented
- Dockerfiles for:
  - API
  - Scheduler
  - Worker
- Docker Compose setup
- Shared `common/` package
- `.env` based configuration

### Issues Encountered
- psycopg2 build failures
- import path issues
- services starting before DB ready

### Fixes
- `psycopg2-binary`
- explicit `PYTHONPATH`
- DB wait utilities

---

## Phase 4 — Worker (Single Node Execution)

**Goal:** Execute JobRuns reliably.

### Implemented
- Worker process
- Polls DB for `PENDING` or `RETRY` JobRuns
- Marks RUNNING
- Simulates execution
- Handles:
  - SUCCESS
  - FAILURE
  - RETRY with delay
- Retry scheduling by updating `scheduled_time`
- UTC-only timestamps

### Important Design Decisions
- Retry logic handled by **worker**, not scheduler
- No Redis yet
- One DB as coordinator
- Execution happens **outside DB transactions**

### Observations
- Multiple commits & rollbacks are normal
- State transitions must be explicit
- Time-based scheduling beats sleep-based retry

---

## Phase 4.5 — Multiple Workers (Concurrency Issues)

**Goal:** Understand real distributed problems.

### What We Observed
- Inconsistent job status counts
- Race conditions when multiple workers claim jobs
- Double execution risk

### Key Insight
> **Postgres must decide the winner, not Python**

This led to understanding:
- Atomic job claiming
- Row-level locking
- Why naive polling breaks under concurrency

---

## Phase 5 — Reliability, Leases & Failure Detection

**Status:** ✅ Done (design-first)

**Implemented:**
- Scheduler
- Workers (scalable)
- Atomic job claiming
- Retries with delay
- Heartbeat mechanism
- Zombie job reaper
- Dockerized setup

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
## Phase 6: Metrics & observability

**Goal:** Make the system observable and debuggable under concurrent, distributed execution.

### Implemented:
- Structured JSON logging across:
  - API
  - Scheduler
  - Workers

### Logged key lifecycle events:
  - Scheduler startup
  - Job scheduling
  - Job claiming
  - Job execution start 
  - Heartbeats 
  - Job success / retry / failure 

### Periodic cluster state logs from scheduler:
  - Active worker count 
  - Running job count 

### Heartbeat emission from workers while executing jobs 

### Important Design Decisions
- Logs are append-only and immutable
- Logging is non-blocking and does not affect execution flow 
- No external log aggregator yet (stdout-first design)
- Scheduler observes system state via DB + logs, not worker RPCs

### Observations
- Structured logs make distributed flows traceable 
- Heartbeats are essential for detecting stalled or zombie executions 
- Observability must be built before scaling workers 
- Logs double as both debugging tool and future metrics source

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

## What This Project Is Really About

This is **not** about:
- Building Airflow
- Optimizing performance
- Production readiness

This **is** about:
- Understanding distributed systems
- Learning failure modes
- Thinking in leases, not locks
- Designing for crashes, not happy paths

---

## Next Planned Phases

- Phase 7A: Deploy this project
- Phase 7B: Redis-based queue

---

## Final Note

This repo intentionally documents **mistakes and evolution**.  
Every phase exists because something broke.

That’s the point.
