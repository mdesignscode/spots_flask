"""Caches a search query"""

from json import load, dump
from json.decoder import JSONDecodeError
from typing import Any, Callable, Literal, Optional, TypedDict, Sequence, overload
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
TArtistCache = dict[str, Sequence[Metadata | Sentinel]]

TSerializedRecord = dict[str, dict[str, Any]]

MediaProviders = Literal["spotify", "artist", "ytdl", "yt_likes", "spotify_likes"]

NOT_FOUND = Sentinel()


class CacheOptions(TypedDict):
    spotify: TSpotifyCache
    artist: TArtistCache
    ytdl: dict[str, Any]
    yt_likes: dict[str, YTVideoInfo | Sentinel]
    spotify_likes: TSpotifyCache


class SerializedCacheOptions(TypedDict):
    spotify: dict[str, TSerializedRecord]
    artist: dict[str, list[dict[str, Any]]]
    ytdl: dict[str, YTVideoInfo]
    yt_likes: dict[str, TSerializedRecord]
    spotify_likes: dict[str, TSerializedRecord]


class FileStorage:
    """A class for caching search results in a JSON file."""

    def __init__(self):
        self.__file_path = "./Music/.metadata.json"
        self.__objects: CacheOptions = {
            "artist": {},
            "spotify": {},
            "ytdl": {},
            "yt_likes": {},
            "spotify_likes": {},
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

    @overload
    def new(
        self,
        query: str,
        result: YTVideoInfo | Sentinel,
        query_type: Literal["yt_likes"],
    ) -> None: ...

    @overload
    def new(
        self,
        query: str,
        result: Metadata | Sentinel,
        query_type: Literal["spotify"],
    ) -> None: ...

    @overload
    def new(
        self,
        query: str,
        result: Metadata | Sentinel,
        query_type: Literal["spotify_likes"],
    ) -> None: ...

    @overload
    def new(
        self,
        query: str,
        result: Sequence[Metadata | Sentinel],
        query_type: Literal["artist"],
    ) -> None: ...

    @overload
    def new(
        self,
        query: str,
        result: YTVideoInfo | Sentinel,
        query_type: Literal["ytdl"],
    ) -> None: ...

    def new(
        self,
        query: str,
        result,
        query_type: MediaProviders,
    ) -> None:
        query = query.replace(" Audio", "")

        if self.__objects[query_type].get(query):
            return

        self._dirty = True

        match query_type:
            case "spotify":
                self.__objects["spotify"][query] = result
            case "artist":
                self.__objects["artist"][query] = list(self.__objects["artist"][query]) + [result]
            case "ytdl":
                self.__objects["ytdl"][query] = result
            case "spotify_likes":
                self.__objects["spotify_likes"][query] = result
            case "yt_likes":
                self.__objects["yt_likes"][query] = result

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
            "yt_likes": {
                key: value.__dict__ for key, value in self.__objects["yt_likes"].items()
            },
            "spotify_likes": {
                key: value.__dict__ for key, value in self.__objects["spotify_likes"].items()
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
        print("reloading objects")
        try:
            with open(self.__file_path, "r") as file:
                loaded_objects = load(file)

                if "spotify" in loaded_objects:
                    self.__objects["spotify"] = {
                        key: Metadata(**value) if value != NOT_FOUND.__dict__ else NOT_FOUND
                        for key, value in loaded_objects["spotify"].items()
                    }
                else:
                    self.__objects["spotify"] = {}

                if "spotify_likes" in loaded_objects:
                    self.__objects["spotify_likes"] = {
                        key: Metadata(**value) if value != NOT_FOUND.__dict__ else NOT_FOUND
                        for key, value in loaded_objects["spotify_likes"].items()
                    }
                else:
                    self.__objects["spotify_likes"] = {}

                if "artist" in loaded_objects:
                    self.__objects["artist"] = {
                        artist: [
                            Metadata(**item) if item != NOT_FOUND.__dict__ else NOT_FOUND
                            for item in playlist
                        ]
                        for artist, playlist in loaded_objects["artist"].items()
                    }
                else:
                    self.__objects["artist"] = {}

                if "ytdl" in loaded_objects:
                    self.__objects["ytdl"] = {
                        key: (
                            YTVideoInfo(**value)
                            if value != NOT_FOUND.__dict__
                            else NOT_FOUND
                        )
                        for key, value in loaded_objects["ytdl"].items()
                    }
                else:
                    self.__objects["ytdl"] = {}

                if "yt_likes" in loaded_objects:
                    self.__objects["yt_likes"] = {
                        key: (
                            YTVideoInfo(**value)
                            if value != NOT_FOUND.__dict__
                            else NOT_FOUND
                        )
                        for key, value in loaded_objects["yt_likes"].items()
                    }
                else:
                    self.__objects["yt_likes"] = {}
        except (FileNotFoundError, JSONDecodeError):
            self.__objects = {
                "spotify": {},
                "artist": {},
                "ytdl": {},
                "yt_likes": {},
                "spotify_likes": {},
            }

    @overload
    def get(
        self,
        query: str,
        query_type: Literal["spotify"],
        fetch_data: Callable[[], Metadata],
        *,
        alt_query: str = "",
    ) -> Metadata: ...

    @overload
    def get(
        self,
        query: str,
        query_type: Literal["artist"],
        fetch_data: Callable[[], list[Metadata]],
        *,
        alt_query: str = "",
    ) -> list[Metadata]: ...

    @overload
    def get(
        self,
        query: str,
        query_type: Literal["ytdl"],
        fetch_data: Callable[[], YTVideoInfo],
        *,
        alt_query: str = "",
    ) -> YTVideoInfo: ...

    @overload
    def get(
        self,
        query: str,
        query_type: Literal["yt_likes"],
    ) -> bool: ...

    def get(
        self,
        query: str,
        query_type: MediaProviders,
        fetch_data: Callable[[], Any] | None = None,
        *,
        alt_query: str = "",
    ):
        query = query.replace(" Audio", "")

        if query_type == "yt_likes":
            return query in self.__objects["yt_likes"]

        if fetch_data is None:
            raise TypeError(f"`fetch_data` is required for query_type '{query_type}'")

        cache = self.__objects[query_type].get(query) or self.__objects[query_type].get(
            alt_query
        )

        if isinstance(cache, Sentinel):
            info(f"[Cache Miss] {query}")
            raise SongNotFound(query)
        elif not cache:
            print("Performing new search")
            return fetch_data()
        else:
            info(f"[Cache] {query}")
            return cache

