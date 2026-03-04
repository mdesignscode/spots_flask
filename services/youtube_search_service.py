from __future__ import annotations

from logging import error
from math import ceil
from tenacity import stop_after_delay
from typing import Any, Literal, overload, TYPE_CHECKING

from clients.ytdl import YtDlpClient
from engine.persistence_model import storage
from engine.retry import retry
from models.errors import SongNotFound
from models.helper_models import SearchResponseMultiple, SearchResponseSingle
from models.playlist_info import PlaylistInfo
from models.sentinel import Sentinel
from models.yt_video_info import YTVideoInfo

if TYPE_CHECKING:
    from bootstrap.container import Clients


class YoutubeSearchService:
    """Responsible for searching for query on YouTube"""

    def __init__(
            self,*, clients: Clients
    ):
        self.clients = clients

    def get_video_size(self, data: dict[str, Any]) -> int:
        size = data.get("filesize") or data.get("filesize_approx")
        return ceil(size / (1024 * 1024)) if size else 0

    def youtube_playlist_search(self, link: str) -> PlaylistInfo:
        playlist_opts = {
            "quiet": True,
            "extract_flat": True,
            "playlistend": None,  # Extract full playlist,
        }
        playlist_processor = YtDlpClient(extra_options=playlist_opts)

        try:
            playlist_search = playlist_processor.ydl.extract_info(link, download=False)
        except Exception as e:
            error(str(e))
            raise

        if not playlist_search:
            raise SongNotFound(link)

        playlist_name = playlist_search["title"]
        playlist_cover = "youtube-playlist(mdesigns).jpg"

        videos_list = [
            YTVideoInfo(
                title=result["title"],
                uploader=result["uploader"],
                filesize=self.get_video_size(result),
                audio_ext=result["audio_ext"],
                id=result["id"],
            )
            for result in playlist_search["entries"]
        ]

        return PlaylistInfo(
            name=playlist_name,
            cover=playlist_cover,
            youtube_metadata=videos_list,
            spotify_metadata=[],
        )

    @overload
    def video_search(
        self, *, query: str, is_general_search: Literal[False]
    ) -> SearchResponseSingle: ...

    @overload
    def video_search(
        self, *, query: str, is_general_search: Literal[True] = True
    ) -> SearchResponseMultiple: ...

    @retry(stop=stop_after_delay(60))
    def video_search(
        self, *, query, is_general_search=True
    ) -> SearchResponseSingle | SearchResponseMultiple:
        cache = storage.get(query=query, query_type="ytdl")
        if isinstance(cache, Sentinel):
            raise SongNotFound(query)
        elif isinstance(cache, YTVideoInfo):
            return (
                SearchResponseSingle(result=cache, is_cached=True)
                if not is_general_search
                else SearchResponseMultiple(result=[cache], is_cached=True)
            )
        else:
            search_term = f"ytsearch5:{query}" if is_general_search else query
            search_result = self.clients.ytdlp.ydl.extract_info(
                search_term, download=False
            )

            if not search_result:
                storage.new(query=query, result=Sentinel(), query_type="ytdl")
                raise SongNotFound(query)

            if is_general_search and not search_result.get("entries"):
                storage.new(query=query, result=Sentinel(), query_type="ytdl")
                raise SongNotFound(query)

            if not is_general_search:

                return SearchResponseSingle(
                    result=YTVideoInfo(
                        title=search_result["title"],
                        uploader=search_result["uploader"],
                        id=search_result["id"],
                        filesize=self.get_video_size(search_result),
                        audio_ext=search_result.get("audio_ext", "webm"),
                    ),
                    is_cached=False,
                )
            else:
                result_objects: list[YTVideoInfo] = []
                for result in search_result["entries"]:
                    result_objects.append(
                        YTVideoInfo(
                            title=result["title"],
                            uploader=result["uploader"],
                            id=result["id"],
                            filesize=self.get_video_size(result),
                            audio_ext=result.get("audio_ext", "webm"),
                        )
                    )

                return SearchResponseMultiple(result=result_objects, is_cached=False)

