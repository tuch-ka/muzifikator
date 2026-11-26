"""Тесты истории генераций: статусы, стадии, результат, чтение."""

from datetime import UTC, datetime, timedelta

import pytest

from muzifikator.storage import (
    GenerationNotFoundError,
    InvalidTransitionError,
    create_generation,
    fail_generation,
    finish_generation,
    get_generation,
    list_generations,
    set_stage,
    start_generation,
)


def _created(session, text="привет"):
    generation = create_generation(session, text=text, tts_provider="edge", voice="ru-RU")
    session.commit()
    return generation


def test_create_sets_pending_and_utc_time(session):
    generation = _created(session)

    assert generation.status == "pending"
    assert generation.created_at.tzinfo is UTC
    assert generation.id
    assert generation.text == "привет"
    assert generation.tts_provider == "edge"
    assert generation.stage is None
    assert generation.finished_at is None


def test_identifiers_are_unique(session):
    first = _created(session, text="a")
    second = _created(session, text="b")

    assert first.id != second.id


def test_success_path(session):
    generation = _created(session)

    start_generation(session, generation.id)
    session.commit()
    assert get_generation(session, generation.id).status == "running"

    for stage in ("tts", "music", "mix"):
        set_stage(session, generation.id, stage)
        session.commit()
        assert get_generation(session, generation.id).stage == stage

    finish_generation(session, generation.id, output_path="out/a.mp3", duration_seconds=12.5)
    session.commit()
    stored = get_generation(session, generation.id)

    assert stored.status == "done"
    assert stored.output_path == "out/a.mp3"
    assert stored.duration_seconds == 12.5
    assert stored.finished_at is not None
    assert stored.finished_at.tzinfo is UTC


def test_fail_from_running(session):
    generation = _created(session)
    start_generation(session, generation.id)

    fail_generation(session, generation.id, error="edge-tts недоступен")
    session.commit()
    stored = get_generation(session, generation.id)

    assert stored.status == "failed"
    assert stored.error == "edge-tts недоступен"
    assert stored.finished_at is not None


def test_fail_from_pending(session):
    generation = _created(session)

    fail_generation(session, generation.id, error="нет ffmpeg")
    session.commit()

    assert get_generation(session, generation.id).status == "failed"


@pytest.mark.parametrize("target", ["done", "failed"])
def test_terminal_record_cannot_change(session, target):
    generation = _created(session)
    start_generation(session, generation.id)
    if target == "done":
        finish_generation(session, generation.id, output_path="out/a.mp3", duration_seconds=1.0)
    else:
        fail_generation(session, generation.id, error="сбой")
    session.commit()

    with pytest.raises(InvalidTransitionError):
        start_generation(session, generation.id)
    with pytest.raises(InvalidTransitionError):
        fail_generation(session, generation.id, error="ещё раз")
    with pytest.raises(InvalidTransitionError):
        finish_generation(session, generation.id, output_path="out/b.mp3", duration_seconds=2.0)
    session.rollback()


def test_stage_requires_running(session):
    generation = _created(session)

    with pytest.raises(InvalidTransitionError):
        set_stage(session, generation.id, "tts")
    session.rollback()


def test_unknown_stage_rejected(session):
    generation = _created(session)
    start_generation(session, generation.id)

    with pytest.raises(InvalidTransitionError):
        set_stage(session, generation.id, "mastering")
    session.rollback()


def test_empty_error_rejected(session):
    generation = _created(session)

    with pytest.raises(InvalidTransitionError):
        fail_generation(session, generation.id, error="   ")
    session.rollback()


def test_missing_record_for_update(session):
    with pytest.raises(GenerationNotFoundError):
        start_generation(session, "нет-такой")
    session.rollback()


def test_get_missing_returns_none(session):
    assert get_generation(session, "нет-такой") is None


def test_list_orders_newest_first_and_limits(session):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(4):
        generation = create_generation(session, text=f"текст {index}")
        generation.created_at = base + timedelta(minutes=index)
    session.commit()

    everything = list_generations(session)
    limited = list_generations(session, limit=2)

    assert [item.text for item in everything] == ["текст 3", "текст 2", "текст 1", "текст 0"]
    assert [item.text for item in limited] == ["текст 3", "текст 2"]


def test_list_rejects_non_positive_limit(session):
    with pytest.raises(ValueError):
        list_generations(session, limit=0)


def test_history_survives_restart(db_path, engine):
    from muzifikator.config import Settings
    from muzifikator.storage import create_session_factory, init_storage

    factory = create_session_factory(engine)
    with factory() as session:
        generation = create_generation(session, text="до перезапуска")
        session.commit()
        kept_id = generation.id
    engine.dispose()

    restarted = init_storage(Settings(db_path=db_path))
    try:
        with create_session_factory(restarted)() as session:
            stored = get_generation(session, kept_id)
            assert stored is not None
            assert stored.text == "до перезапуска"
    finally:
        restarted.dispose()
