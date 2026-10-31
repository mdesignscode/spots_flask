from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING
from yt_dlp import YoutubeDL

from spots_cli.utils import get_config_path, detect_browser, detect_js_runtimes

if TYPE_CHECKING:
    from yt_dlp import _Params
    from spots_cli.clients import SecretsManager


logger = getLogger(__name__)


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
        secrets: SecretsManager,
    ):
        """
        Initialize the YtDlpClient.

        Sets up youtube clients.
        """
        js_runtimes = detect_js_runtimes()
        if not js_runtimes:
            logger.warning(
                "No JavaScript runtime found (deno, bun or node). YouTube downloads may "
                "fail with HTTP 403. See https://github.com/yt-dlp/yt-dlp/wiki/EJS"
            )

        self.default_options: _Params = {
            "js_runtimes": js_runtimes,
            "remote_components": {"ejs:github"},
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "cachedir": str(get_config_path() / "yt_cache"),
        }
        browser = detect_browser()
        if browser:
            self.default_options["cookiesfrombrowser"] = browser
            cookies_path = secrets.read(key="YOUTUBE_COOKIES_PATH")
            if cookies_path:
                self.default_options["cookiefile"] = cookies_path

        # the baseline every call starts from: defaults, cookies and caller options
        self.base_options: _Params = self.default_options | extra_options
        self.client_options: _Params = self.base_options

        self.client = YoutubeDL(self.client_options)

    @property
    def options(self) -> _Params:
        return self.client_options

    @options.setter
    def options(self, extra_options: _Params) -> None:
        self.client_options = self.client_options | extra_options
        self.client = YoutubeDL(self.client_options)

    def reset_options(self) -> None:
        # keep cookies and caller options; dropping them made later requests
        # run as a different session from the one that extracted the formats
        self.client_options = self.base_options
        self.client = YoutubeDL(self.client_options)
