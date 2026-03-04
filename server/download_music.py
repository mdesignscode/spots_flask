from bootstrap.container import Container
from logging import info
from clients.secrets_manager import SecretsManager
from engine.retry import retry
from engine.persistence_model import storage
from flask import Blueprint, request, jsonify
from models.metadata import Metadata
from models.errors import SongNotFound, TitleExistsError
from models.yt_video_info import YTVideoInfo
from tenacity import stop_after_delay
from typing import Any, Dict, cast


blueprint = Blueprint("download", __name__, url_prefix="/download")


bootstrapper = Container()
bootstrapper.setup_container()


@retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/saved", methods=["POST"])
def download_saved_tracks():
    username = SecretsManager.read(key="username")
    if not username:
        return jsonify({"error": "No username"})

    saved_tracks = bootstrapper.app.spotify_playlist_compiler.user_saved_tracks()

    if not saved_tracks:
        return jsonify({"error": "No saved tracks found"})

    exceptions = []

    for index, track in enumerate(
        zip(saved_tracks.spotify_metadata, saved_tracks.youtube_metadata)
    ):
        info(f"Downloading track {index + 1}/{len(saved_tracks.spotify_metadata)}")

        video_info = track[1]
        metadata = track[0]

        try:
            bootstrapper.app.downloader.download(
                video_info=video_info, metadata=metadata
            )
        except SongNotFound as e:
            exceptions.append(str(e))

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
    try:
        # Access json data
        json_data = cast(Dict[str, Any], request.json)
    except Exception:
        json_data = request.form.to_dict()

    # -------- Metadata validation --------
    missing_metadata = [
        field for field in ["title", "artist", "link"] if field not in json_data
    ]

    # -------- YTVideoInfo validation --------
    video_fields = [
        "id",
        "title",
        "uploader",
        "audio_ext",
        "filesize",
    ]

    missing_video_fields = [field for field in video_fields if field not in json_data]

    missing_fields = missing_metadata + missing_video_fields
    if missing_fields:
        return (
            jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}),
            400,
        )

    # -------- Create Metadata --------
    metadata = Metadata(
        json_data["title"],
        json_data["artist"],
        json_data["link"],
        json_data.get("cover"),
        json_data.get("tracknumber"),
        json_data.get("album"),
        json_data.get("lyrics"),
        json_data.get("release_date"),
    )

    # -------- Create YTVideoInfo --------
    video_info = YTVideoInfo(
        id=json_data["id"],
        title=json_data["title"],
        uploader=json_data["uploader"],
        audio_ext=json_data["audio_ext"],
        filesize=int(json_data["filesize"]),
    )

    try:
        bootstrapper.app.downloader.download(video_info=video_info, metadata=metadata)
        return jsonify({"message": "Successfully downloaded"}), 200
    except TitleExistsError as e:
        return jsonify({"message": f"Download failed: {str(e)}"}), 500
    except Exception as e:
        raise e


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

