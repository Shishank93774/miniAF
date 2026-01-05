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

## Phase 5 — Reliability, Leases & Failure Detection (Design Phase)

**Status:** 🔄 In progress (design-first)

### Problems to Solve
- Worker crashes mid-execution
- Infinite RUNNING jobs
- Long-running jobs vs stuck jobs
- Safe job recovery

### Core Insight
> **RUNNING is a lease, not a permanent state**

### Planned Mechanism
- `last_heartbeat_at` column
- Workers periodically heartbeat
- Scheduler (or reaper) detects expired leases
- Jobs reclaimed or failed based on policy

### Explicitly NOT Doing
- Long-lived DB transactions
- Relying on locks for execution lifetime

### Design Principles
- Short transactions
- Explicit liveness checks
- Idempotent recovery
- DB as the single source of truth

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

- Phase 5A: Lease expiry & heartbeat
- Phase 5B: Atomic job claiming with `SELECT ... FOR UPDATE SKIP LOCKED`
- Phase 6: Redis-based queue (optional)
- Phase 7: Metrics & observability
- Phase 8: Graceful shutdown & recovery

---

## Final Note

This repo intentionally documents **mistakes and evolution**.  
Every phase exists because something broke.

That’s the point.
