"""Equivalent Switch format labels must not hide better availability evidence."""
import pytest

from romarr.platforms import by_slug, GB
from romarr.selection import Release, best_release, judge, score


def release(title, seeds=11):
    return Release(title, 4 * GB, seeds, (1000,), "magnet:?test", "torrent")


@pytest.mark.parametrize("format", ["NSP", "XCI"])
def test_package_label_and_filename_receive_equal_platform_evidence(format):
    platform = by_slug("switch")
    filename = release(f"Example Adventure.{format.lower()}", 1)
    labelled = release(f"[Switch {format}] Example Adventure", 11)
    assert score(labelled, "Example Adventure", platform) > score(filename, "Example Adventure", platform)
    assert best_release([filename, labelled], "Example Adventure", platform) == labelled
    assert score(release(labelled.title, 1), "Example Adventure", platform) == score(filename, "Example Adventure", platform)


@pytest.mark.parametrize("title", [
    "[Switch NSP] Example Adventure PC Repack",
    "[Switch NSP] Example Adventure DLC",
])
def test_package_marker_does_not_override_content_rejections(title):
    assert not judge(release(title, 500), "Example Adventure", by_slug("switch")).accepted


def test_zero_seed_public_package_remains_rejected():
    assert not judge(release("[Switch NSP] Example Adventure", 0), "Example Adventure", by_slug("switch")).accepted


def test_generic_format_and_substring_are_not_switch_package_evidence():
    # Use the resolved platform explicitly; generic ISO and word substrings
    # must not earn the specific package-label bonus.
    platform = by_slug("switch")
    for title in ("[Switch ISO] Example Adventure", "Switch Example Adventure Conspiracy"):
        assert not any("package format" in reason for _, reason in judge(release(title), "Example Adventure", platform).reasons)
