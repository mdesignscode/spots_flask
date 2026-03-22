from dataclasses import dataclass

from app import (
    Downloader,
    MediaResolver,
    YouTubeUserPlaylist,
    SpotifyPlaylistCompilation,
)
from clients import (
    YtDlpClient,
    SpotifyClient,
    SecretsManager,
    YouTubeApiClient,
    DeezerClient,
)
from core import (
    WebScraper,
    LyricsFinder,
    HistoryManager,
    PatternMatcher,
    VideoConverter,
    YouTubeExtractor,
)
from models import MetadataProvider, SearchProvider
from services import (
    YoutubeSearchService,
    YouTubeMetadataService,
    ProvidersSearch,
    ProvidersMetadata,
)
from integrations import SpotifyUserPlaylistModify
from services.spotify_metadata_service import SpotifyMetadataService
from services.spotify_search_service import SpotifySearchService


@dataclass
class Core:
    history: HistoryManager
    lyrics: LyricsFinder
    matcher: PatternMatcher
    converter: VideoConverter
    scraper: WebScraper
    extractor: YouTubeExtractor


@dataclass
class Clients:
    spotify: SpotifyClient
    youtube: YouTubeApiClient
    ytdlp: YtDlpClient
    secrets: SecretsManager
    deezer: DeezerClient


@dataclass
class Domain:
    provider_search: ProvidersSearch
    provider_metadata: MetadataProvider
    youtube_search: YoutubeSearchService
    youtube_metadata: YouTubeMetadataService


@dataclass
class App:
    downloader: Downloader
    resolver: MediaResolver
    spotify_playlist_compiler: SpotifyPlaylistCompilation
    youtube_user_playlist: YouTubeUserPlaylist
    spotify_playlist_modify: SpotifyUserPlaylistModify


class Container:
    def __init__(self):
        self.core =self._build_core()
        self.clients = self._build_clients()
        self.domain = self._build_domain()
        self.app = self._build_application()

    def _build_clients(self) -> Clients:
        return Clients(
            spotify=SpotifyClient(),
            youtube=YouTubeApiClient(),
            ytdlp=YtDlpClient(),
            secrets=SecretsManager(),
            deezer=DeezerClient(),
        )

    def _build_core(self) -> Core:
        scraper = WebScraper()
        secrets_manager = SecretsManager()
        extractor = YouTubeExtractor()

        return Core(
            history=HistoryManager(),
            lyrics=LyricsFinder(scraper=scraper, secrets_manager=secrets_manager),
            matcher=PatternMatcher(extractor=extractor),
            converter=VideoConverter(),
            scraper=WebScraper(),
            extractor=YouTubeExtractor(),
        )

    def _build_domain(self) -> Domain:
        youtube_search = YoutubeSearchService(clients=self.clients)

        provider_metadata = ProvidersMetadata(
            clients=self.clients,
            core=self.core,
        )
        provider_search = ProvidersSearch(
            core=self.core,
            clients=self.clients,
            youtube_search=youtube_search,
            metadata=provider_metadata.metadata,
        )

        youtube_metadata = YouTubeMetadataService(
            search=provider_search.main, clients=self.clients, core=self.core
        )

        return Domain(
            youtube_search=youtube_search,
            provider_search=provider_search,
            provider_metadata=provider_metadata.metadata,
            youtube_metadata=youtube_metadata,
        )

    def _build_application(self) -> App:
        downloader = Downloader(core=self.core, clients=self.clients)
        resolver = MediaResolver(
            core=self.core,
            domain=self.domain,
            clients=self.clients,
        )
        spotify_playlist_modify = SpotifyUserPlaylistModify(clients=self.clients)

        youtube_search = YoutubeSearchService(clients=self.clients)
        spotify_metadata = SpotifyMetadataService(clients=self.clients, core=self.core)
        providers_search = ProvidersSearch(
            youtube_search=youtube_search,
            clients=self.clients,
            core=self.core,
            metadata=spotify_metadata,
        )
        spotify_playlist_compiler = SpotifyPlaylistCompilation(
            core=self.core,
            domain=self.domain,
            clients=self.clients,
            metadata=spotify_metadata,
            providers_search=providers_search,
        )
        youtube_user_playlist = YouTubeUserPlaylist(
            search=youtube_search,
            clients=self.clients,
            core=self.core,
            spotify_playlist_compiler=spotify_playlist_compiler,
        )

        return App(
            downloader=downloader,
            resolver=resolver,
            spotify_playlist_modify=spotify_playlist_modify,
            spotify_playlist_compiler=spotify_playlist_compiler,
            youtube_user_playlist=youtube_user_playlist,
        )

