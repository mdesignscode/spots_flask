"""Caches a search query"""

from json import load, dump
from json.decoder import JSONDecodeError
from typing import Any, Callable, Literal, Optional, TypedDict, cast, overload
from models.errors import SongNotFound
from models.metadata import Metadata
from models.sentinel import Sentinel
from models.yt_video_info import YTVideoInfo
from pathlib import Path
from shutil import move
from tempfile import NamedTemporaryFile
from logging import info, INFO, basicConfig

basicConfig(level=INFO)

TSpotifyCache = dict[str, Metadata | Sentinel]
TArtistCache = dict[str, list[Metadata | Sentinel]]

TSerializedRecord = dict[str, dict[str, Any]]

MediaProviders = Literal["spotify", "artist", "ytdl"]

NOT_FOUND = Sentinel()

class CacheOptions(TypedDict):
    spotify: TSpotifyCache
    artist: TArtistCache
    ytdl: dict[str, Any]


class SerializedCacheOptions(TypedDict):
    spotify: dict[str, TSerializedRecord]
    artist: dict[str, list[dict[str, Any]]]
    ytdl: dict[str, YTVideoInfo]


class FileStorage:
    """A class for caching search results in a JSON file."""

    def __init__(self):
        self.__file_path = ".metadata.json"
        self.__objects: CacheOptions = {
            "artist": {},
            "spotify": {},
            "ytdl": {},
        }
        self._dirty = False

    def update_ytdl(
        self,
        query: str,
        *,
        title: Optional[str] = None,
        uploader: Optional[str] = None,
    ) -> None:
        """Update fields of an existing YT-DLP cache entry."""
        record = self.__objects["ytdl"].get(query)

        if not record:
            return

        if title is not None:
            record.title = title

        if uploader is not None:
            record.uploader = uploader

    def all(self) -> CacheOptions:
        """Returns the stored objects."""
        return self.__objects

    def new(self, query: str, result, query_type: MediaProviders) -> None:
        """Adds a new search result to the cache.

        Args:
            query (str): The search query.
            result (Metadata | Tuple[str, dict, int]): The search result.
            query_type (str): `spotify` | `youtube` | `artist` | `ytdl`.
        """
        query = query.replace(" Audio", "")
        if not self.__objects[query_type].get(query):
            self._dirty = True
        else:
            return

        match query_type:
            case "spotify":
                self.__objects["spotify"][query] = result

            case "artist":
                self.__objects["artist"][query] = result

            case "ytdl":
                self.__objects["ytdl"][query] = result

    def save(self) -> None:
        """Serializes and saves the cache to the JSON file safely."""
        if not self._dirty:
            return

        serialized_objects: SerializedCacheOptions = {
            "spotify": {
                key: value.__dict__ for key, value in self.__objects["spotify"].items()
            },
            "artist": {
                artist: [item.__dict__ for item in playlist]
                for artist, playlist in self.__objects["artist"].items()
            },
            "ytdl": {
                key: value.__dict__ for key, value in self.__objects["ytdl"].items()
            },
        }

        # Write to temp file in the same directory
        dir_path = Path(self.__file_path).parent
        with NamedTemporaryFile(
            "w", dir=dir_path, delete=False, encoding="utf-8"
        ) as tmp_file:
            dump(serialized_objects, tmp_file)
            temp_path = tmp_file.name

        tmp_file.close()

        # Atomically replace the original file
        move(temp_path, self.__file_path)

        self._dirty = False

    def reload(self) -> None:
        """Deserializes and reloads the cache from the JSON file."""
        try:
            with open(self.__file_path, "r") as file:
                loaded_objects = load(file)
                self.__objects["spotify"] = {
                    key: Metadata(**value) if value != NOT_FOUND.__dict__ else NOT_FOUND
                    for key, value in loaded_objects["spotify"].items()
                }

                self.__objects["artist"] = {
                    artist: [Metadata(**item) if item != NOT_FOUND.__dict__ else NOT_FOUND for item in playlist]
                    for artist, playlist in loaded_objects["artist"].items()
                }
                self.__objects["ytdl"] = {
                    key: YTVideoInfo(**value) if value != NOT_FOUND.__dict__ else NOT_FOUND
                    for key, value in loaded_objects["ytdl"].items()
                }
        except (FileNotFoundError, JSONDecodeError):
            self.__objects = {
                "spotify": {},
                "artist": {},
                "ytdl": {},
            }

    @overload
    def get(
        self,
        query: str,
        query_type: Literal["spotify"],
        fetch_data: Callable[[], Metadata],
    ) -> Metadata: ...
    @overload
    def get(
        self,
        query: str,
        query_type: Literal["artist"],
        fetch_data: Callable[[], list[Metadata]],
    ) -> list[Metadata]: ...
    @overload
    def get(
        self,
        query: str,
        query_type: Literal["ytdl"],
        fetch_data: Callable[[], YTVideoInfo],
    ) -> YTVideoInfo: ...

    def get(
            self, query: str, query_type: MediaProviders, fetch_data: Callable[[], Any], alt_query: str = ""
    ):
        """Gets the search result for a given query and query type.

        Args:
            query (str): The search query.
            query_type (str): `spotify` or `youtube`.
            fetch_data (Callable[[], Any]): A callback that makes a network request for new data.
            alt_query (str, Optional): An alternative query to lookup. Defaults to "".

        Returns:
            The search result for the given query and query type.
        """
        query = query.replace(" Audio", "")
        cache = self.__objects[query_type].get(query, None) or self.__objects[query_type].get(alt_query, None)
        print(cache)
        print(f"Query: {query}\n\n")
        if isinstance(cache, Sentinel):
            info(f"[Cache Miss] {query}")
            raise SongNotFound(query)

        elif not cache:
            return fetch_data()

        else:
            info(f"[Cache] {query}")
            return cache

