from fastapi import FastAPI
from api.app.routers import jobs
from common.db.session import engine
from common.db.base import Base
from common.db.utils import wait_for_db

app = FastAPI()

app.include_router(jobs.router)

@app.on_event("startup")
def startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}
