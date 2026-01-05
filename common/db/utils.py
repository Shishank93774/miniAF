import time
from sqlalchemy import text
from common.db.session import engine

def wait_for_db():
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("DB is reachable")
            return
        except Exception:
            print("Waiting for DB...")
            time.sleep(2)
