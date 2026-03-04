from __future__ import annotations
from dataclasses import dataclass

from engine.persistence_model import storage
from logging import info
from models.errors import EmptySpotifyLikes, SongNotFound
from spotipy.exceptions import SpotifyException
from tenacity import stop_after_delay
from engine.retry import retry
from typing import TYPE_CHECKING

from models.playlist_info import PlaylistInfo

if TYPE_CHECKING:
    from bootstrap.container import Core, Domain, Orchestration, Clients


@dataclass
class ArtistResult:
    playlist: list[PlaylistInfo]
    name: str
    cover: str

class SpotifyPlaylistCompilation:
    """A service for retrieving a collection of playlists from Spotify"""

    def __init__(self, *, core: Core, domain: Domain, orchestration: Orchestration, clients: Clients) -> None:
        self.core = core
        self.domain = domain
        self.orchestration = orchestration
        self.clients = clients

    @retry(stop=stop_after_delay(60))
    def artist_albums(self, *, artist: str, essentials_playlist: str | None = None) -> ArtistResult:
        """
        Retrieves the albums of a given artist.

        Args:
            artist (str): The name of the artist. Can be either then name of artist or spotify url to artist
            essentials_playlist (str | None, optional): A spotify playlist to scrape. Defaults to None.
        """

        artist_search = self.domain.spotify_search.search_artist(artist)
        artist_name = artist_search["name"]
        artist_id = artist_search["id"]
        artist_cover = artist_search["images"][0]["url"]

        all_artist_albums: list[PlaylistInfo] = []

        # get artist's This Is playlist
        if essentials_playlist:
            essentials_playlist_data = self.core.scraper.scrape_spotify_playlist(
                essentials_playlist
            )

            scraped_playlist = [self.orchestration.metadata.spotify_metadata.get(track_id=track_id) for track_id in essentials_playlist_data.ids]
            domain_matches = self.orchestration.search.filter_matching_domain_results(spotify_results=scraped_playlist)

            scraped_cover = essentials_playlist_data.cover
            scraped_title = essentials_playlist_data.name
            essential_cover = (
                scraped_cover if scraped_cover else "/static/single-cover.jpg"
            )
            essential_title = (
                scraped_title if scraped_title else f"This is {artist_name}"
            )
            scraped_data = {
                "cover": essential_cover,
                "name": essential_title,
                "artist": artist_name,
            } | {"spotify_metadata": domain_matches.spotify, "youtube_metadata": domain_matches.youtube}

            all_artist_albums.append(PlaylistInfo(**scraped_data))

        # top tracks
        try:
            top_tracks = self.orchestration.search.spotify_search.search_artist_top_tracks(artist_id=artist_id)
            all_artist_albums.append(top_tracks)
        except SongNotFound:
            pass

        # retrieve artist albums
        result = self.clients.spotify.spotify.artist_albums(artist_id)
        if not result:
            return ArtistResult(playlist=all_artist_albums, name=artist_name, cover=artist_cover)

        # filter albums for the specified artist
        artist_albums = list(
            filter(
                lambda item: any(
                    artist_obj["name"].lower() == artist.lower()
                    for artist_obj in item["artists"]
                ),
                result["items"],
            )
        )

        artist_albums = result["items"]

        for item in artist_albums:
            # get all tracks of album
            album_url = "https://open.spotify.com/album/" + item["id"]

            all_artist_albums.append(self.orchestration.search.spotify_search.search_album(album_url))

        return ArtistResult(playlist=all_artist_albums, name=artist_name, cover=artist_cover)

    @retry(stop=stop_after_delay(60))
    def user_saved_tracks(self) -> PlaylistInfo:
        """retrieves a user's saved tracks

        Returns:
            list[Metadata]: A list of Metadata objects or None

        Raises:
            EmptySpotifyLikes: When no likes returned
        """
        info("Searching for user saved tracks...")
        limit = 50
        user_tracks = None

        try:
            user_tracks = self.clients.spotify.spotify.current_user_saved_tracks(limit=limit)
        except SpotifyException:
            self.clients.spotify.signin()
            user_tracks = self.clients.spotify.spotify.current_user_saved_tracks(limit=limit)

        if not user_tracks:
            raise EmptySpotifyLikes

        total_tracks = user_tracks["total"]
        # get first 50 tracks's ids
        id_list = [track["track"]["id"] for track in user_tracks["items"]]

        # check if there are more tracks
        next_page = user_tracks["next"]
        if next_page:
            index = limit

            # paginate through the rest of the tracks
            while index <= total_tracks:
                user_tracks = self.clients.spotify.spotify.current_user_saved_tracks(offset=index, limit=limit)

                if user_tracks:
                    # append the next set of ids
                    for track in user_tracks["items"]:
                        id_list.append(track["track"]["id"])

                index += limit

        # get metadata for each track
        metadata_list = []
        for index, track_id in enumerate(id_list):
            print(f"Getting liked song {index + 1}/{len(id_list)}")
            # get track data
            metadata = self.orchestration.metadata.spotify_metadata.get(track_id=track_id)
            metadata_list.append(metadata)

            # add to likes cache
            title = f"{metadata.artist} - {metadata.title}"
            storage.new(query=title, result=metadata, query_type="spotify_likes")

            if (index % 10 == 0) or (index == (len(id_list) - 1)):
                storage.save()

        domain_matches = self.orchestration.search.filter_matching_domain_results(spotify_results=metadata_list)
        cover = "avatar.jpg"
        username = self.clients.secrets.read(key="username")
        if not username:
            raise RuntimeError("No username provided in `.env` file")
        return PlaylistInfo(cover=cover, name=username, spotify_metadata=domain_matches.spotify,youtube_metadata=domain_matches.youtube)

