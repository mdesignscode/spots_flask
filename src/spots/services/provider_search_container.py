from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spots.bootstrap.container import Clients, Core
    from spots.models import SearchProvider, MetadataProvider

class ProviderSearchContainer:
    def __init__(self, clients: Clients, metadata: MetadataProvider, core: Core):
        from spots.services import DeezerSearchService, SpotifySearchService

        # Define all possible providers with availability checks
        provider_registry: dict[str, tuple[type[SearchProvider], bool]] = {
            "deezer": (DeezerSearchService, True),  # always available
            "spotify": (
                SpotifySearchService,
                bool(clients.spotify),  # availability check
            ),
        }

        # Filter only available providers
        available_providers = {
            name: cls
            for name, (cls, is_available) in provider_registry.items()
            if is_available
        }

        if not available_providers:
            raise RuntimeError("No search providers available")

        # Resolve default provider safely
        default_provider = clients.secrets.read(key="main_provider", alt="deezer")

        if default_provider not in available_providers:
            # fallback to first available provider
            default_provider = next(iter(available_providers))

        provider_cls = available_providers[default_provider]

        # Remove main from fallback pool
        fallback_classes = {
            name: cls
            for name, cls in available_providers.items()
            if name != default_provider
        }

        # Instantiate fallback providers
        fallback_providers = [
            cls(metadata=metadata, clients=clients, core=core)
            for cls in fallback_classes.values()
        ]

        # Wire fallbacks (optional, depending on your design)
        for provider in fallback_providers:
            provider.fallback_providers = fallback_providers

        # Instantiate main provider
        self.main = provider_cls(
            metadata=metadata,
            clients=clients,
            core=core,
            fallback_providers=fallback_providers,
        )

        self.fallbacks = fallback_providers
