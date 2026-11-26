"""Тесты плана сегментов."""

import pytest

from muzifikator.music import CROSSFADE_SECONDS, MusicRequestError, plan_segments


def test_within_window_single_segment():
    assert plan_segments(29.5) == [29.5]
    assert plan_segments(30) == [30.0]


def test_just_over_window():
    lengths = plan_segments(30.5)

    assert lengths == [30.0, 2.5]
    assert sum(lengths) - CROSSFADE_SECONDS == pytest.approx(30.5)


def test_forty_seconds():
    assert plan_segments(40) == [30.0, 12.0]


def test_fifty_five_seconds():
    assert plan_segments(55) == [30.0, 27.0]


def test_ninety_seconds():
    assert plan_segments(90) == [30.0, 30.0, 30.0, 6.0]


def test_minimum_duration():
    assert plan_segments(1) == [1.0]


@pytest.mark.parametrize("duration", [1, 5, 12.5, 29.9, 30, 31, 45, 61.7, 100, 120])
def test_assembled_duration_is_not_shorter(duration):
    lengths = plan_segments(duration)

    assembled = sum(lengths) - CROSSFADE_SECONDS * (len(lengths) - 1)
    assert assembled + 1e-9 >= duration


def test_every_segment_within_window():
    for duration in (31, 45, 75, 120):
        assert all(length <= 30 for length in plan_segments(duration))


def test_too_short_is_rejected():
    with pytest.raises(MusicRequestError):
        plan_segments(0.5)


def test_crossfade_not_smaller_than_window_is_rejected():
    with pytest.raises(ValueError):
        plan_segments(60, window=2, crossfade=2)
