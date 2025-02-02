#!/usr/bin/python3
"""A class that searches for a track from youtube on spotify"""

from __future__ import unicode_literals
from engine import storage
from html import unescape
from logging import basicConfig, error, ERROR, info, INFO
from typing import cast
from flask import url_for
from models.errors import InvalidURL, SongNotFound, TitleExistsError
from models.spotify_worker import SpotifyWorker, Metadata
from models.spotify_to_youtube import ProcessSpotifyLink
from re import search, compile, escape
from tenacity import retry, stop_after_delay
from yt_dlp import YoutubeDL


class ProcessYoutubeLink(SpotifyWorker, ProcessSpotifyLink):
    """Searches for a track from youtube on spotify"""

    def __init__(
        self,
        youtube_url: str = "",
        search_title: str = "",
        metadata: Metadata | None = None,
    ):
        """initializes the url for title to be searched for

        Args:
            youtube_url (str, optional): the url to be processed. Defaults to ''.
            search_title (str, optional): a title to be searched for. Defaults to ''.
            metadata (Metadata, optional): a spotify metadata object. Defaults to None.
        """
        SpotifyWorker.__init__(self)

        self.title = search_title

        if metadata and youtube_url:
            ProcessSpotifyLink.__init__(self, metadata, youtube_url)
            return

        if youtube_url:
            self.youtube_url = youtube_url
            return

        if metadata:
            ProcessSpotifyLink.__init__(self, metadata)
            return

    def process_youtube_url(self, single_only: bool = False, default_cover: str = "") -> Metadata | None:
        """Processes a youtube url and returns the metadata for video

        Args:
            single_only (boolean, optional): whether to retrieve the recommended tracks or not. Defaults to False
            default_cover (str, optional): Fallback cover url.

        Returns:
            Metadata: the metadata of youtube song
        """
        basicConfig(level=INFO)
        info(f"Processing youtube url: {self.youtube_url}")

        try:
            artist, title, _ = self.get_title()
        except SongNotFound as e:
            info(f"No results for: {self.youtube_url}")
            raise e

        info(f"Found: {title} by {artist}")

        # get cover from static folder
        static_cover = f'http://localhost:5000{url_for("static", filename="single-cover.jpg")}'
        cover = default_cover if default_cover else static_cover

        search_title = f"{artist} - {title}"

        # get metadata for youtube title
        metadata = self.search_track(search_title, single_only)

        if not metadata:
            info(f"No spotify results for {search_title}")
            return Metadata(title, artist, self.youtube_url, cover)

        metadata = metadata[0]

        query = f"{metadata.artist} - {metadata.title}"

        # if youtube video matches spotify track
        if search(artist, query) and search(title, query):
            # initialize parent
            ProcessSpotifyLink.__init__(self, metadata, self.youtube_url)
            return metadata

        # else download from youtube without editing metadata
        else:
            # create metadata object
            metadata = Metadata(title, artist, self.youtube_url, cover)

            # initialize parent
            ProcessSpotifyLink.__init__(self, metadata, self.youtube_url)
            return metadata
        return pattern.sub("", string)

    @retry(stop=stop_after_delay(max_delay=120))
    def get_title(self) -> tuple[str, str, int]:
        """Retrieve artist and title on YouTube video object

        Returns:
            tuple[str,str, float]: the video author and title, and the video size in MB

        Raises:
            InvalidURL: if invalid YouTube video url provided
        """
        options = {
            'format': 'bestaudio/best',
            'quiet': True,
            'cookiefile': 'cookies.txt',  # Path to your cookies file
            'outtmpl': '%(title)s.%(ext)s',
        }

        with YoutubeDL(options) as ydl:
            youtube = ydl

        # check cache
        cache = storage.get(self.youtube_url, "ytdl")
        if cache:
            info(f"Cached response: {cache['title']}")
            search_response = cache

        else:
            search_response = youtube.extract_info(self.youtube_url, download=False)
            storage.new(self.youtube_url, search_response, "ytdl")

        if not search_response:
            basicConfig(level=ERROR)
            error(f"{self.youtube_url} is not available")
            raise SongNotFound(self.youtube_url)

        result_title = search_response.get("title")

        # Decode the string
        try:
            youtube_video_title = unescape(result_title)
        except TypeError:
            youtube_video_title = result_title

        youtube_video_title = self.remove_odd_keywords(youtube_video_title)

        # determine if original artist uploaded video
        split_title = youtube_video_title.split("-")
        artist = split_title[0].strip() if len(split_title) > 1 else search_response["uploader"]

        title = (
            split_title[1]
            if "-" in youtube_video_title
            else youtube_video_title
        )

        # check if ProcessSpotifyLink is initialized
        try:
            file_size = cast(int, self.download_youtube_video(get_size=True))
        except AttributeError:
            # caller doesn't need file size
            file_size = 0
        except Exception as e:
            error(f"Error occured: {e}")
            raise e

        return artist, title, file_size

    def download_title(self) -> None:
        # download video as audio
        self.download_youtube_video()

