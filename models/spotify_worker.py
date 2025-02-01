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
from models.retrieve_spotify_playlist import retrieve_spotify_playlist as scrape_playlist
from os import environ, getenv
from re import search
from requests.exceptions import ReadTimeout
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy import Spotify
from spotipy.util import prompt_for_user_token
from tenacity import retry, stop_after_delay

load_dotenv()


class SpotifyWorker:
    """A class to retrieve metadata for a spotify track, album or playlist

    Attributes:
        track_url (str): The spotify url to be processed
    """

    # create a Spotify API client
    auth_manager = SpotifyClientCredentials()
    spotify = Spotify(auth_manager=auth_manager)

    # create genius api for lyrics
    genius = Genius(getenv("lyricsgenius_key"))

    def __init__(self, track_url: str = "") -> None:
        """Initializes a spotify object

        Args:
            track_url (str, optional): A spotify url to be processed. Defaults to "".
        """
        self.track_url: str = track_url

    @retry(stop=stop_after_delay(max_delay=60))
    def get_user(self) -> str | None:
        """Retrieves the current user

        Args:
            username (str): the user's name
            scope (str, optional): the scope to read user data. Defaults to "user-library-read".

        Returns:
            str: The user's display name
        """
        if not getenv("username"):
            return

        user = None

        try:
            user = self.spotify.current_user()
        except SpotifyException:
            self.signin()
            user = self.spotify.current_user()

        if user:
            return user["display_name"]

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
        basicConfig(level=INFO)
        info("Searching for metadata on Spotify...")
        url = "https://open.spotify.com/track/" + track_id
        cache = storage.get(url, "spotify")
        if cache:
            info(f"Cached result: {cache.artist} - {cache.title}")
            return cache

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
                song = self.genius.search_song(track_name, artist)

                if not song or "Verse" not in song.lyrics or track_name not in song.title:
                    lyrics = ""
                else:
                    lyrics = song.lyrics
            except Exception:
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
                spotify_id=track_id,
            )

            storage.new(url, metadata, "spotify")

            return metadata

        except SpotifyException:
            basicConfig(level=ERROR)
            error(f"{self.track_url} is invalid")
            raise InvalidURL(self.track_url)

    @retry(stop=stop_after_delay(60))
    def process_url(self, single: bool = True):
        """
        Processes a Spotify URL and returns metadata information.

        Args:
            single: (boolean, optional): don't search for recommended tracks. Defaults to False

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
                info("Processing Spotify Playlist...")

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
                info("Processing Album...")

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
                        error(f"Error occurred while processing playlist: {e}")

                return track_list, album_data

            elif resource_type == "track":
                info("Processing Single...")
                try:
                    return (
                        self.get_track(track_id),
                        self.get_recommended_tracks(track_id) if not single else None,
                    )
                except Exception as e:
                    error(f"Error occurred while processing single: {e}")

            else:
                error(f"Invalid url: {self.track_url}")
                raise InvalidURL(self.track_url)

        except ReadTimeout:
            basicConfig(level=ERROR)
            error("Network Connection Timed Out!")
            return track_list, playlist_data

    @retry(stop=stop_after_delay(30))
    def search_track(
        self, query: str, single: bool = False
    ) -> Tuple[Metadata, List[Metadata] | None] | None:
        """Searches for a title on spotify

        Args:
            query (str): the title to be searched for
            single: (str | None, optional): don't search for recommended tracks. Defaults to None

        Raises:
            SongNotFound: the `query` is not found on spotify.
            TypeError: if query format not: `Artist - Title`

        Returns:
            Tuple[Metadata, List[Metadata] | None]: The metadata of searched track and a list of recommended tracks.
        """
        basicConfig(level=INFO)

        if "-" not in query:
            basicConfig(level=ERROR)
            error_txt = "Search format: `Artist` - `Title`"
            error(error_txt)
            raise TypeError(error_txt)

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
                return (
                    self.get_track(id),
                    self.get_recommended_tracks(id) if not single else None,
                )
            except SongNotFound:
                info(f"{query} not found")

                return

        return single_data, self.get_recommended_tracks(id) if not single else None

    @retry(stop=stop_after_delay(60))
    def get_recommended_tracks(self, id: str) -> List[Metadata] | None:
        """Get a list of recommended songs for a track

        Args:
            id (str): the id of the track

        Returns:
            List[Metadata] | None: A list of metadata for each song or None if no recommendations found
        """
        info(f"Retrieving recommended tracks for id: {id}")
        # get related songs
        try:
            results = self.spotify.recommendations(seed_tracks=[id])
        except Exception:
            return

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
    def artist_albums(self, artist: str, essentials_playlist: str | None = None):
        """
        Retrieves the albums of a given artist.

        Args:
            artist (str): The name of the artist. Can be either then name of artist or spotify url to artist
            essentials_playlist (str | None, optional): A spotify playlist to scrape. Defaults to None.
        """
        artist_url = "https://open.spotify.com/artist/"
        artist_id = ""

        # get artist by id
        if (artist_url in artist):
            artist_id = artist.replace(artist_url, "").split("?")[0]
            result = self.spotify.__getattribute__("artist")(artist_id)

        else:
            # search for the artist
            result = self.spotify.search(artist, 1, type="artist")

        if not result:
            return

        artist_name = result["name"]
        info(f"Searching for albums by {artist_name}")

        # get artist items
        if not artist_url in artist:
            data = cast(Dict[str, Any], result)
            artist_items: Dict[str, Any] = data["artists"]["items"][0]
            artist_id = artist_items["id"]
        else:
            artist_items = result

        artist_cover = artist_items["images"][0]["url"]

        # get top tracks
        info("Searching for top tracks")
        top_tracks_search = self.spotify.artist_top_tracks(artist_id)
        top_tracks_playlist = []
        if top_tracks_search:
            # get metadata for each top track
            top_tracks_playlist = [
                self.get_track(top_track["id"])
                for top_track in top_tracks_search["tracks"]
            ]

        top_tracks_playlist_data = {
            "cover": artist_cover,
            "name": "Top Tracks",
            "artist": None,
        }

        # retrieve artist albums
        result = self.spotify.artist_albums(artist_id)
        data = cast(Dict[str, Any], result)

        # filter albums for the specified artist
        artist_albums = list(
            filter(
                lambda item: any(
                    artist_obj["name"].lower() == artist.lower() for artist_obj in item["artists"]
                ),
                data["items"],
            )
        )

        artist_albums = data["items"]
        albums = []

        for item in artist_albums:
            # get all tracks of album
            self.track_url = "https://open.spotify.com/album/" + item["id"]

            albums.append(self.process_url())

        albums.append((top_tracks_playlist, top_tracks_playlist_data))

        if essentials_playlist:
            # get artist's This Is playlist
            scraped_ids, scraped_cover, scraped_title = scrape_playlist(essentials_playlist)
            scraped_playlist = [self.get_track(id) for id in scraped_ids]

            essential_cover = scraped_cover if scraped_cover else '/static/single-cover.jpg'
            essential_title = scraped_title if scraped_title else f'This is {artist_name}'
            scraped_data = {
                    'cover': essential_cover,
                    'name': essential_title,
                    'artist': artist_name
            }

            albums.append((scraped_playlist, scraped_data))

        return albums, {
            "cover": artist_items["images"][0]["url"],
            "name": artist_items["name"],
        }

    @retry(stop=stop_after_delay(60))
    def user_saved_tracks(self) -> list[Metadata] | None:
        """retrieves a user's saved tracks

        Returns:
            list[Metadata] | None: A list of Metadata objects or None
        """
        info("Searching for user saved tracks...")
        limit = 50
        user_tracks = None

        try:
            user_tracks = self.spotify.current_user_saved_tracks(limit=limit)
        except SpotifyException:
            self.signin()
            user_tracks = self.spotify.current_user_saved_tracks(limit=limit)

        if user_tracks:
            total_tracks = user_tracks["total"]
            # get first 50 tracks's ids
            id_list = [track["track"]["id"] for track in user_tracks["items"]]

            # check if there are more tracks
            next_page = user_tracks["next"]
            if next_page:
                index = limit

                # paginate through the rest of the tracks
                while index <= total_tracks:
                    user_tracks = self.spotify.current_user_saved_tracks(
                        offset=index, limit=limit
                    )

                    if user_tracks:
                        # append the next set of ids
                        [
                            id_list.append(track["track"]["id"])
                            for track in user_tracks["items"]
                        ]

                    index += limit

            # get metadata for each track
            return [self.get_track(id) for id in id_list]

    def signin(self):
        """signs into a user's spotify account"""
        # sign user in if username present in env
        username = getenv("username")
        if not username:
            return

        scope = getenv("scope") or "user-library-read"

        info(f"Signing in to {username} on Spotify with scope: {scope}")

        token = prompt_for_user_token(username, scope)

        if token:
            info("Signed in")
            self.spotify = Spotify(auth=token)
        else:
            raise Exception("Can't get token for", username)

    @retry(stop=stop_after_delay(30))
    def modify_saved_tracks_playlist(self, action: str, tracks: str):
        environ["scope"] = "user-library-modify"
        self.signin()
        info(f"Removing {tracks} from playlist...")
        if action == "add":
            self.spotify.current_user_saved_tracks_add(tracks)
        elif action == "delete":
            self.spotify.current_user_saved_tracks_delete([tracks])
        else:
            raise TypeError("`delete` or `add` actions only")

