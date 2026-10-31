import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# the API is run from api/ and imports its package as `server`
sys.path.insert(0, str(Path(__file__).parents[2] / "api"))

from server import app  # noqa: E402
from spots_cli.models import (  # noqa: E402
    ResolutionUnavailable,
    SearchResponseMultiple,
    SearchResponseSingle,
    SongNotFound,
    VideoResolution,
)

VIDEO = {
    "id": "kSBQZH3dkZ8",
    "title": "THAT GIRL",
    "uploader": "Tyla",
    "audio_ext": "webm",
    "filesize": 48,
}


@pytest.fixture
def bootstrapper():
    mock = Mock()
    mock.app.downloader.download_video.return_value = "/Downloads/Tyla - THAT GIRL.mp4"
    with patch("server.download_video.bootstrapper", mock):
        yield mock


@pytest.fixture
def client():
    return app.test_client()


def download_call(bootstrapper) -> dict:
    return bootstrapper.app.downloader.download_video.call_args.kwargs


def test_video_info_with_resolution_object(client, bootstrapper):
    resolution = {"format_id": "137", "height": 1080, "ext": "mp4", "vcodec": "avc1", "acodec": "none"}
    res = client.post("/download/video", json=VIDEO | {"resolution": resolution})

    assert res.status_code == 200
    assert res.json == {"message": "Successfully downloaded", "file": "/Downloads/Tyla - THAT GIRL.mp4"}
    assert isinstance(download_call(bootstrapper)["resolution"], VideoResolution)
    assert download_call(bootstrapper)["video_info"].id == "kSBQZH3dkZ8"


def test_query_url_with_resolution_label(client, bootstrapper, video_info):
    search = bootstrapper.domain.youtube_search.video_search
    search.return_value = SearchResponseSingle(result=video_info, is_cached=False)
    url = "https://youtube.com/watch?v=kSBQZH3dkZ8"

    res = client.post("/download/video", json={"query": url, "resolution": "720p"})

    assert res.status_code == 200
    search.assert_called_once_with(query=url, is_general_search=False)
    assert download_call(bootstrapper) == {
        "video_info": video_info,
        "resolution": "720p",
        "directory_path": "",
    }


def test_query_search_terms_use_top_result_and_best_resolution(client, bootstrapper, video_info):
    search = bootstrapper.domain.youtube_search.video_search
    search.return_value = SearchResponseMultiple(result=[video_info, Mock()], is_cached=False)

    res = client.post("/download/video", json={"query": "Tyla That Girl"})

    assert res.status_code == 200
    search.assert_called_once_with(query="Tyla That Girl", is_general_search=True)
    assert download_call(bootstrapper)["video_info"] is video_info
    assert download_call(bootstrapper)["resolution"] is None


def test_query_not_found(client, bootstrapper):
    bootstrapper.domain.youtube_search.video_search.side_effect = SongNotFound("x")
    res = client.post("/download/video", json={"query": "x"})
    assert res.status_code == 404


def test_unavailable_resolution_lists_choices(client, bootstrapper):
    bootstrapper.app.downloader.download_video.side_effect = ResolutionUnavailable(
        "4320p", ["360p", "1080p"]
    )
    res = client.post("/download/video", json=VIDEO | {"resolution": "4320p"})

    assert res.status_code == 400
    assert res.json["available"] == ["360p", "1080p"]


@pytest.mark.parametrize(
    "body",
    [
        {},  # no video
        {"query": ""},
        {"query": 5},
        VIDEO | {"resolution": 720},
        VIDEO | {"resolution": {"format_id": "137"}},
        VIDEO | {"directory_path": "/etc"},
        VIDEO | {"directory_path": "../../outside"},
    ],
)
def test_bad_requests(client, bootstrapper, body):
    res = client.post("/download/video", json=body)
    assert res.status_code == 400
    bootstrapper.app.downloader.download_video.assert_not_called()


def test_download_failure(client, bootstrapper):
    bootstrapper.app.downloader.download_video.side_effect = RuntimeError("HTTP Error 403")
    res = client.post("/download/video", json=VIDEO)
    assert res.status_code == 500


def test_sub_folder_is_passed_through(client, bootstrapper):
    client.post("/download/video", json=VIDEO | {"directory_path": "clips/tyla"})
    assert download_call(bootstrapper)["directory_path"] == "clips/tyla"
