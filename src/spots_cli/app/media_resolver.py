from __future__ import annotations

from logging import getLogger
from tenacity import stop_after_delay
from typing import TYPE_CHECKING, Any, cast

from spots_cli.app.domain_resolver import fallback_metadata
from spots_cli.engine import retry
from spots_cli.models import (
    InvalidURL,
    SongNotFound,
    SpotifyUnavailableError,
    MediaResourceSingle,
    MediaResourcePlaylist,
    PlaylistInfo,
    Sentinel,
    UnavailableVideo,
    YTVideoInfo,
)

if TYPE_CHECKING:
    from spots_cli.bootstrap.container import Core, Domain, Clients
    from spots_cli.app import DomainResolver


logger = getLogger(__name__)


class MediaResolver:
    def __init__(
        self,
        core: Core,
        domain: Domain,
        clients: Clients,
        domain_resolver: DomainResolver,
    ) -> None:
        self.domain_resolver = domain_resolver
        self.core = core
        self.domain = domain
        self.clients = clients

    @retry(stop=stop_after_delay(60))
    def resolve(self, *, url: str) -> MediaResourceSingle | MediaResourcePlaylist:
        """Converts a youtube or spotify url to mp3, or a youtube video to mp3

        Args:
            url (str): url to be converted
            single: (bool, optional): don't search for recommended tracks if false. Defaults to False

        Raises:
            InvalidURL: if provided url not available
        """
        # process spotify link
        if "spotify" in url:
            # a Spotify id means nothing to the other providers
            if not self.clients.spotify:
                raise SpotifyUnavailableError(
                    "Spotify links need Spotify turned on. Run `spots_cli setup` "
                    "and enable Spotify, or paste the YouTube link instead."
                )

            # single
            if "track" in url:
                # retrieve Provider data
                logger.debug("Resource type: single")

                track_id = url.split("/")[-1]
                metadata = self.domain.provider_metadata.get(track_id=track_id)

                # search on YouTube
                youtube_results = self.domain.youtube_search.video_search(
                    query=metadata.full_title, is_general_search=True
                )
                best_match = self.core.matcher.find_best_match(
                    search_results=youtube_results.result, metadata=metadata
                )

                return MediaResourceSingle(
                    resource_type="single",
                    metadata=metadata,
                    video_info=best_match,
                )
            # playlist
            else:
                logger.debug("Resource type: playlist")
                playlist_info = self.domain.provider_search.search_playlist(
                    url)

                return MediaResourcePlaylist(
                    resource_type="playlist", playlist_info=playlist_info
                )

        # process youtube link
        elif "youtu" in url:
            logger.debug("URL type: YouTube")
            # playlist
            if "playlist" in url:
                logger.debug("Resource type: playlist")

                self.clients.ytdlp.options = {
                    "ignoreerrors": True, "quiet": True}
                try:
                    playlist_search = self.clients.ytdlp.client.extract_info(
                        url, download=False
                    )
                except Exception as e:
                    logger.error(f"Failed to extract playlist {url}: {e}")
                    raise SongNotFound(url)
                finally:
                    self.clients.ytdlp.reset_options()

                if not playlist_search:
                    raise SongNotFound(url)

                playlist_search = cast(dict[str, Any], playlist_search)

                videos_list: list[YTVideoInfo] = []
                unavailable_videos: list[UnavailableVideo] = []
                for position, result in enumerate(playlist_search["entries"]):
                    # `ignoreerrors` leaves a `None` placeholder for videos
                    # that failed to extract (private, deleted, region-locked)
                    if result is None:
                        logger.warning(
                            f"Skipping unavailable playlist entry at position {
                                position}"
                        )
                        unavailable_videos.append(
                            UnavailableVideo(
                                reason="unavailable (private, deleted, or region-locked)",
                            )
                        )
                        continue

                    try:
                        videos_list.append(
                            YTVideoInfo(
                                id=result["id"],
                                filesize=self.domain.youtube_search.get_video_size(
                                    result
                                ),
                                title=result["title"],
                                uploader=result["uploader"],
                                audio_ext=result.get("audio_ext", "webm"),
                            )
                        )
                    except KeyError as e:
                        logger.warning(
                            f"Skipping playlist entry missing field {
                                e}: {result.get('id')}"
                        )
                        unavailable_videos.append(
                            UnavailableVideo(
                                id=result.get("id"),
                                title=result.get("title"),
                                reason=f"missing field: {e}",
                            )
                        )
                        continue

                domain_matches = self.domain_resolver.filter_matching_domain_results(
                    youtube_results=videos_list
                )

                cover = self.clients.secrets.read(
                    key="static_playlist_cover_name", alt="youtube-playlist.jpg"
                )
                playlist_name = playlist_search["title"]

                playlist_info = PlaylistInfo(
                    name=playlist_name,
                    cover=cover,
                    provider_metadata=domain_matches.provider,
                    youtube_metadata=domain_matches.youtube,
                    unavailable=unavailable_videos,
                )

                return MediaResourcePlaylist(
                    resource_type="playlist", playlist_info=playlist_info
                )
            else:
                logger.debug("Resource type: single")

                video_info = self.domain.youtube_search.video_search(
                    query=url, is_general_search=False
                )
                if video_info.is_cached:
                    cached_metadata = self.core.storage.get(
                        query=url, query_type="metadata"
                    )
                    return MediaResourceSingle(
                        resource_type="single",
                        metadata=cached_metadata,
                        video_info=video_info.result,
                    )

                yt_title = self.core.extractor.build_search_query(
                    video_info.result.uploader, video_info.result.title
                )
                # the user picked this video, so it is downloaded either way;
                # the provider only adds tags (cover, album, lyrics)
                try:
                    metadata = self.domain.provider_search.search_track(
                        yt_title)
                except SongNotFound:
                    metadata = None

                if metadata is None or not self.core.matcher.match_tracks(
                    metadata=metadata, video_info=video_info.result
                ):
                    logger.debug(
                        f"No matching provider metadata for '{yt_title}', "
                        "falling back to YouTube-derived metadata"
                    )
                    metadata = fallback_metadata(
                        video_info.result, self.core.extractor
                    )

                self.core.storage.new(
                    query=yt_title, result=metadata, query_type="metadata"
                )
                self.core.storage.new(
                    query=yt_title, result=video_info.result, query_type="youtube"
                )
                return MediaResourceSingle(
                    resource_type="single",
                    metadata=metadata,
                    video_info=video_info.result,
                )
        else:
            raise InvalidURL(url)
