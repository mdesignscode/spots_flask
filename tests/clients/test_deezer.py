from unittest.mock import patch

import pytest

from spots_cli.clients import DeezerClient
from spots_cli.models import InvalidURL, SongNotFound
from spots_cli.utils import FetchResponseFailure, FetchResponseSuccess

FETCH = "spots_cli.clients.deezer.fetch_data"


@pytest.fixture
def client():
    return DeezerClient()


def test_search_returns_first_track_id(client):
    response = FetchResponseSuccess(data={"total": 1, "data": [{"id": 3135556}]})
    with patch(FETCH, return_value=response) as fetch:
        assert client.search("Daft Punk - One More Time") == "3135556"
    assert "q=Daft Punk - One More Time" in fetch.call_args.args[0]


def test_search_with_no_results_raises_not_found(client):
    response = FetchResponseSuccess(data={"total": 0, "data": []})
    with patch(FETCH, return_value=response):
        with pytest.raises(SongNotFound):
            client.search("nothing - here")


def test_track_fetches_by_id(client):
    with patch(FETCH, return_value=FetchResponseSuccess(data={"id": 7})) as fetch:
        assert client.track(7) == {"id": 7}
    fetch.assert_called_once_with("https://api.deezer.com/track/7")


def test_missing_resource_raises_not_found(client):
    with patch(FETCH, return_value=FetchResponseFailure(error="no data")):
        with pytest.raises(SongNotFound):
            client.track(7)


def test_non_deezer_url_is_rejected(client):
    with pytest.raises(InvalidURL):
        client._get_resource_by_url.__wrapped__(client, "https://example.com/track/1")


def test_artist_top_tracks(client):
    responses = {
        "https://api.deezer.com/artist/27/top": FetchResponseSuccess(
            data={"data": [{"id": 1}, {"id": 2}]}
        ),
        "https://api.deezer.com/artist/27": FetchResponseSuccess(
            data={"name": "Daft Punk", "picture": "cover.jpg", "id": 27}
        ),
    }
    with patch(FETCH, side_effect=lambda url: responses[url]):
        artist, tracks = client.artist_top_tracks(27)

    assert (artist.name, artist.cover, artist.id) == ("Daft Punk", "cover.jpg", 27)
    assert tracks == [{"id": 1}, {"id": 2}]
