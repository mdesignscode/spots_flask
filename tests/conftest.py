"""Shared test setup.

Points the config directory at a throwaway folder *before* spots_cli is
imported, so tests never read or write the real ~/.config/spots_cli (its
.env, cache and download history).
"""

import os
import tempfile
from unittest.mock import Mock

import pytest

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="spots-test-config-")

from spots_cli.models import VideoResolution, YTVideoInfo  # noqa: E402


@pytest.fixture
def video_info() -> YTVideoInfo:
    return YTVideoInfo(
        id="kSBQZH3dkZ8",
        title="THAT GIRL",
        uploader="Tyla",
        audio_ext="webm",
        filesize=48,
    )


@pytest.fixture
def resolutions() -> dict[str, VideoResolution]:
    return {
        "360p": VideoResolution(
            format_id="18", height=360, ext="mp4", vcodec="avc1", acodec="mp4a"
        ),
        "1080p": VideoResolution(
            format_id="137", height=1080, ext="mp4", vcodec="avc1", acodec="none"
        ),
        "720p": VideoResolution(
            format_id="247", height=720, ext="webm", vcodec="vp9", acodec="none"
        ),
    }


@pytest.fixture
def ytdlp() -> Mock:
    """A stand-in for YtDlpClient: records options, never touches the network."""
    client = Mock()
    client.options = {}
    return client
