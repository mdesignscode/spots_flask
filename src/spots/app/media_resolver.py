from __future__ import annotations

from logging import info
from tenacity import stop_after_delay
from typing import TYPE_CHECKING, Any, cast

from app import DomainResolver
from engine.persistence_model import storage
from engine.retry import retry
from models import (
    InvalidURL,
    SongNotFound,
    MediaResourceSingle,
    MediaResourcePlaylist,
    PlaylistInfo,
    Sentinel,
    YTVideoInfo,
)

if TYPE_CHECKING:
    from bootstrap.container import Core, Domain, Clients


class MediaResolver:
    def __init__(self, core: Core, domain: Domain, clients: Clients, domain_resolver: DomainResolver) -> None:
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
            # single
            if "track" in url:
                # retrieve Spotify data
                info("Resource type: single")

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
                info("Resource type: playlist")
                playlist_info = self.domain.provider_search.search_playlist(url)

                return MediaResourcePlaylist(
                    resource_type="playlist", playlist_info=playlist_info
                )

        # process youtube link
        elif "youtu" in url:
            info("URL type: YouTube")
            # playlist
            if "playlist" in url:
                info("Resource type: playlist")
                playlist_search = self.clients.ytdlp.client.extract_info(
                    url, download=False
                )

                if not playlist_search:
                    raise SongNotFound(url)

                playlist_search = cast(dict[str, Any], playlist_search)

                videos_list = [
                    YTVideoInfo(
                        id=result["id"],
                        filesize=self.domain.youtube_search.get_video_size(result),
                        title=result["title"],
                        uploader=result["uploader"],
                        audio_ext=result["audio_ext"],
                    )
                    for result in playlist_search["entries"]
                ]

                domain_matches = (
                    self.domain_resolver.filter_matching_domain_results(
                        youtube_results=videos_list
                    )
                )

                cover = "http://localhost:5000/static/youtube-playlist.jpg"
                playlist_name = playlist_search["title"]

                playlist_info = PlaylistInfo(
                    name=playlist_name,
                    cover=cover,
                    provider_metadata=domain_matches.provider,
                    youtube_metadata=domain_matches.youtube,
                )

                return MediaResourcePlaylist(
                    resource_type="playlist", playlist_info=playlist_info
                )
            else:
                info("Resource type: single")

                video_info = self.domain.youtube_search.video_search(
                    query=url, is_general_search=False
                )
                if video_info.is_cached:
                    cached_metadata = storage.get(query=url, query_type="metadata")
                    return MediaResourceSingle(
                        resource_type="single",
                        metadata=cached_metadata,
                        video_info=video_info.result,
                    )

                yt_title = video_info.result.full_title
                try:
                    metadata = self.domain.provider_search.search_track(yt_title)
                except SongNotFound:
                    storage.new(
                        query=yt_title, result=Sentinel(), query_type="metadata"
                    )
                    storage.new(query=yt_title, result=Sentinel(), query_type="youtube")
                    raise

                tracks_match = self.core.matcher.match_tracks(
                    metadata=metadata, video_info=video_info.result
                )
                if not tracks_match:
                    storage.new(
                        query=yt_title, result=Sentinel(), query_type="metadata"
                    )
                    storage.new(query=yt_title, result=Sentinel(), query_type="youtube")
                    raise SongNotFound(yt_title)
                else:
                    storage.new(query=yt_title, result=metadata, query_type="metadata")
                    storage.new(
                        query=yt_title, result=video_info.result, query_type="youtube"
                    )
                    return MediaResourceSingle(
                        resource_type="single",
                        metadata=metadata,
                        video_info=video_info.result,
                    )
        else:
            raise InvalidURL(url)

