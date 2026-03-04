from __future__ import annotations

from hashlib import md5
from models.errors import TitleExistsError
from models.metadata import Metadata
from models.yt_video_info import YTVideoInfo
from os.path import join
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Core, Clients


class Downloader:
    """A service for interacting with YouTube."""

    def __init__(self, *, core: Core, clients: Clients):
        self.core = core
        self.clients = clients

    def download(
        self, *, video_info: YTVideoInfo, metadata: Metadata, directory_path: str = ""
    ) -> bool:
        """Downloads a YouTube video as mp3

        Args:
            video_info (YTVideoInfo): the extracted info.
            directory_path (str, Optional): the folder to be downloaded to. Defaults to the root of the Music folder.

        Returns:
            bool: True if downloaded successfully.
        """
        url = "https://youtube.com/watch?v=" + video_info.id
        title = f"{video_info.uploader} - {video_info.title}"

        # normalize title
        # '/' will read file name as folder in *nix systems
        filename = title.replace("/", "|")
        # Check if the file name length is too long, truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            file_hash = md5(filename.encode()).hexdigest()
            filename = file_hash[:25]

        # check if downloaded already
        if self.core.history.read(filename):
            raise TitleExistsError(filename)

        download_path = join(
            "Music", directory_path, f"{filename}.{video_info.audio_ext}"
        )
        converted_path = join("Music", directory_path, f"{filename}.mp3")

        # set template for download titles
        self.clients.ytdlp.options = {"outtmpl": download_path}

        # download video
        self.clients.ytdlp.ydl.download([url])

        # post download processing
        converted = self.core.converter.convert_to_mp3(
            old_file=download_path, new_file=converted_path
        )
        if converted:
            metadata_updated = self.core.converter.update_metadata(
                audio_path=converted_path, metadata=metadata
            )
            if metadata_updated:
                self.core.history.write(filename)
        else:
            return False

        return True

