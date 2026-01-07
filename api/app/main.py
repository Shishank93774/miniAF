from fastapi import FastAPI
from api.app.routers import jobs
from common.db.session import engine
from common.db.base import Base
from common.db.utils import wait_for_db
from common.logging.logger import StructuredLogger
from common.redis.client import redis_client

logger = StructuredLogger(
    name="api",
    logfile="api.log",
)
app = FastAPI()

app.include_router(jobs.router)

@app.on_event("startup")
def startup():
    wait_for_db()
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match="worker:*", count=100)
        if keys:
            redis_client.delete(*keys)
        if cursor == 0:
            break

    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}
