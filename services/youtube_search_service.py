from __future__ import unicode_literals
from os import getenv
from html import unescape
from logging import error, info
from flask import url_for
from models.errors import SongNotFound
from models.metadata import Metadata
from models.yt_video_info import YTVideoInfo
from services.youtube_matcher import YoutubeMatcher
from services.ytdlp_client import YtDlpClient
from tenacity import stop_after_delay
from engine.retry import retry


class YoutubeSearchService:
    """
    A service responsible for performing searches on YouTube.

    Attributes:
        @ytdlp (YtDlpClient): A YouTube dlp client service.
        @matcher (YoutubeMatcher): A service for matching titles.

    Methods:
        @search_best_match

        @get_title

        @process_spotify_title

        @process_youtube_url
    """

    def __init__(
        self,
        ytdlp: YtDlpClient = YtDlpClient(),
        matcher: YoutubeMatcher = YoutubeMatcher(),
    ):
        """
        Initialize the YoutubeSearchService.

        Sets up ytdlp and matcher clients.
        """
        self.ytdlp = ytdlp
        self.matcher = matcher

        from engine import storage

        self._storage = storage

    def search_best_match(self, metadata: Metadata, search_title: str = "") -> str:
        """
        Searches for the best title matched result on YouTube.

        Args:
            metadata (Metadata): Metadata object containing song information.
            search_title: The title to search for if metadata is not present. Defaults to "".

        Returns:
            str | None: The url to the best matched title. None if no match found.

        Raises:
            SongNotFound: If no search result or match is found.
        """

        from engine.file_storage import NOT_FOUND

        def save_match(entry):
            video_info = YTVideoInfo(
                id=entry.id,
                title=entry.title,
                uploader=entry.uploader,
                audio_ext=entry.audio_ext,
                filesize=entry.filesize,
            )
            watch_url = base_url + video_info.id
            # cache search query
            self._storage.new(original_title, video_info, query_type="ytdl")
            # and youtube url
            self._storage.new(watch_url, video_info, query_type="ytdl")

            return watch_url

        # search for audio version
        search_query = (
            f"{search_title} Audio"
            if search_title
            else f"{metadata.artist} - {metadata.title} Audio"
        )
        search_query = self.matcher.remove_odd_keywords(search_query)
        original_title = search_query.replace(" Audio", "")
        info(f"[Best Match] Searching for {search_query} on YouTube...")

        base_url = f"https://www.youtube.com/watch?v="

        # search for audio version
        video_info = self.ytdlp.search(search_query, True)

        yt_title = self.matcher.remove_odd_keywords(video_info.title)
        pattern = search_query.replace(" Audio", "")
        titles_match = self.matcher.match_titles(pattern, yt_title)

        if titles_match:
            return save_match(video_info)
        else:
            info("Searching for video version")
            print(f"\n\nAudio not match:\nYT title: {yt_title}\nPattern: {pattern}\n\n")

            # search for video version
            video_pattern = search_query.replace(" Audio", "")
            video_info = self.ytdlp.search(video_pattern, True)

            yt_title = self.matcher.remove_odd_keywords(video_info.title)
            video_titles_match = self.matcher.match_titles(video_pattern, yt_title)

            if not video_titles_match:
                print(
                    f"\n\nVideo not match either:\nYT title: {yt_title}\nPattern: {pattern}\n\n"
                )
                info(f"No match found for: {search_query}")
                self._storage.new(original_title, NOT_FOUND, query_type="ytdl")
                raise SongNotFound(search_query)
            else:
                return save_match(video_info)

    @retry(stop=stop_after_delay(max_delay=120))
    def get_title(self, youtube_url: str) -> tuple[str, str, int]:
        """Retrieve artist and title on YouTube video object

        Args:
            youtube_url (str): The link to retrieve the title from.

        Returns:
            tuple[str, str, float]: the video author and title, and the video size in MB

        Raises:
            InvalidURL: if invalid YouTube video url provided
        """
        search_response = self.ytdlp.search(youtube_url, True, is_general_search=False)

        result_title = search_response.title

        # Decode the string
        try:
            youtube_video_title = unescape(result_title)
        except TypeError:
            youtube_video_title = result_title
        except Exception as e:
            error(f"Unhandled error occurred while retrieving title: {e}")
            raise e

        youtube_video_title = self.matcher.remove_odd_keywords(youtube_video_title)

        # determine if original artist uploaded video
        split_title = youtube_video_title.split("-")
        artist = (
            split_title[0].strip() if len(split_title) > 1 else search_response.uploader
        )
        artist = self.matcher.remove_odd_keywords(artist)
        title = split_title[1] if "-" in youtube_video_title else youtube_video_title

        # sync cache with heuristic artist and title
        self._storage.update_ytdl(youtube_url, uploader=artist, title=title)

        video_info = artist, title, search_response.filesize

        print(f"Video title: {youtube_video_title}\nArtist: {artist}\nTitle: {title}\n\n")
        return video_info

    def process_spotify_title(self, metadata: Metadata) -> tuple[str, str, float]:
        """
        Searches for a spotify title on YouTube.

        Args:
            title (Metadata): Spotify search result.

        Returns:
            tuple[str,str, float]: the video author and title, and the video size in MB
        """
        yt_url = self.search_best_match(metadata)
        if not yt_url:
            raise SongNotFound(f"{metadata.artist} - {metadata.title}")

        return self.get_title(yt_url)

    def process_youtube_url(
        self, youtube_url: str, single_only: bool = True, default_cover: str = ""
    ) -> Metadata:
        """Processes a youtube url and returns the metadata for video

        Args:
            youtube_url (str): The youtube url to be processed.
            single_only (boolean, optional): whether to retrieve the recommended tracks or not. Defaults to True
            default_cover (str, optional): Fallback cover url.

        Returns:
            Metadata: the metadata of youtube song
        """
        info(f"Processing youtube url: {youtube_url}")

        try:
            artist, title, _ = self.get_title(youtube_url)
        except SongNotFound as e:
            info(f"No results for: {youtube_url}")
            raise e

        info(f"Found: {title} by {artist}")

        # get cover from static folder
        static_cover_name = getenv("static_cover_name", "single-cover.jpg")
        static_cover = (
            f'http://localhost:5000{url_for("static", filename=static_cover_name)}'
        )
        cover = default_cover if default_cover else static_cover

        search_title = f"{artist} - {title}"

        # get metadata for youtube title
        from models.spotify_worker import SpotifyWorker

        spotify = SpotifyWorker()
        try:
            metadata = spotify.search_track(search_title, single_only)
        except SongNotFound:
            info(f"No spotify results for {search_title}")
            return Metadata(title, artist, youtube_url, cover)

        metadata = metadata[0]

        query = f"{metadata.artist} - {metadata.title}"

        search_title_match = self.matcher.match_titles(search_title, query)
        query_match = self.matcher.match_titles(query, search_title)

        # if youtube video matches spotify track
        if search_title_match or query_match:
            return metadata

        # else download from youtube without editing metadata
        else:
            # create metadata object
            return Metadata(title, artist, youtube_url, cover)

