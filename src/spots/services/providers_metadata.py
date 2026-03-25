from __future__ import annotations

from spots.models import MetadataProvider
from spots.services import DeezerMetadataService, SpotifyMetadataService
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots.bootstrap.container import Clients, Core

class ProvidersMetadata:
    def __init__(self, *, clients: Clients, core: Core):
        media_providers: dict[str, type[MetadataProvider]] = {
            "deezer": DeezerMetadataService,
            "spotify": SpotifyMetadataService,
        }

        default_provider = clients.secrets.read(key="main_provider", alt="deezer")

        provider_cls = media_providers[default_provider]
        self.metadata = provider_cls(core=core, clients=clients)

