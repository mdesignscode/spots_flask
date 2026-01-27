from hashlib import md5
from logging import error, info
from math import ceil
from models.errors import SongNotFound
from models.metadata import Metadata
from models.yt_video_info import YTVideoInfo
from os import path
from services.add_to_history_service import AddToHistoryService
from services.video_to_mp3_service import VideoToMp3Service
from tenacity import stop_after_delay
from engine.retry import retry
from typing import Any, Literal, cast, overload
from yt_dlp import YoutubeDL
from yt_dlp.utils import ExtractorError, DownloadError


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
        from engine import storage

        self._storage = storage

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
    ) -> list[YTVideoInfo]: ...

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
            YTVideoInfo | list[YTVideoInfo]: The extracted info

        Raises:
            SongNotFound: If no result is found.
        """
        search_term = f"ytsearch5:{query}" if is_general_search else query

        if not first_result_only:
            info("Extracting list of videos")
            results = self.ydl.extract_info(search_term, download=False)
            try:
                entries = results["entries"]
                return [self._create_yt_video_obj(entry) for entry in entries]
            except (KeyError, IndexError):
                raise SongNotFound(query)


        return self._storage.get(
            query,
            "ytdl",
            lambda: self._search_on_yt(query, search_term, is_general_search),
        )

    def _search_on_yt(self, cache_query: str, search_term: str, is_general_search: bool) -> YTVideoInfo:
        """
        Searches for a title on YouTube

        Args:
            cache_query (str): the query to add an unavailable video.
            search_term (str): the title to be searched for.
            is_general_search (bool, Optional): True for search term, False for urls. Defaults to True.

        Returns:
            YTVideoInfo

        Raises:
            SongNotFound: if a song is unavailable.
        """
        from engine.file_storage import NOT_FOUND

        try:
            results = self.ydl.extract_info(search_term, download=False)
        except (ExtractorError, DownloadError):
            raise SongNotFound(search_term)

        try:
            first_entry = results if not is_general_search else results["entries"][0]
        except (KeyError, IndexError):
            info(f"[Not found] {cache_query}")
            self._storage.new(
                cache_query.replace(" Audio", ""), NOT_FOUND, query_type="ytdl"
            )
            raise SongNotFound(cache_query)

        video_info = self._create_yt_video_obj(first_entry)
        if not is_general_search:
            self._storage.new(cache_query, video_info, query_type="ytdl")
        return video_info

    def _create_yt_video_obj(self, entry: dict[str, Any]) -> YTVideoInfo:
        """
        Creates a YTVideoInfo object

        Args:
            entry: the search result entry

        Returns:
            YTVideoInfo
        """
        from services.youtube_matcher import YoutubeMatcher

        matcher = YoutubeMatcher()
        title = matcher.remove_odd_keywords(entry.get("title", "Unknown"))
        uploader = matcher.remove_odd_keywords(entry.get("uploader", "Unknown"))
        audio_ext = entry.get("audio_ext", "webm")
        id = cast(str, entry.get("id"))
        filesize = self.get_filesize_mb(entry)

        return YTVideoInfo(
            id=id,
            title=title,
            audio_ext=audio_ext,
            uploader=uploader,
            filesize=filesize,
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

