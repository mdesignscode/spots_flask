"""Downloads a search"""

from typing import Dict, cast
from download_urls import playlist_downloader
from engine import storage
from flask import Blueprint, request, jsonify
from models.spotify_worker import Metadata, SpotifyWorker
from models.process_youtube_link import ProcessYoutubeLink
from models.errors import TitleExistsError
from os import getenv
from services.youtube_search_service import YoutubeSearchService
from tenacity import stop_after_delay
from engine.retry import retry


blueprint = Blueprint("download", __name__, url_prefix="/download")


@retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/saved", methods=["POST"])
def download_saved_tracks():
    username = getenv("username")
    if not username:
        return jsonify({"error": "No username"})

    spotify = SpotifyWorker()
    saved_tracks = spotify.user_saved_tracks()

    if not saved_tracks:
        return jsonify({"error": "No saved tracks found"})

    exceptions = playlist_downloader(saved_tracks, username)

    storage.save()

    return jsonify(
        {
            "message": (
                exceptions
                if len(exceptions)
                else [f"Successfully downloaded {username}"]
            )
        }
    )


@retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/single", methods=["POST"])
def download_song():
    if request.method == "POST":
        try:
            # Access json data
            json_data = cast(Dict[str, str], request.json)
        except Exception:
            json_data = request.form

        # Validate required fields
        required_fields = [
            "title",
            "artist",
            "link",
            "cover",
            "tracknumber",
            "album",
            "lyrics",
            "release_date",
        ]
        missing_fields = [field for field in required_fields if field not in json_data]
        if missing_fields:
            return (
                jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}),
                400,
            )

        # Create a metadata object
        metadata = Metadata(
            json_data.get("title"),
            json_data.get("artist"),
            json_data.get("link"),
            json_data.get("cover"),
            json_data.get("tracknumber"),
            json_data.get("album"),
            json_data.get("lyrics"),
            json_data.get("release_date"),
        )

        yt_searcher = YoutubeSearchService()
        search_title = f"{metadata.artist} - {metadata.title}"
        youtube_url = yt_searcher.search_best_match(metadata, search_title)

        youtube = ProcessYoutubeLink()

        try:
            youtube.ytdlp.download_youtube_video(youtube_url, metadata)
            storage.save()
            return jsonify({"message": "Successfully downloaded"}), 200
        except TitleExistsError as e:
            return jsonify({"message": f"Download failed: {str(e)}"}), 500
        except Exception as e:
            raise e
    else:
        return jsonify({"message": "Only POST method allowed"}), 405


@retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/artist", methods=["POST"])
@blueprint.route("/playlist", methods=["POST"])
def download_playlist():
    query = request.args.get("artist")

    json_dict = cast(Dict[str, str], request.json)
    json_data = json_dict["selected_songs"]
    playlist_name = json_dict["playlist_name"]

    selected_songs = [Metadata(**song) for song in json_data]

    exceptions = playlist_downloader(selected_songs, playlist_name, bool(query))

    storage.save()

    return jsonify(
        {
            "message": (
                exceptions
                if len(exceptions)
                else [f"Successfully downloaded {playlist_name}"]
            )
        }
    )

