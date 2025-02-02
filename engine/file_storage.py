#!/usr/bin/python3
"""Caches a search query"""

import json
from json.decoder import JSONDecodeError
from logging import info, INFO, basicConfig
from typing import Any, Literal, Optional, TypedDict, overload
from models.metadata import Metadata

basicConfig(level=INFO)

TSpotifyCache = dict[str, Metadata]
TYouTubeCache = dict[str, tuple[str, Metadata, int]]
TArtistCache = dict[str, list[Metadata]]

TSerializedRecord = dict[str, dict[str, Any]]

MediaProviders = Literal["spotify", "youtube", "artist", "ytdl"]

class CacheOptions(TypedDict):
    spotify: TSpotifyCache
    youtube: TYouTubeCache
    artist: TArtistCache
    ytdl: dict[str, Any]

class SerializedCacheOptions(TypedDict):
    spotify: dict[str, TSerializedRecord]
    youtube: TYouTubeCache
    artist: dict[str, list[TSerializedRecord]]
    ytdl: dict[str, Any]

class FileStorage:
    """A class for caching search results in a JSON file."""

    def __init__(self):
        self.__file_path = ".metadata.json"
        self.__objects: CacheOptions = {"youtube": {}, "artist": {}, "spotify": {}, "ytdl": {}}

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
        match query_type:
            case "spotify":
                self.__objects["spotify"][query] = result

            case "youtube":
                self.__objects["youtube"][query] = result

            case "artist":
                if not self.__objects["artist"].get(query):
                    self.__objects["artist"][query] = []
                self.__objects["artist"][query].append(result)

            case "ytdl":
                self.__objects["ytdl"][query] = result

    def save(self) -> None:
        """Serializes and saves the cache to the JSON file."""
        with open(self.__file_path, "w") as file:
            serialized_objects: SerializedCacheOptions = {
                "spotify": {
                    key: value.__dict__
                    for key, value in self.__objects["spotify"].items()
                },
                "youtube": self.__objects["youtube"],
                "artist": {
                    artist: [item.__dict__ for item in playlist]
                    for artist, playlist in self.__objects["artist"].items()
                },
                "ytdl": {
                    key: value
                    for key, value in self.__objects["ytdl"].items()
                }
            }
            json.dump(serialized_objects, file)

    def reload(self) -> None:
        """Deserializes and reloads the cache from the JSON file."""
        try:
            with open(self.__file_path, "r") as file:
                loaded_objects = json.load(file)
                self.__objects["spotify"] = {
                    key: Metadata(**value)
                    for key, value in loaded_objects["spotify"].items()
                }

                self.__objects["youtube"] = loaded_objects["youtube"]

                self.__objects["artist"] = {
                    artist: [Metadata(**item) for item in playlist]
                    for artist, playlist in loaded_objects["artist"].items()
                }
                self.__objects["ytdl"] = {
                    key: value
                    for key, value in loaded_objects["ytdl"].items()
                }
        except (FileNotFoundError, JSONDecodeError):
            self.__objects = {
                "spotify": {},
                "youtube": {},
                "artist": {},
                "ytdl": {},
            }

    @overload
    def get(self, query: str, query_type: Literal["spotify"]) -> Optional[Metadata]: ...
    @overload
    def get(self, query: str, query_type: Literal["youtube"]) -> Optional[tuple[str, Metadata, int]]: ...
    @overload
    def get(self, query: str, query_type: Literal["artist"]) -> Optional[list[Metadata]]: ...
    @overload
    def get(self, query: str, query_type: Literal["ytdl"]) -> Optional[dict[str, Any]]: ...

    def get(self, query: str, query_type: MediaProviders):
        """Gets the search result for a given query and query type.

        Args:
            query (str): The search query.
            query_type (str): `spotify` or `youtube`.

        Returns:
            The search result for the given query and query type.
        """
        return self.__objects[query_type].get(query, None)

