from unittest.mock import patch

from typer.testing import CliRunner

from spots_cli.cli import app

runner = CliRunner()


def test_download_video_prints_saved_path():
    with patch("spots_cli.cli.Spots") as spots:
        spots.return_value.download_video.return_value = "/Downloads/clip.mp4"
        result = runner.invoke(app, ["download-video", "Tyla That Girl", "-r", "720p"])

    assert result.exit_code == 0
    assert result.output.strip() == "/Downloads/clip.mp4"
    spots.return_value.download_video.assert_called_once_with(
        "Tyla That Girl", resolution="720p"
    )


def test_download_video_defaults_to_best_resolution():
    with patch("spots_cli.cli.Spots") as spots:
        spots.return_value.download_video.return_value = "/Downloads/clip.mp4"
        runner.invoke(app, ["download-video", "https://youtu.be/x"])

    spots.return_value.download_video.assert_called_once_with(
        "https://youtu.be/x", resolution=None
    )


def test_download_video_exits_non_zero_when_nothing_downloaded():
    with patch("spots_cli.cli.Spots") as spots:
        spots.return_value.download_video.return_value = None
        result = runner.invoke(app, ["download-video", "nothing"])

    assert result.exit_code == 1
