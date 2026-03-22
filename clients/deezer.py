from logging import info, error
from requests.exceptions import HTTPError
from tenacity import stop_after_delay
from typing import Any, TypedDict, cast

from engine.retry import retry
from models import SongNotFound, InvalidURL, ArtistInfo
from utils.fetch import FetchResponseFailure, FetchResponseSuccess, fetch_data


class DeezerResponseBase(TypedDict):
    total: int
    data: list[dict[str, Any]]


class DeezerClient:

    @retry(stop=stop_after_delay(60))
    def _get_resource_by_url(self, resource_link: str) -> dict[str, Any]:
        base_url = "https://api.deezer.com/"
        if not resource_link.startswith(base_url):
            raise InvalidURL(resource_link)

        resource_response = fetch_data(resource_link)

        if isinstance(resource_response, FetchResponseFailure):
            resource_error = cast(FetchResponseFailure, resource_response)
            error_msg = resource_error.error

            if error_msg == "no data":
                raise SongNotFound(f"Resource not found: {resource_link}")
            else:
                raise Exception(f"Unknown error occured: {error_msg}")

        resource_success = cast(FetchResponseSuccess, resource_response)
        resource_payload = cast(dict[str, Any], resource_success.data)
        return resource_payload

    def artist_top_tracks(self, artist_id: int) -> tuple[ArtistInfo, list[dict[str, Any]]]:
        base_url = f"https://api.deezer.com/artist/{artist_id}"
        top_tracks_res = self._get_resource_by_url(f"{base_url}/top")

        artist_info = self._get_resource_by_url(base_url)

        top_tracks = cast(list[dict[str, Any]], top_tracks_res["data"])
        return ArtistInfo(name=artist_info["name"], cover=artist_info["picture"], id=artist_info["id"]), top_tracks

    def track(self, track_id: int) -> dict[str, Any]:
        track_url = f"https://api.deezer.com/track/{track_id}"
        return self._get_resource_by_url(track_url)

    @retry(stop=stop_after_delay(60))
    def search(self, query: str) -> str:
        try:
            info(f"Searching for {query} on Deezer")
            search_url = f"https://api.deezer.com/search?q={query}&limit=1"
            res = fetch_data(search_url)
            if res.success and res.data is not None:
                res_json = cast(DeezerResponseBase, res.data)
                if res_json["total"] == 0:
                    error("No results found")
                    raise SongNotFound(query)

                return str(res_json["data"][0]["id"])
            else:
                raise SongNotFound(query)
        except HTTPError as e:
            error("An error occured", e)
            raise SongNotFound(query)

