from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from engine.persistence_model import storage
from models.errors import SongNotFound
from models.metadata import Metadata
from models.yt_video_info import YTVideoInfo
from models.sentinel import Sentinel
from models.errors import SongNotFound
from models.metadata import Metadata
from models.sentinel import Sentinel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.pattern_matcher import PatternMatcher
    from orchestration.metadata_orchestrator import MetadataOrchestrator
    from services.spotify_search_service import SpotifySearchService
    from services.youtube_search_service import YoutubeSearchService


@dataclass
class MatchingDomainResults:
    spotify: list[Metadata]
    youtube: list[YTVideoInfo]

@dataclass
class ResolvedDomainResult:
    spotify: Metadata
    youtube: YTVideoInfo


class SearchOrchestrator():
    """Aggregates YouTube and Spotify search services"""

    def __init__(
        self,
        youtube_search: YoutubeSearchService,
        spotify_search: SpotifySearchService,
        metadata_orchestrator: MetadataOrchestrator,
        matcher: PatternMatcher
    ):
        self.matcher = matcher
        self.spotify_search = spotify_search
        self.youtube_search = youtube_search
        self.metadata_orchestrator = metadata_orchestrator

    def resolve_spotify_track(self, track_id):
        metadata = self.metadata_orchestrator.spotify_metadata.get(track_id=track_id)

        youtube_results = self.youtube_search.video_search(
            query=metadata.full_title,
            is_general_search=True,
        )

        best_match = self.matcher.find_best_match(
            search_results=youtube_results.result,
            metadata=metadata,
        )

        return metadata, best_match

    @overload
    def filter_matching_domain_results(
        self, *, spotify_results: list[Metadata], youtube_results: None = None
    ) -> MatchingDomainResults: ...

    @overload
    def filter_matching_domain_results(
        self, *, spotify_results: None = None, youtube_results: list[YTVideoInfo]
    ) -> MatchingDomainResults: ...

    def filter_matching_domain_results(
        self,
        *,
        spotify_results: list[Metadata] | None = None,
        youtube_results: list[YTVideoInfo] | None = None,
    ) -> MatchingDomainResults:
        spotify_playlist: list[Metadata] = []
        youtube_videos: list[YTVideoInfo] = []

        if youtube_results is not None:
            for index, video in enumerate(youtube_results):
                video_title = video.full_title

                try:
                    spotify_search_result = self.spotify_search.search_track(
                        video_title
                    )
                except SongNotFound:
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="spotify"
                    )
                    storage.new(query=video_title, result=Sentinel(), query_type="ytdl")
                    continue

                tracks_match = self.matcher.match_tracks(
                    video_info=video, metadata=spotify_search_result
                )
                if not tracks_match:
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="spotify"
                    )
                    storage.new(query=video_title, result=Sentinel(), query_type="ytdl")
                    continue
                else:
                    storage.new(
                        query=video_title,
                        result=spotify_search_result,
                        query_type="spotify",
                    )
                    storage.new(query=video_title, result=video, query_type="ytdl")
                    spotify_playlist.append(spotify_search_result)
                    youtube_videos.append(video)

                if (index % 10 == 0) or index == (len(youtube_results) - 1):
                    storage.save()

        if spotify_results is not None:
            for track in spotify_results:
                spotify_title = track.full_title

                try:
                    youtube_search_results = self.youtube_search.video_search(
                        query=spotify_title, is_general_search=True
                    )
                except SongNotFound:
                    storage.new(
                        query=spotify_title, result=Sentinel(), query_type="spotify"
                    )
                    storage.new(
                        query=spotify_title, result=Sentinel(), query_type="ytdl"
                    )
                    continue

                if youtube_search_results.is_cached:
                    cache = youtube_search_results.result[0]
                    if isinstance(cache, Sentinel):
                        continue
                    else:
                        spotify_playlist.append(track)
                        youtube_videos.append(cache)

                else:
                    try:
                        best_match = self.matcher.find_best_match(
                            search_results=youtube_search_results.result, metadata=track
                        )
                    except SongNotFound:
                        storage.new(
                            query=spotify_title, result=Sentinel(), query_type="spotify"
                        )
                        storage.new(
                            query=spotify_title, result=Sentinel(), query_type="ytdl"
                        )
                        continue

                    spotify_playlist.append(track)
                    youtube_videos.append(best_match)

        return MatchingDomainResults(spotify=spotify_playlist, youtube=youtube_videos)

