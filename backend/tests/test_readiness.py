import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, inspect, text
from fastapi.testclient import TestClient
from app import main, database
from app.models import Base
from app.services.providers.sec_provider import SECFundamentalsProvider


class ReadinessTests(unittest.TestCase):
    def test_existing_schema_migration_is_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE rs_histories (id INTEGER PRIMARY KEY)"))
        with patch.object(database, "engine", engine):
            database.ensure_schema_compatibility()
            database.ensure_schema_compatibility()
        self.assertIn("retry_count", {c["name"] for c in inspect(engine).get_columns("rs_histories")})
        Base.metadata.create_all(engine)
        self.assertIn("portfolios", inspect(engine).get_table_names())
        engine.dispose()

    def test_database_failure_restarts_initialization(self):
        main.app.state.db_ready = True
        with patch.object(main.engine, "connect", side_effect=RuntimeError("temporary outage")), patch.object(main, "_start_initialization") as restart:
            result = main.health()
        self.assertEqual(result["database"], "unavailable")
        restart.assert_called_once()

    def test_unready_api_returns_retryable_503(self):
        main.app.state.db_ready = False
        with patch.object(main, "_start_initialization"):
            client = TestClient(main.app)
            response = client.get("/portfolios")
        self.assertEqual(response.status_code, 503)
        self.assertIn("reconnecting", response.json()["detail"])

    def test_sec_requires_identifiable_user_agent(self):
        with patch.dict(os.environ, {"SEC_USER_AGENT": ""}):
            with self.assertRaisesRegex(RuntimeError, "SEC_USER_AGENT"):
                SECFundamentalsProvider()


if __name__ == "__main__":
    unittest.main()
