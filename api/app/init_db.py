from common.db.session import engine
from common.db.base import Base
from common.db import models  # noqa

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
