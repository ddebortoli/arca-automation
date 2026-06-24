"""Tests for database repository factory and SQLite stats."""

import pytest

from src.bootstrap import build_repository, verify_database_connection
from src.repositories.sqlite_payment_repository import SqlitePaymentRepository


@pytest.fixture
def sqlite_repo(tmp_path) -> SqlitePaymentRepository:
    return SqlitePaymentRepository(tmp_path / "payments.db")


def test_sqlite_count_payment_stats_empty(sqlite_repo: SqlitePaymentRepository) -> None:
    assert sqlite_repo.count_payment_stats() == (0, 0, 0)


def test_build_repository_from_env_sqlite(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("ARC_ENV_FILE", raising=False)

    repository = build_repository()

    assert isinstance(repository, SqlitePaymentRepository)
    assert repository.count_payment_stats() == (0, 0, 0)


def test_build_repository_postgres_requires_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("ARC_ENV_FILE", raising=False)

    with pytest.raises(EnvironmentError, match="DATABASE_URL"):
        build_repository()


def test_verify_database_connection_sqlite(tmp_path) -> None:
    db_path = tmp_path / "probe.db"
    verify_database_connection(backend="sqlite", database_path=str(db_path))
    assert db_path.exists()


def test_verify_database_connection_postgres_missing_url() -> None:
    with pytest.raises(EnvironmentError, match="DATABASE_URL"):
        verify_database_connection(backend="postgres", database_url="")
