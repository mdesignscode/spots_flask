from __future__ import annotations

from services.deezer_search_service import DeezerSearchService
from services.spotify_search_service import SpotifySearchService
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from bootstrap.container import Clients
    from models import SearchProvider, MetadataProvider


class ProviderSearchContainer:
    def __init__(self, clients: Clients, metadata: MetadataProvider):
        self.clients = clients

        # map all providers
        media_providers: dict[str, type[SearchProvider]] = {
            "deezer": DeezerSearchService,
            "spotify": SpotifySearchService,
        }

        # get default provider
        default_provider = clients.secrets.read(key="main_provider", alt="deezer")
        provider_cls: type[SearchProvider] = media_providers[default_provider]
        del media_providers[default_provider]

        # initiate fallback providers
        fallback_providers = [
            provider(metadata=metadata, clients=self.clients)
            for provider in media_providers.values()
        ]

        # wire fallback providers
        for provider in fallback_providers:
            provider.fallback_providers = fallback_providers

        self.main = provider_cls(
            metadata=metadata, clients=self.clients, fallback_providers=fallback_providers
        )

        self.falbacks = fallback_providers

