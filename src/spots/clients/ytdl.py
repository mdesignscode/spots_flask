from __future__ import annotations

from typing import TYPE_CHECKING
from yt_dlp import YoutubeDL

if TYPE_CHECKING:
    from yt_dlp import _Params


class YtDlpClient:
    """
    A service for interacting with the YouTube DL library.

    Attributes:
        @ydl (YoutubeDL): YouTube DL client.
        @video_to_mp3 (VideoToMp3Service): Service for post-video-downloaded processing.
        @directory_path (str, optional): The directory to save the audio. Defaults to ''.

    Methods:
        @download_youtube_video
    """

    def __init__(
        self,
        *,
        extra_options: _Params = {},
    ):
        """
        Initialize the YtDlpClient.

        Sets up youtube clients.
        """

        self.default_options: _Params = {
            "js_runtimes": {"node": {}},
            "remote_components":  {"ejs:github"},
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "cookiefile": "cookies.txt",
            "noplaylist": True,
            "cachedir": "./yt_cache",
        }
        self.client_options: _Params = self.default_options | extra_options
        self.client = YoutubeDL(self.client_options)

    @property
    def options(self) -> _Params:
        return self.client_options

    @options.setter
    def options(self, extra_options: _Params) -> None:
        self.client_options = self.client_options | extra_options
        self.client = YoutubeDL(self.client_options)

    def reset_options(self) -> None:
        self.client_options = self.default_options
        self.client = YoutubeDL(self.default_options)
