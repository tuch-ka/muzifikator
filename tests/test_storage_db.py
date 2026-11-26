"""Тесты инициализации хранилища, миграций и времени UTC."""

import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from muzifikator import __main__ as entry
from muzifikator.config import Settings
from muzifikator.logging_setup import configure_logging
from muzifikator.storage import StorageError, create_session_factory, init_storage
from muzifikator.storage.models import Generation, UTCDateTime


def test_init_creates_directory_and_schema(db_path):
    engine = init_storage(Settings(db_path=db_path))
    try:
        assert db_path.is_file()
        with engine.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    text("select name from sqlite_master where type='table'")
                )
            }
    finally:
        engine.dispose()

    assert {"generations", "settings", "alembic_version"} <= tables


def test_init_is_idempotent(db_path):
    first = init_storage(Settings(db_path=db_path))
    first.dispose()
    second = init_storage(Settings(db_path=db_path))
    second.dispose()

    assert db_path.is_file()


def test_alembic_revision_is_head(db_path):
    engine = init_storage(Settings(db_path=db_path))
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("select version_num from alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()

    assert revision


def test_utc_datetime_roundtrip(engine):
    factory = create_session_factory(engine)
    moment = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    with factory() as session:
        session.add(Generation(id="a", created_at=moment, text="текст", status="pending"))
        session.commit()
    with factory() as session:
        stored = session.get(Generation, "a")
        assert stored is not None
        assert stored.created_at == moment
        assert stored.created_at.tzinfo is UTC


def test_utc_datetime_rejects_naive():
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)


def test_init_fails_on_unwritable_directory(tmp_path, db_path):
    db_path.parent.mkdir(parents=True)
    db_path.parent.chmod(0o500)
    try:
        with pytest.raises(StorageError):
            init_storage(Settings(db_path=db_path))
    finally:
        db_path.parent.chmod(0o700)


def test_main_exits_one_when_storage_fails(monkeypatch, capsys):
    def broken(_settings):
        raise StorageError("нет доступа")

    monkeypatch.setattr(entry, "init_storage", broken)
    monkeypatch.setattr(entry, "run_preflight", lambda _settings: _ok_preflight())

    code = entry.main([])

    assert code == 1
    assert "нет доступа" in capsys.readouterr().err


def _ok_preflight():
    from muzifikator.preflight import BinaryStatus, PreflightResult

    status = BinaryStatus(name="ffmpeg", available=True, path="/bin/ffmpeg", version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=status)


def test_migrations_do_not_reconfigure_application_logging(db_path):
    configure_logging("INFO")
    before = list(logging.getLogger().handlers)

    engine = init_storage(Settings(db_path=db_path))
    engine.dispose()

    assert list(logging.getLogger().handlers) == before
