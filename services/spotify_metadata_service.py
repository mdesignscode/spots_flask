from __future__ import annotations

from datetime import datetime
from logging import error, info
from spotipy.exceptions import SpotifyException
from typing import TYPE_CHECKING, Any, overload

from engine.persistence_model import storage
from models.errors import SongNotFound
from models.metadata import Metadata
from models.sentinel import Sentinel

if TYPE_CHECKING:
    from bootstrap.container import Core, Clients

class SpotifyMetadataService:
    def __init__(
        self,
        core: Core,
        clients: Clients,
    ):
        self.core = core
        self.clients = clients

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
        """
        Retrieves metadata for a spotify track

        Arguments:
            track_id (str): the track id to retrieve data from.

        Returns:
            Metadata: an object with retrieved data

        Raises:
            SongNotFound: if spotify search results empty.
            InvalidURL: if spotify url invalid.
            MetadataNotFound: if metadata not found for id.
        """
        info("Searching for metadata on Spotify...")

        if track_id is not None:
            query_id = track_id
        if search_result is not None:
            query_id = search_result["id"]
        else:
            raise ValueError("Either track_id or search_result must be provided")

        # check cache first
        url = "https://open.spotify.com/track/" + query_id
        cache = storage.get(query=url, query_type="spotify")
        if isinstance(cache, Sentinel):
            raise SongNotFound(query_id)
        elif isinstance(cache, Metadata):
            return cache

        # search song if id provided
        if track_id is not None:
            try:
                # retrieve track from spotify
                track = self.clients.spotify.spotify.track(
                    track_id
                )

            except SpotifyException as e:
                if e.http_status == 401:
                    if "Invalid access token" in e.msg:
                        raise RuntimeError("Authentication Failed") from e
                    else:
                        self.clients.spotify.signin()
                        track = self.clients.spotify.spotify.track(
                            track_id
                        )
                else:
                    error(f"Unexpected error occurred when retrieving Spotify metadata")
                    raise RuntimeError(
                        "Unhandled error in get"
                    ) from e

            if not track:
                storage.new(query=url, result=Sentinel(), query_type="spotify")
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
        try:
            song = self.core.lyrics.genius.search_song(
                track_name, artist
            )

            if not song or "Verse" not in song.lyrics or track_name not in song.title:
                lyrics = (
                    self.core.scraper.scrape_azlyrics(
                        artist=artist, title=track_name
                    )
                )
            else:
                lyrics = song.lyrics
        except Exception as e:
            error(e)
            lyrics = ""

        preview_url = track["preview_url"] or ""

        metadata = Metadata(
            track_name,
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

