from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from spots.models import YTVideoInfo, Metadata, SongNotFound

if TYPE_CHECKING:
    from spots.bootstrap.container import Core, Clients
    from spots.models import SearchProvider


logger = getLogger(__name__)

class YouTubeMetadataService:

    def __init__(
        self,
        search: SearchProvider,
        core: Core,
        clients: Clients
    ):
        self.core = core
        self.clients = clients
        self.search = search

    def get(self, video_info: YTVideoInfo) -> Metadata:
        """Retrieves the metadata for a video

        Args:
            video_info (YTVideoInfo): The youtube video info.

        Returns:
            Metadata: the metadata of youtube song
        """
        logger.info(f"Retrieving metadata for YouTube video: {video_info.title}")

        # get cover from static folder
        cover = self.clients.secrets.read(key="static_cover_name", alt="single-cover.jpg")

        search_title = video_info.full_title
        youtube_url = f"https://youtube.com/watch?v={video_info.id}"

        try:
            logger.info("Searching for metadata from Provider")
            search_result = self.search.search_track(search_title)
        except SongNotFound:
            spotify_title = self.core.extractor.remove_odd_keywords(video_info.title)
            spotify_artist = self.core.extractor.remove_odd_keywords(video_info.uploader)
            return Metadata(
                title=spotify_title,
                artist=spotify_artist,
                link=youtube_url,
                cover=cover,
                artist_id="",
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
                artist_id="",
            )

