from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence, overload

from spots.engine import storage
from spots.models import Metadata, SongNotFound, Sentinel, YTVideoInfo

if TYPE_CHECKING:
    from spots.bootstrap.container import Core
    from spots.models import SearchProvider
    from spots.services import YoutubeSearchService


@dataclass
class MatchingDomainResults:
    provider: list[Metadata]
    youtube: list[YTVideoInfo]


@dataclass
class ResolvedDomainResult:
    provider: Metadata
    youtube: YTVideoInfo


class DomainResolver:
    def __init__(
        self,
        core: Core,
        provider_search: SearchProvider,
        youtube_search: YoutubeSearchService,
    ) -> None:
        self.core = core
        self.provider_search = provider_search
        self.youtube_search = youtube_search

    @overload
    def filter_matching_domain_results(
        self,
        *,
        provider_results: Sequence[Metadata | Sentinel],
        youtube_results: None = None,
    ) -> MatchingDomainResults: ...

    @overload
    def filter_matching_domain_results(
        self,
        *,
        provider_results: None = None,
        youtube_results: Sequence[YTVideoInfo | Sentinel],
    ) -> MatchingDomainResults: ...

    def filter_matching_domain_results(
        self,
        *,
        provider_results: Sequence[Metadata | Sentinel] | None = None,
        youtube_results: Sequence[YTVideoInfo | Sentinel] | None = None,
    ) -> MatchingDomainResults:
        provider_playlist: list[Metadata] = []
        youtube_videos: list[YTVideoInfo] = []

        if youtube_results is not None:
            for index, video in enumerate(youtube_results):
                if isinstance(video, Sentinel):
                    continue

                video_title = video.full_title

                try:
                    spotify_search_result = self.provider_search.search_track(
                        video_title
                    )
                except SongNotFound:
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="metadata"
                    )
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="youtube"
                    )
                    continue

                tracks_match = self.core.matcher.match_tracks(
                    video_info=video, metadata=spotify_search_result
                )
                if not tracks_match:
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="metadata"
                    )
                    storage.new(
                        query=video_title, result=Sentinel(), query_type="youtube"
                    )
                    continue
                else:
                    storage.new(
                        query=video_title,
                        result=spotify_search_result,
                        query_type="metadata",
                    )
                    storage.new(query=video_title, result=video, query_type="youtube")
                    provider_playlist.append(spotify_search_result)
                    youtube_videos.append(video)

                if (index % 10 == 0) or index == (len(youtube_results) - 1):
                    storage.save()

        if provider_results is not None:
            for track in provider_results:
                if isinstance(track, Sentinel):
                    continue

                provider_title = track.full_title

                try:
                    youtube_search_results = self.youtube_search.video_search(
                        query=provider_title, is_general_search=True
                    )
                except SongNotFound:
                    storage.new(
                        query=provider_title, result=Sentinel(), query_type="metadata"
                    )
                    storage.new(
                        query=provider_title, result=Sentinel(), query_type="youtube"
                    )
                    continue

                if youtube_search_results.is_cached:
                    cache = youtube_search_results.result[0]
                    if isinstance(cache, Sentinel):
                        continue
                    else:
                        provider_playlist.append(track)
                        youtube_videos.append(cache)

                else:
                    try:
                        best_match = self.core.matcher.find_best_match(
                            search_results=youtube_search_results.result, metadata=track
                        )
                    except SongNotFound:
                        storage.new(
                            query=provider_title,
                            result=Sentinel(),
                            query_type="metadata",
                        )
                        storage.new(
                            query=provider_title,
                            result=Sentinel(),
                            query_type="youtube",
                        )
                        continue

                    provider_playlist.append(track)
                    youtube_videos.append(best_match)

        return MatchingDomainResults(provider=provider_playlist, youtube=youtube_videos)

