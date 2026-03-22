from __future__ import annotations

from logging import error, info
from math import ceil
from tenacity import stop_after_delay
from typing import Any, Literal, cast, overload, TYPE_CHECKING
from yt_dlp import _Params

from engine.persistence_model import storage
from engine.retry import retry
from models import (
    SongNotFound,
    SearchResponseSingle,
    SearchResponseMultiple,
    PlaylistInfo,
    Sentinel,
    YTVideoInfo,
)

if TYPE_CHECKING:
    from bootstrap.container import Clients


class YoutubeSearchService:
    """Responsible for searching for query on YouTube"""

    def __init__(self, *, clients: Clients):
        self.clients = clients

    def get_video_size(self, data: dict[str, Any]) -> int:
        size = data.get("filesize") or data.get("filesize_approx")
        return ceil(size / (1024 * 1024)) if size else 0

    def youtube_playlist_search(self, link: str) -> PlaylistInfo:
        playlist_opts: _Params = {
            "quiet": True,
            "extract_flat": True,
            "playlistend": None,  # Extract full playlist,
        }
        self.clients.ytdlp.options = playlist_opts

        try:
            playlist_search = self.clients.ytdlp.client.extract_info(
                link, download=False
            )
        except Exception as e:
            error(str(e))
            raise

        if not playlist_search:
            raise SongNotFound(link)

        playlist_search = cast(dict[str, Any], playlist_search)
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

        self.clients.ytdlp.reset_options()

        return PlaylistInfo(
            name=playlist_name,
            cover=playlist_cover,
            youtube_metadata=videos_list,
            provider_metadata=[],
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
        cache = storage.get(query=query, query_type="youtube")
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
            search_result = self.clients.ytdlp.client.extract_info(
                search_term, download=False
            )

            if not search_result:
                storage.new(query=query, result=Sentinel(), query_type="youtube")
                raise SongNotFound(query)

            if is_general_search and not search_result.get("entries"):
                storage.new(query=query, result=Sentinel(), query_type="youtube")
                raise SongNotFound(query)

            search_result = cast(dict[str, Any], search_result)

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

    def artist_search(self, artist: str):
        """
        Search for for all videos by an artist name on youtube

        Args:
            artist (str): The name of the artist
            default_cover (str): Fallback cover url

        Returns:
            List[Metadata]: A list of songs by `artist` found on YT
        """
        info(f"[Search Artist on YouTube] Searching for {artist}'s songs on YT")

        ydl_opts: _Params = {
            "quiet": True,
            "extract_flat": True,
        }

        self.clients.ytdlp.options = ydl_opts
        search_results = self.clients.ytdlp.client.extract_info(artist, download=False)

        if not search_results:
            raise SongNotFound(artist)

        video_record: dict[str, YTVideoInfo] = {}

        search_results = cast(dict[str, Any], search_results)

        playlist_len = len(search_results["entries"])
        for index, entry in enumerate(search_results["entries"]):
            info(
                f"[Search Artist on YouTube] Searching for track {index + 1}/{playlist_len} on YouTube..."
            )
            title = entry.get("title")

            if not video_record.get(title):
                try:
                    id = entry.get("id")
                    watch_url = f"https://www.youtube.com/watch?v={id}"
                    metadata = self.video_search(
                        query=watch_url, is_general_search=False
                    )
                    video_record[title] = metadata.result

                    if (index % 10 == 0) or (index == (playlist_len - 1)):
                        storage.save()

                except SongNotFound:
                    continue
            else:
                continue

            self.clients.ytdlp.reset_options()

            artist_playlist = list(video_record.values())
            storage.new(query=artist, result=artist_playlist, query_type="artist")

            storage.save()

            return artist_playlist

