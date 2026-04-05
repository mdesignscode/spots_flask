from dataclasses import dataclass
from logging import DEBUG, ERROR, basicConfig, INFO, getLogger
from os.path import exists

from spots_cli.app import (
    Downloader,
    MediaResolver,
    YouTubeUserPlaylist,
    SpotifyPlaylistCompilation,
    DomainResolver,
)
from spots_cli.clients import (
    YtDlpClient,
    SpotifyClient,
    SecretsManager,
    YouTubeApiClient,
    DeezerClient,
)
from spots_cli.core import (
    WebScraper,
    LyricsFinder,
    HistoryManager,
    PatternMatcher,
    VideoConverter,
    YouTubeExtractor,
)
from spots_cli.engine import FileStorage
from spots_cli.models import MetadataProvider, SearchProvider
from spots_cli.services import (
    YoutubeSearchService,
    YouTubeMetadataService,
    ProvidersMetadata,
    ProviderSearchContainer,
    SpotifySearchService,
    SpotifyMetadataService,
)
from spots_cli.integrations import SpotifyUserPlaylistModify
from spots_cli.utils import get_config_path

logger = getLogger(__name__)


@dataclass
class Core:
    history: HistoryManager
    lyrics: LyricsFinder
    matcher: PatternMatcher
    converter: VideoConverter
    scraper: WebScraper
    extractor: YouTubeExtractor
    storage: FileStorage


@dataclass
class Clients:
    spotify: SpotifyClient | None
    youtube: YouTubeApiClient | None
    ytdlp: YtDlpClient
    secrets: SecretsManager
    deezer: DeezerClient


@dataclass
class Domain:
    provider_search: SearchProvider
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
    domain_resolver: DomainResolver


class Container:
    def __init__(self):
        self.__path = get_config_path() / ".bootstrapped"

        secrets = SecretsManager()
        environment_mode = secrets.read(key="environment_mode", alt="PRODUCTION")
        basicConfig(level=INFO if environment_mode.lower() == "production" else DEBUG)
        getLogger("googleapiclient.discovery_cache").setLevel(ERROR)

        logger.debug("Bootstrapping app...")

        self.initial_setup()

        logger.debug("Setting up core components...")
        self.core = self._build_core()
        self.clients = self._build_clients()
        self.domain = self._build_domain()
        self.app = self._build_application()
        logger.debug("Components setup complete.")

        # cache
        logger.debug("Loading cache into memory...")
        self.core.storage.cache_file_exists()
        self.core.storage.reload()
        logger.debug("Cache loaded.")

        logger.debug("Bootstrap complete. App ready for use.")

    def initial_setup(self) -> None:
        if not exists(self.__path):
            logger.debug("Running initial setup...")
            logger.debug("Creating internal files used for tracking downloads...")

            # downloads history
            logger.debug("Creating downloads history file...")
            history = HistoryManager()
            history.history_file_exists()
            logger.debug("History file created.")

            with open(self.__path, "w"):
                pass

            logger.debug("Download manager files setup complete.")

    def _build_clients(self) -> Clients:
        secrets = SecretsManager()

        youtube = None
        if secrets.read(key="youtube_account_access", alt="false").lower() == "true":
            youtube = YouTubeApiClient()

        spotify = None
        if (
            secrets.read(key="spotify_features_available", alt="false").lower()
            == "true"
        ):
            spotify = SpotifyClient()

        return Clients(
            spotify=spotify,
            youtube=youtube,
            ytdlp=YtDlpClient(secrets=secrets),
            secrets=secrets,
            deezer=DeezerClient(),
        )

    def _build_core(self) -> Core:
        scraper = WebScraper()
        secrets_manager = SecretsManager()
        extractor = YouTubeExtractor()

        return Core(
            storage=FileStorage(),
            history=HistoryManager(),
            lyrics=LyricsFinder(scraper=scraper, secrets_manager=secrets_manager),
            matcher=PatternMatcher(extractor=extractor),
            converter=VideoConverter(),
            scraper=WebScraper(),
            extractor=YouTubeExtractor(),
        )

    def _build_domain(self) -> Domain:
        youtube_search = YoutubeSearchService(clients=self.clients, core=self.core)

        provider_metadata = ProvidersMetadata(
            clients=self.clients,
            core=self.core,
        )

        provider_search = ProviderSearchContainer(
            clients=self.clients, metadata=provider_metadata.metadata, core=self.core
        )

        youtube_metadata = YouTubeMetadataService(
            search=provider_search.main, clients=self.clients, core=self.core
        )

        return Domain(
            youtube_search=youtube_search,
            provider_search=provider_search.main,
            provider_metadata=provider_metadata.metadata,
            youtube_metadata=youtube_metadata,
        )

    def _build_application(self) -> App:
        downloader = Downloader(core=self.core, clients=self.clients)

        youtube_search = YoutubeSearchService(clients=self.clients, core=self.core)
        domain_resolver = DomainResolver(
            core=self.core,
            youtube_search=youtube_search,
            provider_search=self.domain.provider_search,
        )

        resolver = MediaResolver(
            core=self.core,
            domain=self.domain,
            clients=self.clients,
            domain_resolver=domain_resolver,
        )
        spotify_playlist_modify = SpotifyUserPlaylistModify(clients=self.clients)

        spotify_metadata = SpotifyMetadataService(clients=self.clients, core=self.core)

        spotify_search = SpotifySearchService(
            metadata=spotify_metadata, clients=self.clients, core=self.core
        )
        spotify_playlist_compiler = SpotifyPlaylistCompilation(
            core=self.core,
            domain=self.domain,
            clients=self.clients,
            metadata=spotify_metadata,
            spotify_search=spotify_search,
            domain_resolver=domain_resolver,
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
            domain_resolver=domain_resolver,
        )
