#!/usr/bin/python3
"""Caches a search query"""

import json
from logging import info, INFO, basicConfig
from typing import Dict
from models.metadata import Metadata

basicConfig(level=INFO)

class FileStorage:
    """A class for caching search results in a JSON file."""

    def __init__(self):
        self.__file_path = ".metadata.json"
        self.__objects = {"spotify": {}, "youtube": {}}

    def all(self) -> Dict[str, Dict]:
        """Returns the stored objects."""
        return self.__objects

    def new(self, query: str, result, query_type: str) -> None:
        """Adds a new search result to the cache.

        Args:
            query (str): The search query.
            result (Metadata | Tuple[str, dict, int]): The search result.
            query_type (str): `spotify` or `youtube`.
        """
        if query_type == "spotify":
            self.__objects["spotify"][query] = result
        elif query_type == "youtube":
            self.__objects["youtube"][query] = result

    def save(self) -> None:
        """Serializes and saves the cache to the JSON file."""
        with open(self.__file_path, "w") as file:
            serialized_objects = {
                "spotify": {
                    key: value.__dict__
                    for key, value in self.__objects["spotify"].items()
                },
                "youtube": self.__objects["youtube"],
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
        except:
            self.__objects = {
                "spotify": {},
                "youtube": {}
            }

    def get(self, query: str, query_type: str):
        """Gets the search result for a given query and query type.

        Args:
            query (str): The search query.
            query_type (str): `spotify` or `youtube`.

        Returns:
            The search result for the given query and query type.
        """
        return self.__objects[query_type].get(query, None)
