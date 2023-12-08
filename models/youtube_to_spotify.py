#!/usr/bin/python3
"""A class that searches for a track from youtube on spotify"""

from __future__ import unicode_literals
from html import unescape
from logging import basicConfig, error, ERROR
from typing import cast
from flask import url_for
from models.errors import InvalidURL, TitleExistsError
from models.get_spotify_track import GetSpotifyTrack, Metadata
from os import getenv
from models.spotify_to_youtube import ProcessSpotifyLink
from pytube import YouTube
from re import search


class ProcessYoutubeLink(GetSpotifyTrack, ProcessSpotifyLink):
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
        GetSpotifyTrack.__init__(self)

        self.title = search_title

        if metadata and youtube_url:
            ProcessSpotifyLink.__init__(self, metadata, youtube_url)
            return

        if youtube_url:
            self.youtube_url = youtube_url
            self.youtube = YouTube(
                self.youtube_url, use_oauth=bool(getenv("use_oauth"))
            )
            return

        elif metadata:
            ProcessSpotifyLink.__init__(self, metadata)
            return

    async def process_youtube_url(self) -> Metadata | None:
        """Processes a youtube url and returns the metadata for video

        Returns:
            Metadata: the metadata of youtube song
        """
        try:
            artist, title, _ = self.get_title()
        except InvalidURL:
            return

        # get cover from static folder
        cover = url_for("static", filename="single-cover.jpg")

        search_title = f"{artist} - {title}"

        # get metadata for youtube title
        metadata = await self.search_track(search_title)

        if not metadata:
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

    def get_title(self) -> tuple[str, str, int]:
        """Retrieve artist and title on YouTube video object

        Returns:
            tuple[str,str, float]: the video author and title, and the video size in MB

        Raises:
            InvalidURL: if invalid YouTube video url provided
        """
        # check url availability
        search_response = self.youtube
        if not search_response:
            basicConfig(level=ERROR)
            error(f"{self.youtube_url} is not available")
            raise InvalidURL(self.youtube_url)

        search_response.check_availability()

        result_title = search_response.title

        # Decode the string
        try:
            youtube_video_title = unescape(result_title)
        except TypeError:
            youtube_video_title = result_title

        # remove unnecessary keywords from title
        youtube_video_title = youtube_video_title.replace(" (Audio Visual)", "")
        youtube_video_title = youtube_video_title.replace(" (Official Audio)", "")
        youtube_video_title = youtube_video_title.replace(" (Official Video)", "")
        youtube_video_title = youtube_video_title.replace(" (Audio)", "")
        youtube_video_title = youtube_video_title.replace(" Uncut [HD]", "")
        youtube_video_title = youtube_video_title.replace(" [Video]", "")
        youtube_video_title = youtube_video_title.replace(" (HD)", "")
        youtube_video_title = youtube_video_title.replace(" (Official Music Video)", "")
        youtube_video_title = youtube_video_title.replace(" [Official Music Video]", "")
        youtube_video_title = youtube_video_title.replace(" - Topic", "")
        youtube_video_title = youtube_video_title.replace(" (Official Visualizer)", "")
        youtube_video_title = youtube_video_title.replace(" (Complete)", "")
        youtube_video_title = youtube_video_title.replace(" (Visualizer)", "")

        # determine if original artist uploaded video
        artist = (
            search_response.author
            if search_response.author
            else youtube_video_title.split("-")[0]
        )

        title = (
            youtube_video_title.split("-")[1]
            if "-" in youtube_video_title
            else youtube_video_title
        )

        file_size = cast(int, self.download_youtube_video(get_size=True))

        return artist, title, file_size

    def download_title(self) -> None:
        # download video as audio
        self.download_youtube_video()
