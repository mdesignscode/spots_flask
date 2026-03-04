from typing import Any
from yt_dlp import YoutubeDL


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
        extra_options: dict[str, Any] = {},
    ):
        """
        Initialize the YtDlpClient.

        Sets up youtube clients.
        """

        self.client_options = {
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "cookiefile": "cookies.txt",
            "noplaylist": True,
            "cachedir": "./yt_cache",
        } | extra_options
        self.ydl = YoutubeDL(self.options)

    @property
    def options(self):
        return self.client_options

    @options.setter
    def options(self, extra_options: dict[str, Any]):
        self.options = self.client_options | extra_options

