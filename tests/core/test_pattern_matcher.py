import pytest

from spots_cli.core.pattern_matcher import PatternMatcher
from spots_cli.core.youtube_extractor import YouTubeExtractor
from spots_cli.models import Metadata, YTVideoInfo


@pytest.fixture
def matcher() -> PatternMatcher:
    return PatternMatcher(extractor=YouTubeExtractor())


def song(title: str, artist: str) -> Metadata:
    return Metadata(title=title, artist=artist, link="", artist_id="")


def video(title: str, uploader: str) -> YTVideoInfo:
    return YTVideoInfo(id="x", title=title, uploader=uploader, audio_ext="webm", filesize=4)


@pytest.mark.parametrize(
    "title, uploader",
    [
        ("Tyla - Water (Official Music Video)", "Tyla"),
        ("Tyla - Water (Official Audio)", "Tyla"),
        ("Tyla - Water", "LatinHype"),
        ("Water", "Tyla"),
    ],
)
def test_matches_raw_youtube_titles(matcher, title, uploader):
    assert matcher.match_tracks(video_info=video(title, uploader), metadata=song("Water", "Tyla"))


def test_rejects_a_different_song_by_the_same_artist(matcher):
    raw = video("Tyla - Truth or Dare (Official Video)", "Tyla")
    assert not matcher.match_tracks(video_info=raw, metadata=song("Water", "Tyla"))


def test_does_not_change_the_video(matcher):
    raw = video("Tyla - Water (Official Music Video)", "Tyla")
    matcher.match_tracks(video_info=raw, metadata=song("Water", "Tyla"))
    assert (raw.title, raw.uploader) == ("Tyla - Water (Official Music Video)", "Tyla")


def test_song_named_after_the_artist(matcher):
    raw = video("Tyla - Tyla (Official Video)", "Tyla")
    assert matcher.match_tracks(video_info=raw, metadata=song("Tyla", "Tyla"))


def test_karaoke_channels_are_still_penalised(matcher):
    raw = video("Tyla - Water (Karaoke Version)", "Sing King Karaoke")
    assert not matcher.match_tracks(video_info=raw, metadata=song("Water", "Tyla"))
