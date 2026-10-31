from unittest.mock import Mock

import pytest

from spots_cli import Spots
from spots_cli.models import (
    ResolutionUnavailable,
    SearchResponseMultiple,
    SearchResponseSingle,
    SongNotFound,
)


@pytest.fixture
def spots() -> Spots:
    # skip __init__: it runs the interactive first-time setup
    app = Spots.__new__(Spots)
    app.container = Mock()
    app.downloader = app.container.app.downloader
    app.downloader.download_video.return_value = "/Downloads/Tyla - THAT GIRL.mp4"
    return app


def search(spots: Spots) -> Mock:
    return spots.container.domain.youtube_search.video_search


def test_url_is_looked_up_directly(spots, video_info):
    search(spots).return_value = SearchResponseSingle(result=video_info, is_cached=False)
    url = "https://youtube.com/watch?v=kSBQZH3dkZ8"

    path = spots.download_video(url, resolution="720p", directory_path="clips")

    assert path == "/Downloads/Tyla - THAT GIRL.mp4"
    search(spots).assert_called_once_with(query=url, is_general_search=False)
    spots.downloader.download_video.assert_called_once_with(
        video_info=video_info, resolution="720p", directory_path="clips"
    )
    spots.container.core.storage.save.assert_called_once()


def test_search_terms_use_top_result(spots, video_info):
    other = Mock()
    search(spots).return_value = SearchResponseMultiple(
        result=[video_info, other], is_cached=False
    )

    spots.download_video("Tyla That Girl")

    search(spots).assert_called_once_with(query="Tyla That Girl", is_general_search=True)
    assert spots.downloader.download_video.call_args.kwargs["video_info"] is video_info
    assert spots.downloader.download_video.call_args.kwargs["resolution"] is None


@pytest.mark.parametrize(
    "error", [SongNotFound("nothing"), ResolutionUnavailable("4k", ["720p"])]
)
def test_expected_failures_return_none(spots, video_info, error, caplog):
    search(spots).return_value = SearchResponseSingle(result=video_info, is_cached=False)
    spots.downloader.download_video.side_effect = error

    assert spots.download_video("https://youtu.be/x") is None
    assert error.message in caplog.text
    spots.container.core.storage.save.assert_called_once()
