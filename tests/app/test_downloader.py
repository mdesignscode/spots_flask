from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from spots_cli.app.downloader import Downloader
from spots_cli.models import ResolutionUnavailable, VideoResolution


@pytest.fixture
def downloader(ytdlp) -> Downloader:
    return Downloader(core=Mock(), clients=Mock(ytdlp=ytdlp))


# --- pick_resolution ---------------------------------------------------------


def test_pick_defaults_to_highest(resolutions):
    assert Downloader.pick_resolution(resolutions).label == "1080p"


@pytest.mark.parametrize("label", ["720p", "720", " 720P "])
def test_pick_by_label(resolutions, label):
    assert Downloader.pick_resolution(resolutions, label).format_id == "247"


def test_pick_unavailable_lists_choices_lowest_first(resolutions):
    with pytest.raises(ResolutionUnavailable) as err:
        Downloader.pick_resolution(resolutions, "4320p")

    assert err.value.available == ["360p", "720p", "1080p"]
    assert "4320p is not available" in str(err.value)


def test_pick_with_no_formats():
    with pytest.raises(ResolutionUnavailable):
        Downloader.pick_resolution({})


# --- get_available_resolutions ---------------------------------------------


def test_available_resolutions_keep_best_format_and_add_audio_size(
    downloader, ytdlp, video_info
):
    mb = 1024 * 1024
    ytdlp.client.extract_info.return_value = {
        "formats": [
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "abr": 128, "filesize": 3 * mb},
            {"format_id": "249", "vcodec": "none", "acodec": "opus", "abr": 50, "filesize": 1 * mb},
            {"format_id": "136", "height": 720, "vcodec": "avc1", "acodec": "none", "filesize": 20 * mb},
            {"format_id": "247", "height": 720, "vcodec": "vp9", "acodec": "none", "filesize": 10 * mb},
            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "filesize": 5 * mb},
        ]
    }

    found = downloader.get_available_resolutions(video_info=video_info)

    assert set(found) == {"720p", "360p"}
    assert found["720p"].format_id == "136"
    assert found["720p"].filesize_mb == 23  # video + best audio track
    assert found["360p"].filesize_mb == 5  # already has audio
    ytdlp.client.extract_info.assert_called_once_with(
        "https://youtube.com/watch?v=kSBQZH3dkZ8", download=False
    )
    ytdlp.reset_options.assert_called_once()


# --- download_video ----------------------------------------------------------


def downloaded(path: str) -> dict:
    return {"requested_downloads": [{"filepath": path}]}


def test_download_merges_audio_for_video_only_format(
    downloader, ytdlp, video_info, resolutions, tmp_path
):
    ytdlp.client.extract_info.return_value = downloaded("/x/Tyla - THAT GIRL.mp4")

    with patch.object(Downloader, "_download_folder", return_value=str(tmp_path)):
        path = downloader.download_video(
            video_info=video_info, resolution=resolutions["1080p"]
        )

    assert path == "/x/Tyla - THAT GIRL.mp4"
    assert ytdlp.options["format"] == "137+bestaudio/best"
    assert ytdlp.options["outtmpl"] == str(tmp_path / "Tyla - THAT GIRL.%(ext)s")
    assert ytdlp.options["merge_output_format"] == "mp4"
    ytdlp.client.extract_info.assert_called_once_with(
        "https://youtube.com/watch?v=kSBQZH3dkZ8", download=True
    )
    ytdlp.reset_options.assert_called_once()


def test_download_progressive_format_as_is(downloader, ytdlp, video_info, resolutions):
    ytdlp.client.extract_info.return_value = downloaded("/x/a.mp4")
    downloader.download_video(video_info=video_info, resolution=resolutions["360p"])
    assert ytdlp.options["format"] == "18"


def test_download_by_label_looks_up_resolutions(downloader, ytdlp, video_info, resolutions):
    ytdlp.client.extract_info.return_value = downloaded("/x/a.mp4")
    with patch.object(Downloader, "get_available_resolutions", return_value=resolutions):
        downloader.download_video(video_info=video_info, resolution="720p")
    assert ytdlp.options["format"] == "247+bestaudio/best"


def test_download_defaults_to_highest(downloader, ytdlp, video_info, resolutions):
    ytdlp.client.extract_info.return_value = downloaded("/x/a.mp4")
    with patch.object(Downloader, "get_available_resolutions", return_value=resolutions):
        downloader.download_video(video_info=video_info)
    assert ytdlp.options["format"] == "137+bestaudio/best"


def test_download_unavailable_label_downloads_nothing(
    downloader, ytdlp, video_info, resolutions
):
    with patch.object(Downloader, "get_available_resolutions", return_value=resolutions):
        with pytest.raises(ResolutionUnavailable):
            downloader.download_video(video_info=video_info, resolution="4k")
    ytdlp.client.extract_info.assert_not_called()


def test_options_reset_even_when_download_fails(downloader, ytdlp, video_info, resolutions):
    ytdlp.client.extract_info.side_effect = RuntimeError("HTTP Error 403")
    with pytest.raises(RuntimeError):
        downloader.download_video(video_info=video_info, resolution=resolutions["360p"])
    ytdlp.reset_options.assert_called_once()


# --- naming --------------------------------------------------------------------


def test_filename_replaces_slashes(video_info):
    video_info.title = "AC/DC"
    assert Downloader._filename(video_info) == "Tyla - AC|DC"


def test_filename_hashes_overlong_titles(video_info):
    video_info.title = "x" * 300
    assert len(Downloader._filename(video_info)) == 25


def test_download_folder_falls_back_to_home(tmp_path):
    with patch("spots_cli.app.downloader.Path.home", return_value=tmp_path):
        assert Downloader._download_folder("clips") == str(tmp_path / "clips")
        (tmp_path / "Downloads").mkdir()
        assert Downloader._download_folder("clips") == str(tmp_path / "Downloads" / "clips")
