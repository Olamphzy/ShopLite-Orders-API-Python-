import os
import tempfile

from .app import create_app
from .db import init_database

# A fresh, seeded database on every start.
DB_PATH = os.environ.get("SHOPLITE_DB_PATH", os.path.join(tempfile.gettempdir(), "shoplite.db"))
init_database(DB_PATH, reset=True)

app = create_app(DB_PATH)
