"""Verify legacy data is retained when workspace ownership is introduced."""
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import inspect, text
from app.db.session import init_db, make_engine

class LegacyMigrationTests(unittest.TestCase):
    def test_existing_analysis_is_preserved_but_unclaimed(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = make_engine(f"sqlite:///{Path(directory, 'old.db').as_posix()}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE analyses (id VARCHAR(32) PRIMARY KEY, title VARCHAR(200))"))
                conn.execute(text("INSERT INTO analyses (id, title) VALUES ('legacy', 'keep')"))
            init_db(engine)
            self.assertIn('owner_hash', {c['name'] for c in inspect(engine).get_columns('analyses')})
            with engine.connect() as conn:
                row = conn.execute(text("SELECT title, owner_hash FROM analyses WHERE id='legacy'")).one()
            self.assertEqual(tuple(row), ('keep', None))
            engine.dispose()
