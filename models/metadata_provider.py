from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, overload, Any

from models.metadata import Metadata

if TYPE_CHECKING:
    from bootstrap.container import Core, Clients


class MetadataProvider(ABC):

    @abstractmethod
    def __init__(
        self,
        *,
        core: Core,
        clients: Clients,
    ):
        pass

    @overload
    def get(self, *, track_id: str, search_result: None = None) -> Metadata: ...

    @overload
    def get(
        self, *, track_id: None = None, search_result: dict[str, Any]
    ) -> Metadata: ...

    @abstractmethod
    def get(
        self,
        *,
        track_id: str | None = None,
        search_result: dict[str, Any] | None = None,
    ) -> Metadata:
        """
        Retrieves metadata for a track

        Arguments:
            track_id (str, Optional): the track id to retrieve data from. None if search_result passed. Defaults to None.
            search_result (dict[str, Any], Optional): Pre-fetched result data. None if track_id passed.Defaults to None.

        Returns:
            Metadata: an object with retrieved data

        Raises:
            SongNotFound: if spotify search results empty.
            InvalidURL: if url invalid.
            MetadataNotFound: if metadata not found for id.
        """
        pass

