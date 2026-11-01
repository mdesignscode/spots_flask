from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from spots_cli.app.media_resolver import MediaResolver
from spots_cli.core.pattern_matcher import PatternMatcher
from spots_cli.core.youtube_extractor import YouTubeExtractor
from spots_cli.models import Metadata, SongNotFound, SpotifyUnavailableError, YTVideoInfo

LINK = "https://www.youtube.com/watch?v=XoiOOiuH8iI"


@pytest.fixture
def upload() -> YTVideoInfo:
    return YTVideoInfo(
        id="XoiOOiuH8iI",
        title="Tyla - Water (Official Music Video)",
        uploader="Tyla",
        audio_ext="webm",
        filesize=4,
    )


def build_resolver(upload, *, provider_result=None, provider_error=None, spotify=None):
    extractor = YouTubeExtractor()
    core = Mock(extractor=extractor, matcher=PatternMatcher(extractor=extractor))
    domain = Mock()
    domain.youtube_search.video_search.return_value = SimpleNamespace(
        is_cached=False, result=upload
    )
    if provider_error:
        domain.provider_search.search_track.side_effect = provider_error
    else:
        domain.provider_search.search_track.return_value = provider_result
    clients = Mock(spotify=spotify)
    return MediaResolver(core=core, domain=domain, clients=clients, domain_resolver=Mock())


def song(title: str, artist: str) -> Metadata:
    return Metadata(title=title, artist=artist, link="", artist_id="", album=title)


def test_youtube_link_uses_matching_provider_metadata(upload):
    resolver = build_resolver(upload, provider_result=song("Water", "Tyla"))

    resource = resolver.resolve(url=LINK)

    assert resource.metadata.album == "Water"
    assert not resource.metadata.is_fallback
    assert resource.video_info is upload


def test_youtube_link_without_provider_metadata_still_resolves(upload):
    resolver = build_resolver(upload, provider_error=SongNotFound("Tyla - Water"))

    resource = resolver.resolve(url=LINK)

    assert resource.metadata.is_fallback
    assert resource.metadata.artist == "Tyla"
    assert resource.video_info is upload


def test_youtube_link_with_mismatched_provider_metadata_falls_back(upload):
    resolver = build_resolver(upload, provider_result=song("Truth or Dare", "Tyla"))

    resource = resolver.resolve(url=LINK)

    assert resource.metadata.is_fallback
    assert resource.metadata.title != "Truth or Dare"


def test_spotify_link_needs_spotify_turned_on(upload):
    resolver = build_resolver(upload)

    with pytest.raises(SpotifyUnavailableError, match="spots_cli setup"):
        resolver.resolve(url="https://open.spotify.com/track/5aIVCx5tnk0ntmdiinnYvw")

    # not retried, and the Spotify id never reaches another provider
    resolver.domain.provider_metadata.get.assert_not_called()


def test_fallback_tags_drop_the_repeated_artist_and_video_tags():
    upload = YTVideoInfo(
        id="kSBQZH3dkZ8",
        title="Tyla - THAT GIRL (Biuro Version) (Official Video)",
        uploader="TylaVEVO",
        audio_ext="webm",
        filesize=4,
    )
    resolver = build_resolver(upload, provider_error=SongNotFound("Tyla - THAT GIRL"))

    metadata = resolver.resolve(url=LINK).metadata

    assert (metadata.artist, metadata.title) == ("Tyla", "THAT GIRL (Biuro Version)")
