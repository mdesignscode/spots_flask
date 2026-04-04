from __future__ import annotations

from logging import getLogger
from typing import Any, cast, overload, TYPE_CHECKING

from spots.models import SongNotFound, Metadata, Sentinel, MetadataProvider
from spots.utils import fetch_data, FetchResponseFailure, FetchResponseSuccess

if TYPE_CHECKING:
    from spots.bootstrap.container import Clients, Core


logger = getLogger(__name__)

class DeezerMetadataService(MetadataProvider):
    def __init__(
        self,
        *,
        clients: Clients,
        core: Core,
    ):
        self.clients = clients
        self.core = core

    @overload
    def get(self, *, track_id: str, search_result: None = None) -> Metadata: ...

    @overload
    def get(
        self, *, track_id: None = None, search_result: dict[str, Any]
    ) -> Metadata: ...

    def get(
        self,
        *,
        track_id: str | None = None,
        search_result: dict[str, Any] | None = None,
    ) -> Metadata:
        logger.debug("Searching for metadata on Deezer...")

        if track_id is not None:
            query_id = track_id
        elif search_result is not None:
            query_id = search_result["id"]
        else:
            raise ValueError("Either track_id or search_result must be provided")

        # check cache first
        url = "https://open.deezer.com/track/" + query_id
        cache = self.core.storage.get(query=url, query_type="metadata")
        if isinstance(cache, Sentinel):
            raise SongNotFound(query_id)
        elif isinstance(cache, Metadata):
            return cache

        # search song if id provided
        if track_id is not None:
            # retrieve track from deezer
            uri = f"https://api.deezer.com/track/{track_id}"
            track_res = fetch_data(uri)

            if isinstance(track_res, FetchResponseFailure):
                track_res = cast(FetchResponseFailure, track_res)
                error_msg = track_res.error

                if error_msg == "no data":
                    raise SongNotFound(f"Id {track_id}")
                else:
                    raise Exception(f"Unknown error occurred: {error_msg}")

            track_res = cast(FetchResponseSuccess, track_res)
            track = cast(dict[str, Any], track_res.data)
        elif search_result is not None:
            track = search_result
        else:
            raise ValueError("Either track_id or search_result must be provided")

        album_info = track["album"]
        album_name = album_info["title"]
        cover = album_info["cover_xl"]

        artist_info = track["artist"]
        artist_name = artist_info["name"]
        track_name = track["title"]

        # get track lyrics
        try:
            lyrics = self.core.lyrics.get_lyrics(title=track_name, artist=artist_name)
        except Exception as e:
            logger.error(f"Error occurred while searching for lyrics", e)
            lyrics = ""

        metadata = Metadata(
            title=track_name,
            artist=artist_name,
            link=track["link"],
            release_date=track["release_date"],
            tracknumber=str(track["track_position"]),
            cover=cover,
            lyrics=lyrics,
            album=album_name,
            preview_url=track["preview"],
            artist_cover=artist_info["picture"],
            artist_id=artist_info["id"],
        )
        self.core.storage.new(query=url, result=metadata, query_type="metadata")
        return metadata

