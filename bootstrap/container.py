from dataclasses import dataclass

from app import (
    Downloader,
    MediaResolver,
    YouTubeUserPlaylist,
    SpotifyPlaylistCompilation,
)
from clients import YtDlpClient, SpotifyClient, SecretsManager, YouTubeApiClient
from core import (
    WebScraper,
    LyricsFinder,
    HistoryManager,
    PatternMatcher,
    VideoConverter,
    YouTubeExtractor,
)
from orchestration import SearchOrchestrator, MetadataOrchestrator
from services import (
    SpotifySearchService,
    YoutubeSearchService,
    SpotifyMetadataService,
    YouTubeMetadataService,
)
from integrations import SpotifyUserPlaylistModify


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


@dataclass
class Orchestration:
    search: SearchOrchestrator
    metadata: MetadataOrchestrator


@dataclass
class Domain:
    spotify_search: SpotifySearchService
    spotify_metadata: SpotifyMetadataService
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
        self.core: Core
        self.clients: Clients
        self.orchestration: Orchestration
        self.domain: Domain
        self.app: App

    def setup_container(self):
        self.build_application()
        self.build_clients()
        self.build_core()
        self.build_domain()
        self.build_orchestrators()

    def build_clients(self):
        self.clients = Clients(
            spotify=SpotifyClient(),
            youtube=YouTubeApiClient(),
            ytdlp=YtDlpClient(),
            secrets=SecretsManager(),
        )

    def build_core(self):
        scraper = WebScraper()
        secrets_manager = SecretsManager()
        extractor = YouTubeExtractor()

        self.core = Core(
            history=HistoryManager(),
            lyrics=LyricsFinder(scraper=scraper, secrets_manager=secrets_manager),
            matcher=PatternMatcher(extractor=extractor),
            converter=VideoConverter(),
            scraper=WebScraper(),
            extractor=YouTubeExtractor(),
        )

    def build_domain(self):
        youtube_search = YoutubeSearchService(clients=self.clients)
        spotify_search = SpotifySearchService(
            spotify_metadata=self.orchestration.metadata.spotify_metadata
        )
        spotify_metadata = SpotifyMetadataService(core=self.core, clients=self.clients)
        youtube_metadata = YouTubeMetadataService(
            spotify_search=spotify_search, core=self.core, clients=self.clients
        )
        self.domain = Domain(
            youtube_search=youtube_search,
            spotify_search=spotify_search,
            spotify_metadata=spotify_metadata,
            youtube_metadata=youtube_metadata,
        )

    def build_application(self):
        downloader = Downloader(core=self.core, clients=self.clients)
        resolver = MediaResolver(
            core=self.core,
            orchestration=self.orchestration,
            domain=self.domain,
            clients=self.clients,
        )
        spotify_playlist_modify = SpotifyUserPlaylistModify(clients=self.clients)
        spotify_playlist_compiler = SpotifyPlaylistCompilation(
            core=self.core,
            orchestration=self.orchestration,
            domain=self.domain,
            clients=self.clients,
        )
        youtube_user_playlist = YouTubeUserPlaylist(
            clients=self.clients, core=self.core, domain=self.domain
        )

        self.app = App(
            downloader=downloader,
            resolver=resolver,
            spotify_playlist_modify=spotify_playlist_modify,
            spotify_playlist_compiler=spotify_playlist_compiler,
            youtube_user_playlist=youtube_user_playlist,
        )

    def build_orchestrators(self):
        search_orchestrator = SearchOrchestrator(
            youtube_search=self.domain.youtube_search,
            spotify_search=self.domain.spotify_search,
            metadata_orchestrator=self.orchestration.metadata,
            matcher=self.core.matcher,
        )
        metadata_orchestrator = MetadataOrchestrator(
            youtube_metadata=self.domain.youtube_metadata,
            spotify_metadata=self.domain.spotify_metadata,
        )

        self.orchestration = Orchestration(
            search=search_orchestrator, metadata=metadata_orchestrator
        )

