#!/usr/bin/python3
"""
Contains the FileStorage class
"""

import json
from typing import Dict

from models.metadata import Metadata


class FileStorage:
    """serializes instances to a JSON file & deserializes back to instances"""

    # string - path to the JSON file
    __file_path = ".metadata.json"
    # dictionary - empty but will store all objects by Artist
    __objects: Dict[str, Metadata] = {}

    def all(self) -> Dict[str, Metadata]:
        """"""
        """returns the dictionary __objects

        Returns:
            Dict[str, Metadata]: a dictionary with metadata objects
        """
        return self.__objects

    def new(self, obj: Metadata) -> None:
        """sets in __objects the obj with key <obj artist name>.<obj title name>"""
        if obj is not None:
            key: str = obj.link
            self.__objects[key] = obj

    def save(self) -> None:
        """serializes __objects to the JSON file (path: __file_path)"""
        with open(file=self.__file_path, mode="w") as f:
            objects = {key: value.__dict__ for key, value in self.__objects.items()}
            json.dump(obj=objects, fp=f)

    def reload(self) -> None:
        """deserializes the JSON file to __objects"""
        try:
            with open(file=self.__file_path, mode="r") as f:
                jo = json.load(fp=f)
            for key in jo:
                self.__objects[key] = Metadata(
                    title=jo[key]["title"],
                    artist=jo[key]["artist"],
                    link=jo[key]["link"],
                    cover=jo[key]["cover"],
                    tracknumber=jo[key]["tracknumber"],
                    album=jo[key]["album"],
                    lyrics=jo[key]["lyrics"],
                    release_date=jo[key]["release_date"],
                )
        except:
            pass

    def get(self, url: str) -> Metadata | None:
        """Returns the object based on the url, or None if not found

        Args:
            url (str): The url for metadata

        Returns:
            Metadata | None: the metadata for `url` or None if not exists
        """
        return self.__objects.get(url, None)
