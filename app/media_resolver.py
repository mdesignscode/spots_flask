from __future__ import annotations

from logging import info
from tenacity import stop_after_delay
from typing import TYPE_CHECKING

from engine.persistence_model import storage
from engine.retry import retry
from models.errors import InvalidURL, SongNotFound
from models.media_resource import MediaResourceSingle, MediaResourcePlaylist
from models.playlist_info import PlaylistInfo
from models.sentinel import Sentinel
from models.yt_video_info import YTVideoInfo

if TYPE_CHECKING:
    from bootstrap.container import Core, Orchestration, Domain, Clients


class MediaResolver:
    def __init__(
        self, core: Core, orchestration: Orchestration, domain: Domain, clients: Clients
    ):
        self.core = core
        self.orchestration = orchestration
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
                metadata = self.orchestration.metadata.spotify_metadata.get(
                    track_id=track_id
                )

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
                playlist_info = self.domain.spotify_search.search_playlist(url)

                return MediaResourcePlaylist(
                    resource_type="playlist", playlist_info=playlist_info
                )

        # process youtube link
        elif "youtu" in url:
            info("URL type: YouTube")
            # playlist
            if "playlist" in url:
                info("Resource type: playlist")
                playlist_search = self.clients.ytdlp.ydl.extract_info(
                    url, download=False
                )

                if not playlist_search:
                    raise SongNotFound(url)

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
                    self.orchestration.search.filter_matching_domain_results(
                        youtube_results=videos_list
                    )
                )

                cover = "http://localhost:5000/static/youtube-playlist.jpg"
                playlist_name = playlist_search["title"]

                playlist_info = PlaylistInfo(
                    name=playlist_name,
                    cover=cover,
                    spotify_metadata=domain_matches.spotify,
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
                    cached_metadata = storage.get(query=url, query_type="spotify")
                    return MediaResourceSingle(
                        resource_type="single",
                        metadata=cached_metadata,
                        video_info=video_info.result,
                    )

                yt_title = video_info.result.full_title
                try:
                    metadata = self.domain.spotify_search.search_track(yt_title)
                except SongNotFound:
                    storage.new(query=yt_title, result=Sentinel(), query_type="spotify")
                    storage.new(query=yt_title, result=Sentinel(), query_type="ytdl")
                    raise

                tracks_match = self.core.matcher.match_tracks(
                    metadata=metadata, video_info=video_info.result
                )
                if not tracks_match:
                    storage.new(query=yt_title, result=Sentinel(), query_type="spotify")
                    storage.new(query=yt_title, result=Sentinel(), query_type="ytdl")
                    raise SongNotFound(yt_title)
                else:
                    storage.new(query=yt_title, result=metadata, query_type="spotify")
                    storage.new(
                        query=yt_title, result=video_info.result, query_type="ytdl"
                    )
                    return MediaResourceSingle(
                        resource_type="single",
                        metadata=metadata,
                        video_info=video_info.result,
                    )
        else:
            raise InvalidURL(url)

