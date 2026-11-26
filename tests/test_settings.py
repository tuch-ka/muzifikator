"""Тесты сохранённых настроек: JSON, значения по умолчанию, независимость."""

import pytest

from muzifikator.storage import MISSING, create_generation, get_setting, set_setting


def test_set_and_get(session):
    set_setting(session, "tts_voice", "ru-RU-DmitryNeural")
    session.commit()

    assert get_setting(session, "tts_voice") == "ru-RU-DmitryNeural"


def test_replace_keeps_only_last_value(session):
    first = set_setting(session, "music_tags", "folk metal")
    session.commit()
    first_updated_at = first.updated_at

    set_setting(session, "music_tags", "symphonic metal")
    session.commit()

    assert get_setting(session, "music_tags") == "symphonic metal"
    assert first.value == '"symphonic metal"'
    assert first.updated_at >= first_updated_at


def test_unknown_key_returns_default(session):
    assert get_setting(session, "нет-ключа", "по умолчанию") == "по умолчанию"
    assert get_setting(session, "нет-ключа", None) is None
    assert get_setting(session, "нет-ключа") is MISSING


def test_saved_null_differs_from_missing(session):
    set_setting(session, "voice", None)
    session.commit()

    assert get_setting(session, "voice", "default") is None
    assert get_setting(session, "нет-ключа", None) is None


@pytest.mark.parametrize(
    "value",
    [
        "строка с кириллицей",
        42,
        12.5,
        True,
        ["a", "b"],
        {"provider": "piper", "voice": "ru", "rate": 1.1},
        None,
    ],
)
def test_json_roundtrip(session, value):
    set_setting(session, "key", value)
    session.commit()

    assert get_setting(session, "key") == value


def test_non_serializable_value_rejected(session):
    with pytest.raises(TypeError):
        set_setting(session, "key", object())
    session.rollback()


def test_settings_do_not_depend_on_history(session):
    set_setting(session, "last_folder", "/Users/me/out")
    session.commit()

    create_generation(session, text="новая генерация")
    session.commit()

    assert get_setting(session, "last_folder") == "/Users/me/out"


def test_settings_survive_restart(db_path, engine):
    from muzifikator.config import Settings
    from muzifikator.storage import create_session_factory, init_storage

    with create_session_factory(engine)() as session:
        set_setting(session, "voice", "ru-RU-SvetlanaNeural")
        session.commit()
    engine.dispose()

    restarted = init_storage(Settings(db_path=db_path))
    try:
        with create_session_factory(restarted)() as session:
            assert get_setting(session, "voice") == "ru-RU-SvetlanaNeural"
    finally:
        restarted.dispose()
