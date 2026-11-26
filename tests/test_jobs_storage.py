"""Тесты хранилища для файлов результата и сброса зависших задач."""

from muzifikator.storage import (
    add_generation_file,
    create_generation,
    fail_stale_generations,
    get_generation,
    get_generation_files,
    list_generation_files,
    start_generation,
)


def _generation(session, text="текст"):
    generation = create_generation(session, text=text)
    session.commit()
    return generation


def test_add_two_formats(session):
    generation = _generation(session)

    add_generation_file(session, generation.id, format="mp3", path="/out/a.mp3")
    add_generation_file(session, generation.id, format="m4a", path="/out/a.m4a")
    session.commit()

    files = get_generation_files(session, generation.id)
    assert files == {"mp3": files["mp3"], "m4a": files["m4a"]}
    assert str(files["mp3"]) == "/out/a.mp3"
    assert len(list_generation_files(session, generation.id)) == 2


def test_same_format_updates_path(session):
    generation = _generation(session)

    add_generation_file(session, generation.id, format="mp3", path="/out/old.mp3")
    add_generation_file(session, generation.id, format="mp3", path="/out/new.mp3")
    session.commit()

    files = get_generation_files(session, generation.id)
    assert len(files) == 1
    assert str(files["mp3"]) == "/out/new.mp3"


def test_files_are_removed_with_generation(session):
    generation = _generation(session)
    add_generation_file(session, generation.id, format="mp3", path="/out/a.mp3")
    session.commit()

    session.delete(generation)
    session.commit()

    assert list_generation_files(session, generation.id) == []


def test_fail_stale_generations(session):
    running = _generation(session, text="в работе")
    start_generation(session, running.id)
    other_running = _generation(session, text="тоже в работе")
    start_generation(session, other_running.id)
    done = _generation(session, text="готова")
    start_generation(session, done.id)
    from muzifikator.storage import finish_generation

    finish_generation(session, done.id, output_path="/out/x.mp3", duration_seconds=1.0)
    session.commit()

    changed = fail_stale_generations(session, reason="прервано перезапуском")
    session.commit()

    assert changed == 2
    for generation_id in (running.id, other_running.id):
        stored = get_generation(session, generation_id)
        assert stored.status == "failed"
        assert stored.error == "прервано перезапуском"
        assert stored.finished_at is not None
    assert get_generation(session, done.id).status == "done"


def test_fail_stale_is_idempotent(session):
    running = _generation(session)
    start_generation(session, running.id)
    session.commit()

    assert fail_stale_generations(session, reason="раз") == 1
    session.commit()
    assert fail_stale_generations(session, reason="два") == 0
