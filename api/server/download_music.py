from logging import getLogger
from typing import Any, cast

from flask import Blueprint, request, jsonify

from spots_cli.bootstrap import Container
from spots_cli.models import Metadata, TitleExistsError, YTVideoInfo

blueprint = Blueprint("download", __name__, url_prefix="/download")

bootstrapper = Container()

logger = getLogger(__name__)

METADATA_FIELDS = ["title", "artist", "link", "artist_id"]
VIDEO_INFO_FIELDS = ["id", "title", "uploader", "audio_ext", "filesize"]


def _get_json_payload(req) -> dict[str, Any]:
    """Safely extracts a dict payload from the request, whether it's JSON
    or form-encoded. Never returns None."""
    try:
        data = cast(dict[str, Any], req.get_json(silent=True))
    except Exception:
        data = None
    if isinstance(data, dict):
        return data
    return req.form.to_dict()


def _parse_song_payload(data: dict[str, Any]) -> tuple[Metadata, YTVideoInfo]:
    """Builds Metadata + YTVideoInfo from a flat song payload.

    Raises:
        ValueError: listing any missing required fields.
    """
    missing_metadata = [
        field for field in METADATA_FIELDS if field not in data]
    missing_video_fields = [
        field for field in VIDEO_INFO_FIELDS if field not in data
    ]
    missing_fields = missing_metadata + missing_video_fields
    if missing_fields:
        raise ValueError(f"Missing fields: {', '.join(missing_fields)}")

    metadata = Metadata(
        title=data["title"],
        artist=data["artist"],
        link=data["link"],
        cover=data.get("cover"),
        tracknumber=data.get("tracknumber"),
        album=data.get("album"),
        lyrics=data.get("lyrics"),
        release_date=data.get("release_date"),
        artist_id=data["artist_id"],
    )

    video_info = YTVideoInfo(
        id=data["id"],
        title=data["title"],
        uploader=data["uploader"],
        audio_ext=data["audio_ext"],
        filesize=int(data["filesize"]),
    )

    return metadata, video_info


@blueprint.route("/single", methods=["POST"])
def download_song():
    json_data = _get_json_payload(request)

    try:
        metadata, video_info = _parse_song_payload(json_data)
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except (TypeError, KeyError):
        return jsonify({"message": "Invalid request body"}), 400

    try:
        bootstrapper.app.downloader.download(
            video_info=video_info, metadata=metadata)
        return jsonify({"message": "Successfully downloaded"}), 200
    except TitleExistsError as e:
        # Not a server error: the client asked to download something that's
        # already been downloaded.
        return jsonify({"message": f"Download failed: {str(e)}"}), 409
    except Exception as e:
        logger.error(f"Download failed for {video_info.id}: {e}")
        return jsonify({"message": f"Download failed: {str(e)}"}), 500


@blueprint.route("/artist", methods=["POST"])
@blueprint.route("/playlist", methods=["POST"])
def download_playlist():
    json_dict = cast(dict[str, Any], request.get_json(silent=True)) or {}

    playlist_name = json_dict.get("playlist_name", "playlist")
    songs_data = json_dict.get("selected_songs")

    if not songs_data:
        return jsonify({"message": "No songs provided in 'selected_songs'"}), 400

    errors: list[str] = []
    successes = 0

    for index, song in enumerate(songs_data):
        try:
            metadata, video_info = _parse_song_payload(song)
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Song {index + 1}: {str(e)}")
            continue

        try:
            bootstrapper.app.downloader.download(
                video_info=video_info, metadata=metadata
            )
            successes += 1
        except TitleExistsError as e:
            errors.append(str(e))
        except Exception as e:
            logger.error(f"Download failed for {video_info.id}: {e}")
            errors.append(f"{metadata.full_title}: {str(e)}")

    # persist the search/metadata cache accumulated during this batch
    bootstrapper.core.storage.save()

    status_code = 200 if successes else 500
    message = [
        f"Downloaded {successes}/{len(songs_data)} songs from {playlist_name}"
    ] + errors

    return jsonify({"message": message}), status_code
