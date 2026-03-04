from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.spotify_metadata_service import SpotifyMetadataService
    from services.youtube_metadata_service import YouTubeMetadataService


class MetadataOrchestrator:
    def __init__(self, *, youtube_metadata: YouTubeMetadataService, spotify_metadata: SpotifyMetadataService):
        self.spotify_metadata = spotify_metadata
        self.youtube_metadata = youtube_metadata

