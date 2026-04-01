from __future__ import annotations

from datetime import datetime
from logging import getLogger
from spotipy.exceptions import SpotifyException
from typing import Any, overload, TYPE_CHECKING

from spots.engine import storage
from spots.models import SongNotFound, Metadata, Sentinel, MetadataProvider, SpotifyUnavailableError

if TYPE_CHECKING:
    from spots.bootstrap.container import Core, Clients
    from spots.clients import SpotifyClient


logger = getLogger(__name__)

class SpotifyMetadataService(MetadataProvider):
    def __init__(
        self,
        *,
        clients: Clients,
        core: Core,
    ):
        self.clients = clients
        self.core = core

    def _spotify(self) -> SpotifyClient:
        if not self.clients.spotify:
            raise SpotifyUnavailableError(
                "Spotify client is not configured. Enable Spotify features in your environment."
            )
        return self.clients.spotify

    @overload
    def get(
        self, *, track_id: str, search_result: None = None
    ) -> Metadata: ...

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
        logger.info("Searching for metadata on Spotify...")

        if track_id is not None:
            query_id = track_id
        if search_result is not None:
            query_id = search_result["id"]
        else:
            raise ValueError("Either track_id or search_result must be provided")

        # check cache first
        url = "https://open.spotify.com/track/" + query_id
        cache = storage.get(query=url, query_type="metadata")
        if isinstance(cache, Sentinel):
            raise SongNotFound(query_id)
        elif isinstance(cache, Metadata):
            return cache

        # search song if id provided
        if track_id is not None:
            try:
                # retrieve track from spotify
                track = self._spotify().client.track(
                    track_id
                )

            except SpotifyException as e:
                if e.http_status == 401:
                    if "Invalid access token" in e.msg:
                        raise RuntimeError("Authentication Failed") from e
                    else:
                        self._spotify().signin()
                        track = self._spotify().client.track(
                            track_id
                        )
                else:
                    logger.error(f"Unexpected error occurred when retrieving Spotify metadata")
                    raise RuntimeError(
                        "Unhandled error in get"
                    ) from e

            if not track:
                storage.new(query=url, result=Sentinel(), query_type="metadata")
                raise SongNotFound(f"Spotify id: {track_id}")
        elif search_result is not None:
            track = search_result

        album = track["album"]

        # get track number
        total_track = album["total_tracks"]
        track_position = track["track_number"]
        track_number = f"{track_position}/{total_track}"

        # cover image
        cover = album["images"][0]["url"]

        # get release date
        try:
            release_date_str = album["release_date"]
            release_date_obj = datetime.strptime(release_date_str, "%Y-%m-%d")
            # release_date = release_date_obj.strftime("%Y")
            release_date = release_date_obj.strftime("%Y-%m-%d")
        except ValueError:
            release_date = None

        # get track name and artist
        track_name = track["name"]

        # artists
        artist_list = [artist["name"] for artist in track["artists"]]
        # remove featured artists from artists list
        for artist in artist_list:
            if artist.lower() in track_name.lower():
                artist_list.remove(artist)

        artist = ", ".join(artist_list)

        track_url = track["external_urls"]["spotify"]
        album_name = album["name"]

        # get track lyrics
        lyrics = self.core.lyrics.get_lyrics(
            title=track_name, artist=artist
        )

        preview_url = track["preview_url"] or ""

        first_artist = track["artists"][0]
        metadata = Metadata(
            track_name,
            artist_id=first_artist["id"],
            artist=artist,
            link=track_url,
            cover=cover,
            tracknumber=track_number,
            album=album_name,
            lyrics=lyrics,
            release_date=release_date,
            preview_url=preview_url,
        )

        return metadata

