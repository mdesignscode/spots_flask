from __future__ import annotations

from typing import TYPE_CHECKING

from models.yt_video_info import YTVideoInfo
from models.errors import SongNotFound
from models.metadata import Metadata

if TYPE_CHECKING:
    from bootstrap.container import Core, Clients
    from services.spotify_search_service import SpotifySearchService


class YouTubeMetadataService:

    def __init__(
        self,
        spotify_search: SpotifySearchService,
        core: Core,
        clients: Clients
    ):
        self.core = core
        self.clients = clients
        self.spotify_search = spotify_search

    def get(self, video_info: YTVideoInfo) -> Metadata:
        """Retrieves the metadata for a video

        Args:
            video_info (YTVideoInfo): The youtube video info.

        Returns:
            Metadata: the metadata of youtube song
        """
        # get cover from static folder
        static_cover_name = self.clients.secrets.read(
            key="static_cover_name", alt="single-cover.jpg"
        )
        cover = f"http://localhost:5000/{static_cover_name}"

        search_title = f"{video_info.uploader} - {video_info.title}"
        youtube_url = f"https://youtube.com/watch?v={video_info.id}"

        try:
            search_result = self.spotify_search.search_track(search_title)
        except SongNotFound:
            spotify_title = self.core.extractor.remove_odd_keywords(video_info.title)
            spotify_artist = self.core.extractor.remove_odd_keywords(video_info.uploader)
            return Metadata(
                title=spotify_title,
                artist=spotify_artist,
                link=youtube_url,
                cover=cover,
            )

        metadata = search_result

        tracks_match = self.core.matcher.match_tracks(
            video_info=video_info, metadata=metadata
        )

        if tracks_match:
            return metadata
        else:
            return Metadata(
                title=video_info.title,
                artist=video_info.uploader,
                link=youtube_url,
                cover=cover,
            )

