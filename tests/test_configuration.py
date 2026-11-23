import os
import unittest
from unittest.mock import patch

from backend.database import open_database


class ConfigurationTests(unittest.TestCase):
    def test_production_rejects_missing_or_temporary_database(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "DATABASE_URL": ""}):
            with self.assertRaises(RuntimeError):
                open_database()
            with self.assertRaises(RuntimeError):
                open_database("sqlite:///temporary.db")

    def test_postgres_connection_string_is_normalized_without_exposing_credentials(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            engine, factory = open_database("postgres://test:dummy@localhost/test")
            self.assertEqual(engine.url.drivername, "postgresql+psycopg")
            engine.dispose()
