from __future__ import annotations

from spots_cli.models import MetadataProvider
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots_cli.bootstrap.container import Clients, Core


class ProvidersMetadata:
    def __init__(self, *, clients: Clients, core: Core):
        from spots_cli.services import DeezerMetadataService, SpotifyMetadataService

        media_providers: dict[str, type[MetadataProvider]] = {
            "deezer": DeezerMetadataService,
            "spotify": SpotifyMetadataService,
        }

        default_provider = clients.secrets.read(key="main_provider", alt="deezer")

        provider_cls = media_providers[default_provider]
        self.metadata = provider_cls(core=core, clients=clients)
