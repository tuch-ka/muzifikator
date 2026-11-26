"""Тесты сервиса музыки: сегменты, seed, промпт, отсутствие кэша, отказы."""

import shutil
import subprocess
from pathlib import Path

import pytest

from muzifikator.music import (
    MusicGenerationError,
    MusicRequest,
    MusicRequestError,
    MusicResourceError,
    MusicService,
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


class FakeProvider:
    name = "fake"

    def __init__(self, seconds_override: float | None = None, fail: Exception | None = None):
        self.seconds_override = seconds_override
        self.fail = fail
        self.calls: list[tuple[str, float, int]] = []

    def segment(self, *, prompt: str, seconds: float, seed: int, target: Path) -> None:
        self.calls.append((prompt, seconds, seed))
        if self.fail is not None:
            raise self.fail
        duration = self.seconds_override if self.seconds_override is not None else seconds
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=32000:cl=mono",
                "-t",
                str(duration),
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            check=True,
            capture_output=True,
        )


def _service(provider, workdir=None) -> MusicService:
    return MusicService(
        provider,
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        default_prompt="folk metal",
        model_name="fake-model",
    )


def test_long_request_uses_two_segments(tmp_path):
    provider = FakeProvider()
    workdir = tmp_path / "work"

    result = _service(provider).generate(MusicRequest(duration_seconds=40, seed=100), workdir)

    assert result.segments == 2
    assert [call[1] for call in provider.calls] == [30.0, 12.0]
    assert [call[2] for call in provider.calls] == [100, 101]
    assert result.duration_seconds >= 40
    assert result.seed == 100
    assert result.path.is_file()


def test_short_request_uses_one_segment(tmp_path):
    provider = FakeProvider()

    result = _service(provider).generate(MusicRequest(duration_seconds=10, seed=1), tmp_path)

    assert result.segments == 1
    assert len(provider.calls) == 1
    assert result.duration_seconds == pytest.approx(10, abs=0.2)


def test_random_seed_is_reported(tmp_path):
    provider = FakeProvider()

    first = _service(provider).generate(MusicRequest(duration_seconds=2), tmp_path)
    second = _service(provider).generate(MusicRequest(duration_seconds=2), tmp_path)

    assert first.seed != second.seed
    assert provider.calls[0][2] == first.seed


def test_default_prompt_is_used(tmp_path):
    provider = FakeProvider()

    result = _service(provider).generate(MusicRequest(duration_seconds=2, seed=3), tmp_path)

    assert result.prompt == "folk metal"
    assert provider.calls[0][0] == "folk metal"


def test_explicit_prompt_wins(tmp_path):
    provider = FakeProvider()

    result = _service(provider).generate(
        MusicRequest(duration_seconds=2, seed=3, prompt="symphonic metal"), tmp_path
    )

    assert result.prompt == "symphonic metal"
    assert provider.calls[0][0] == "symphonic metal"


def test_no_cache_two_identical_requests_generate_again(tmp_path):
    provider = FakeProvider()
    service = _service(provider)
    request = MusicRequest(duration_seconds=2, seed=5)

    first = service.generate(request, tmp_path)
    second = service.generate(request, tmp_path)

    assert len(provider.calls) == 2
    assert first.path != second.path


def test_parts_are_removed_after_assembly(tmp_path):
    provider = FakeProvider()

    result = _service(provider).generate(MusicRequest(duration_seconds=35, seed=1), tmp_path)

    leftovers = [path.name for path in tmp_path.iterdir() if "part" in path.name]
    assert leftovers == []
    assert result.path.exists()


def test_provider_failure_leaves_no_result(tmp_path):
    provider = FakeProvider(fail=MusicResourceError("не хватило памяти"))

    with pytest.raises(MusicResourceError):
        _service(provider).generate(MusicRequest(duration_seconds=2, seed=1), tmp_path)

    assert list(tmp_path.glob("music-*.wav")) == []


def test_too_short_request_is_rejected_before_generation(tmp_path):
    provider = FakeProvider()

    with pytest.raises(MusicRequestError):
        _service(provider).generate(MusicRequest(duration_seconds=0.5), tmp_path)

    assert provider.calls == []


def test_shorter_than_requested_is_an_error(tmp_path):
    provider = FakeProvider(seconds_override=0.3)

    with pytest.raises(MusicGenerationError, match="короче"):
        _service(provider).generate(MusicRequest(duration_seconds=5, seed=1), tmp_path)

    assert list(tmp_path.glob("music-*.wav")) == []


def test_error_type_from_provider_is_kept(tmp_path):
    provider = FakeProvider(fail=MusicGenerationError("модель упала"))

    with pytest.raises(MusicGenerationError, match="модель упала"):
        _service(provider).generate(MusicRequest(duration_seconds=2, seed=1), tmp_path)
