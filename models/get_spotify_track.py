#!/usr/bin/python3
"""A class to retrieve metadata for a spotify track, album or playlist"""

from datetime import datetime
from typing import Any, Dict, List, Tuple, cast
from dotenv import load_dotenv
from engine import storage
from logging import info, basicConfig, error, ERROR, INFO
from lyricsgenius import Genius
from models.errors import InvalidURL, SongNotFound
from models.metadata import Metadata
from os import getenv
from re import search, match
from requests.exceptions import ReadTimeout
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy import Spotify
from tenacity import retry, stop_after_delay

load_dotenv()


class GetSpotifyTrack:
    """A class to retrieve metadata for a spotify track, album or playlist

    Attributes:
        track_url (str): The spotify url to be processed
    """

    # create a Spotify API client
    spotify = Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=getenv("SPOTIPY_CLIENT_ID"), client_secret=getenv("client_secret")
        )
    )

    # create genius api for lyrics
    genius = Genius(getenv("lyricsgenius_key"))

    def __init__(self, track_url: str = "") -> None:
        """Initializes a spotify object

        Args:
            track_url (str, optional): A spotify url to be processed. Defaults to "".
        """
        self.track_url: str = track_url

    @retry(stop=stop_after_delay(max_delay=60))
    def get_track(self, track_id: str) -> Metadata:
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
        print("Searching for metadata on Spotify...")
        metadata_in_file: Metadata | None = storage.get(self.track_url)
        if metadata_in_file:
            return metadata_in_file

        try:
            # retrieve track from spotify
            track = self.spotify.track(track_id)

            if not track:
                raise SongNotFound(f"Spotify id: {track_id}")

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
                release_date = release_date_obj.strftime("%Y")
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
            song = self.genius.search_song(track_name, artist)

            if not song or "Verse" not in song.lyrics or track_name not in song.title:
                lyrics = ""
            else:
                lyrics = song.lyrics

            metadata = Metadata(
                track_name,
                artist=artist,
                link=track_url,
                cover=cover,
                tracknumber=track_number,
                album=album_name,
                lyrics=lyrics,
                release_date=release_date,
            )

            return metadata

        except SpotifyException:
            basicConfig(level=ERROR)
            error(f"{self.track_url} is invalid")
            raise InvalidURL(self.track_url)

    @retry(stop=stop_after_delay(60))
    def process_url(self):
        """
        Processes a Spotify URL and returns metadata information.

        Returns:
            Union[Tuple[List[Metadata], Dict[str, Unknown]], Metadata, None]:
                Either a tuple containing a list of Metadata objects and a dictionary with
                information about the processed Spotify resource, or a single Metadata object, or None if song not found.

        Raises:
            InvalidURL:
                Raised when an invalid Spotify URL is provided.
            ReadTimeout:
                Raised when the network connection times out during processing.
        """
        basicConfig(level=ERROR)

        track_list: list[Metadata] = []
        playlist_data = {}
        try:
            resource_type = self.track_url.split("/")[3]
            track_id = self.track_url.split("/")[-1].split("?")[0]

            if resource_type == "playlist":
                print("Processing Spotify Playlist...")

                # get spotify playlist
                get_playlist = self.spotify.__getattribute__(resource_type)
                spotify_obj = get_playlist(track_id)

                album_data = {
                    "cover": spotify_obj["images"][0]["url"],
                    "name": spotify_obj["name"],
                    "artist": None,
                }

                # get playlist tracks
                playlist = spotify_obj["tracks"]["items"]

                playlist_data = album_data
                # get metadata for each track in playlist
                for track in playlist:
                    try:
                        track_list.append(self.get_track(track["track"]["id"]))
                    except Exception as e:
                        error(e)

                return track_list, album_data

            elif resource_type == "album":
                print("Processing Album...")

                # get spotify album
                get_album = self.spotify.__getattribute__(resource_type)
                spotify_obj = get_album(track_id)

                # artists
                artist_list = [artist["name"] for artist in spotify_obj["artists"]]
                album_data = {
                    "cover": spotify_obj["images"][0]["url"],
                    "name": spotify_obj["name"],
                    "artist": ", ".join(artist_list),
                }

                # get album tracks
                album = spotify_obj["tracks"]["items"]

                playlist_data = album_data
                # get metadata for each track in playlist
                for track in album:
                    try:
                        track_list.append(self.get_track(track["id"]))
                    except Exception as e:
                        error(e)

                return track_list, album_data

            elif resource_type == "track":
                print("Processing Single...")
                try:
                    return self.get_track(track_id)
                except Exception as e:
                    error(e)

            else:
                error(f"Invalid url: {self.track_url}")
                raise InvalidURL(self.track_url)

        except ReadTimeout:
            basicConfig(level=ERROR)
            error("Network Connection Timed Out!")
            return track_list, playlist_data

    @retry(stop=stop_after_delay(30))
    async def search_track(self, query: str) -> Tuple[Metadata, List[Metadata] | None] | None:
        """Searches for a title on spotify

        Args:
            query (str): the title to be searched for

        Raises:
            SongNotFound: the `query` is not found on spotify.
            TypeError: if query format not: `Artist - Title`

        Returns:
            Tuple[Metadata, List[Metadata] | None]: The metadata of searched track and a list of recommended tracks.
        """
        basicConfig(level=INFO)

        if "-" not in query:
            basicConfig(level=ERROR)
            error("Search format: `Artist` - `Title`")
            raise TypeError("Search format: `Artist` - `Title`")

        # search for a single
        single_result = self.spotify.search(query)

        if not single_result:
            info(f"{query} not found")
            raise SongNotFound(query)

        id = single_result["tracks"]["items"][0]["id"]

        # get metadata
        try:
            single_data = self.get_track(id)
        except SongNotFound:
            info(f"{query} not found")
            return

        # get query artist
        query_artist = query.split(" - ")[0].lower()
        result_artist = single_data.artist.lower()
        if len(query_artist) < len(result_artist):
            artist_match = search(query_artist, result_artist)
        else:
            artist_match = search(result_artist, query_artist)

        # if search result does not match query
        # then query may be a single album
        if not artist_match and not search(single_data.title.lower(), query.lower()):
            print("Searching for album version...")
            # get album id of first result
            results = self.spotify.search(query, type="album")

            if not results:
                info(f"{query} not found")
                raise SongNotFound(query)

            album_id = results["albums"]["items"][0]["id"]

            # get album search function
            get_album = self.spotify.__getattribute__("album")
            album = get_album(album_id)

            # get id of first result
            id = album["tracks"]["items"][0]["id"]

            try:
                return self.get_track(id), self.get_recommended_tracks(id)
            except SongNotFound:
                info(f"{query} not found")
                return

        return single_data, self.get_recommended_tracks(id)

    @retry(stop=stop_after_delay(60))
    def get_recommended_tracks(self, id: str) -> List[Metadata] | None:
        """Get a list of recommended songs for a track

        Args:
            id (str): the id of the track

        Returns:
            List[Metadata] | None: A list of metadata for each song or None if no recommendations found
        """
        # get related songs
        results = self.spotify.recommendations(seed_tracks=[id])

        if not results:
            return

        recommended_tracks = []
        for track in results["tracks"]:
            try:
                recommended_tracks.append(self.get_track(track["id"]))
            except:
                pass

        return recommended_tracks

    @retry(stop=stop_after_delay(60))
    def artist_albums(self, artist: str):
        """
        Retrieves the albums of a given artist.

        Args:
            artist (str): The name of the artist."""
        # search for the artist
        result = self.spotify.search(artist, 1, type="artist")

        if not result:
            return

        data = cast(Dict[str, Any], result)
        artist_items: Dict[str, Any] = data["artists"]["items"][0]
        artist_id = artist_items["id"]

        # get top tracks
        top_tracks_search = self.spotify.artist_top_tracks(artist_id)
        top_tracks_playlist = []
        if top_tracks_search:
            # get metadata for each top track
            top_tracks_playlist = [
                self.get_track(top_track["id"])
                for top_track in top_tracks_search["tracks"]
            ]

        top_tracks_playlist_data = {
            "cover": "/static/single-cover.jpg",
            "name": "Top Tracks",
            "artist": None,
        }

        # retrieve artist albums
        result = self.spotify.artist_albums(artist_id)
        data = cast(Dict[str, Any], result)

        # filter albums for the specified artist
        artist_albums = list(
            filter(
                lambda item: item["artists"][0]["name"].lower() == artist.lower(),
                data["items"],
            )
        )

        albums = []

        for item in artist_albums:
            # get all tracks of album
            self.track_url = "https://open.spotify.com/album/" + item["id"]

            albums.append(self.process_url())

        albums.append((top_tracks_playlist, top_tracks_playlist_data))

        return albums, {
            "image": artist_items["images"][0]["url"],
            "name": artist_items["name"],
        }
