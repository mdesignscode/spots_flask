from __future__ import annotations

from models import MetadataProvider
from services.deezer_metadata_service import DeezerMetadataService
from services.spotify_metadata_service import SpotifyMetadataService
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bootstrap.container import Clients, Core

class ProvidersMetadata:
    def __init__(self, *, clients: Clients, core: Core):
        media_providers: dict[str, type[MetadataProvider]] = {
            "deezer": DeezerMetadataService,
            "spotify": SpotifyMetadataService,
        }

        default_provider = clients.secrets.read(key="main_provider", alt="deezer")

        provider_cls = media_providers[default_provider]
        self.metadata = provider_cls(core=core, clients=clients)

