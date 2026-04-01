from logging import getLogger
from spots.bootstrap import Container
from flask import Blueprint, request, jsonify
from typing import Any, cast

from spots.clients import SecretsManager
from spots.models import Metadata, SongNotFound, TitleExistsError, YTVideoInfo


blueprint = Blueprint("download", __name__, url_prefix="/download")

bootstrapper = Container()

logger = getLogger(__name__)

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
        zip(saved_tracks.provider_metadata, saved_tracks.youtube_metadata)
    ):
        logger.info(f"Downloading track {index + 1}/{len(saved_tracks.provider_metadata)}")

        video_info = track[1]
        metadata = track[0]

        try:
            bootstrapper.app.downloader.download(
                video_info=video_info, metadata=metadata
            )
        except SongNotFound as e:
            exceptions.append(str(e))

    bootstrapper.core.storage.save()

    return jsonify(
        {
            "message": (
                exceptions
                if len(exceptions)
                else [f"Successfully downloaded {username}"]
            )
        }
    )


@blueprint.route("/single", methods=["POST"])
def download_song():
    try:
        # Access json data
        json_data = cast(dict[str, Any], request.json)
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
        title=json_data["title"],
        artist=json_data["artist"],
        link=json_data["link"],
        cover=json_data.get("cover"),
        tracknumber=json_data.get("tracknumber"),
        album=json_data.get("album"),
        lyrics=json_data.get("lyrics"),
        release_date=json_data.get("release_date"),
        artist_id=json_data["artist_id"],
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

# NOTE: in progress
@blueprint.route("/artist", methods=["POST"])
@blueprint.route("/playlist", methods=["POST"])
def download_playlist():
    query = request.args.get("artist")

    json_dict = cast(dict[str, str], request.json)
    print(json_dict)
    raise Exception("Okay now")
    json_data = cast(list[dict[str, Any]], json_dict["selected_songs"])
    playlist_name = json_dict["playlist_name"]

    selected_songs = [Metadata(
        title=song["title"],
        artist=song["artist"],
        link=song["link"],
        cover=song.get("cover"),
        tracknumber=song.get("tracknumber"),
        album=song.get("album"),
        lyrics=song.get("lyrics"),
        release_date=song.get("release_date"),
        artist_id=song["artist_id"],
    ) for song in json_data]

    for song in selected_songs:
        bootstrapper.app.downloader.download()

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

