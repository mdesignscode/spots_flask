from os import path
from hashlib import md5
from typing import Any, Literal, cast, overload
from models.metadata import Metadata
from yt_dlp import YoutubeDL
from math import ceil
from engine import storage
from logging import INFO, basicConfig, error, info
from models.errors import SongNotFound
from models.yt_video_info import YTVideoInfo
from tenacity import retry, stop_after_delay
from services.add_to_history_service import AddToHistoryService
from services.video_to_mp3_service import VideoToMp3Service


basicConfig(level=INFO)


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
        video_to_mp3: VideoToMp3Service = VideoToMp3Service(),
        directory_path: str = ".",
        options: dict[str, Any] | None = None,
    ):
        """
        Initialize the YtDlpClient.

        Sets up youtube clients.
        """
        self.options = (
            {
                "js_runtimes": {"node": {}},
                "format": "bestaudio/best",
                "outtmpl": path.join(directory_path, "%(title)s.%(ext)s"),
                "quiet": True,
                "cookiefile": "cookies.txt",
                "outtmpl": "%(title)s.%(ext)s",
                "noplaylist": True,
                "cachedir": "./yt_cache",
            }
            if not options
            else options
        )
        self.ydl = YoutubeDL(self.options)
        self.video_to_mp3 = video_to_mp3
        self.directory_path = directory_path

    @overload
    def search(
        self,
        query: str,
        first_result_only: Literal[True],
        is_general_search: bool = True,
    ) -> YTVideoInfo: ...
    @overload
    def search(
        self,
        query: str,
        first_result_only: Literal[False],
        is_general_search: bool = True,
    ) -> dict[str, Any]: ...

    def search(
            self, query: str, first_result_only: bool = True, is_general_search: bool = True
    ):
        """
        Extracts partial data from a YouTube search result.

        Args:
            query (str): The search term.
            first_result_only (bool, Optional): Determines whether to return only search result.
            is_general_search (bool, Optional): True for search term, False for urls. Defaults to True.

        Returns:
            YTVideoInfo: The extracted info

        Raises:
            SongNotFound: If no result is found.
        """
        from engine import storage

        if not first_result_only:
            return self.ydl.extract_info(query, download=False)

        def yt_search():
            from engine.file_storage import NOT_FOUND
            search_term = f"ytsearch:{query}" if is_general_search else query
            results = self.ydl.extract_info(search_term, download=False)

            try:
                first_entry = results["entries"][0]
            except:
                info(f"[Not found] {query}")
                storage.new(query, NOT_FOUND, "ytdl")
                raise SongNotFound(query)

            from services.youtube_matcher import YoutubeMatcher
            matcher = YoutubeMatcher()
            title = matcher.remove_odd_keywords(first_entry.get("title", "Unknown"))
            uploader = matcher.remove_odd_keywords(first_entry.get("uploader", "Unknown"))
            audio_ext = first_entry.get("audio_ext", "webm")
            id = first_entry.get("id")
            filesize = self.get_filesize_mb(first_entry)

            return YTVideoInfo(
                id=id,
                title=title,
                audio_ext=audio_ext,
                uploader=uploader,
                filesize=filesize,
            )

        return storage.get(
            query,
            "ytdl",
            yt_search,
        )

    def get_filesize_mb(self, info: dict) -> int:
        size = info.get("filesize") or info.get("filesize_approx")
        return ceil(size / (1024 * 1024)) if size else 0

    def download(self, url: str, filename: str):
        opts = {
            "outtmpl": f"{self.directory_path}/{filename}",
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

    def download_youtube_video(
        self, youtube_url: str, spotify_track: Metadata, get_size=False
    ):
        """Downloads a YouTube video as audio, or returns the file size of the video.

        Args:
            spotify_track (Metadata): The spotify metadata of the video.
            youtube_url (str): The YouTube url to be downloaded.
            get_size (bool, optional): If True, only calculate the size of the audio. Defaults to False.

        Returns:
            float | None: The size of the video in MB, if get_size is True.
        """
        # Add title to downloads history
        track_title = f"{spotify_track.artist} - {spotify_track.title}"
        # '/' will read file name as folder in *nix systems
        track_title = track_title.replace("/", "|")

        # return if song already downloaded
        if not get_size:
            AddToHistoryService.add_to_download_history(track_title)

        video_info = self.search(youtube_url, True, is_general_search=False)

        filename = video_info.title
        ext = video_info.audio_ext

        # Check if the file name length is too long, truncate if necessary
        max_filename_length = 255  # Maximum allowed file name length on most systems
        if len(filename) > max_filename_length:
            file_hash = md5(track_title.encode()).hexdigest()
            filename = f"{file_hash[:25]}.{ext}"

        return self.download_with_ytdlp(
            track_title, youtube_url, spotify_track, get_size
        )

    def download_with_ytdlp(
        self,
        track_title: str,
        youtube_url: str,
        metadata: Metadata,
        get_size: bool = False,
    ):
        """download audio using yt-dlp.

        Args:
            track_title (str): The title of the track.
            get_size (bool, optional): If True, only calculate the size of the audio. Defaults to False.

        Returns:
            float | None: The size of the video in MB, if get_size is True.
        """
        # check cached response for getting size only
        if get_size:
            video_info = self.search(youtube_url, True, is_general_search=False)
            return video_info.filesize

        try:
            info(f"Processing {track_title} using yt-dlp...")
            video_info = self.search(youtube_url, True, is_general_search=False)

            # Dynamically infer the downloaded file extension
            artist = f"{video_info.uploader} - " if video_info.uploader else ""
            filename = f"{artist}{video_info.title}.{video_info.audio_ext}"
            ext = video_info.audio_ext
            final_path = filename.rsplit(".", 1)[0] + ".mp3"
            watch_url = f"https://www.youtube.com/watch?v=" + video_info.id
            self.download(watch_url, filename)

            # Convert file to MP3 if necessary
            if ext != "mp3":
                self.video_to_mp3.convert_to_mp3(
                    filename, final_path, track_title, metadata
                )
            else:
                error(f"Audio already in MP3 format: {filename}")

            # Update metadata if Spotify track information is available
            self.video_to_mp3.update_metadata(final_path, metadata)

            info(f"Audio downloaded successfully with yt-dlp: {final_path}")
        except Exception as e:
            raise Exception(f"yt-dlp failed for {youtube_url}: {e}")

