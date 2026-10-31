from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any, cast

from flask import Blueprint, request, jsonify

from spots_cli.bootstrap import Container
from spots_cli.models import (
    ResolutionUnavailable,
    SongNotFound,
    VideoResolution,
    YTVideoInfo,
)

blueprint = Blueprint("download_video", __name__, url_prefix="/download/video")

bootstrapper = Container()

logger = getLogger(__name__)

VIDEO_INFO_FIELDS = ["id", "title", "uploader", "audio_ext", "filesize"]
RESOLUTION_FIELDS = ["format_id", "height", "ext", "vcodec", "acodec"]


def _get_json_payload(req) -> dict[str, Any]:
    """Safely extracts a dict payload from the request, whether it's JSON
    or form-encoded. Never returns None."""
    data = cast(dict[str, Any] | None, req.get_json(silent=True))
    if isinstance(data, dict):
        return data
    return req.form.to_dict()


def _build_video_info(data: dict[str, Any]) -> YTVideoInfo:
    """Builds a YTVideoInfo from a flat payload.

    Raises:
        ValueError: listing any missing required fields.
    """
    missing = [field for field in VIDEO_INFO_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    return YTVideoInfo(
        id=data["id"],
        title=data["title"],
        uploader=data["uploader"],
        audio_ext=data["audio_ext"],
        filesize=int(data["filesize"]),
    )


def _serialize_resolution(resolution: VideoResolution) -> dict[str, Any]:
    return {
        "format_id": resolution.format_id,
        "height": resolution.height,
        "ext": resolution.ext,
        "vcodec": resolution.vcodec,
        "acodec": resolution.acodec,
        "fps": resolution.fps,
        "filesize_mb": resolution.filesize_mb,
    }


def _build_resolution(data: dict[str, Any]) -> VideoResolution:
    """Builds a VideoResolution from a payload (as returned by /resolutions).

    Raises:
        ValueError: listing any missing required fields.
    """
    missing = [field for field in RESOLUTION_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Missing resolution fields: {', '.join(missing)}")

    return VideoResolution(
        format_id=data["format_id"],
        height=data["height"],
        ext=data["ext"],
        vcodec=data["vcodec"],
        acodec=data["acodec"],
        fps=data.get("fps"),
        filesize_mb=data.get("filesize_mb"),
    )


@blueprint.route("/resolutions", methods=["POST"])
def get_resolutions():
    """Returns all available download resolutions for a YouTube video.

    Expects a YTVideoInfo-shaped payload (id, title, uploader, audio_ext,
    filesize). Responds with a dict mapping resolution label (e.g. "1080p")
    to its format details, matching Downloader.get_available_resolutions().
    """
    json_data = _get_json_payload(request)

    try:
        video_info = _build_video_info(json_data)
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"message": str(e)}), 400

    try:
        resolutions = bootstrapper.app.downloader.get_available_resolutions(
            video_info=video_info
        )
    except Exception as e:
        logger.error(f"Failed to fetch resolutions for {video_info.id}: {e}")
        return jsonify({"message": "Failed to fetch available resolutions"}), 502

    return (
        jsonify(
            {
                label: _serialize_resolution(resolution)
                for label, resolution in resolutions.items()
            }
        ),
        200,
    )


def _find_video(query: str) -> YTVideoInfo:
    """The video a url points to, or the top YouTube result for search terms.

    Raises:
        SongNotFound: nothing matched.
    """
    is_url = query.startswith(("http://", "https://"))
    search = bootstrapper.domain.youtube_search.video_search(
        query=query, is_general_search=not is_url
    )
    return search.result if is_url else search.result[0]


@blueprint.route("", methods=["POST"])
def download_video():
    """Downloads a YouTube video as mp4.

    The video is either a YTVideoInfo-shaped payload (id, title, uploader,
    audio_ext, filesize) or a "query": a YouTube url or search terms, whose
    top result is used.

    "resolution" is optional: one of the objects returned by /resolutions, a
    label such as "720p", or omitted for the highest available. An optional
    "directory_path" picks a sub-folder of the downloads folder.

    Responds with the downloaded file's path.
    """
    json_data = _get_json_payload(request)

    query = json_data.get("query")
    if query is not None and not (isinstance(query, str) and query.strip()):
        return jsonify({"message": "'query' must be a non-empty string"}), 400

    resolution_data = json_data.get("resolution")
    resolution: VideoResolution | str | None
    if isinstance(resolution_data, dict):
        try:
            resolution = _build_resolution(resolution_data)
        except (ValueError, TypeError, KeyError) as e:
            return jsonify({"message": str(e)}), 400
    elif resolution_data is None or isinstance(resolution_data, str):
        resolution = resolution_data
    else:
        return jsonify({"message": "'resolution' must be an object or a label like '720p'"}), 400

    directory_path = json_data.get("directory_path", "")
    if not isinstance(directory_path, str) or Path(directory_path).is_absolute() or ".." in Path(directory_path).parts:
        return jsonify({"message": "'directory_path' must be a relative sub-folder"}), 400

    try:
        video_info = _find_video(query.strip()) if query else _build_video_info(json_data)
    except SongNotFound as e:
        return jsonify({"message": str(e)}), 404
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.error(f"Video search failed for '{query}': {e}")
        return jsonify({"message": "Search failed"}), 502

    try:
        path = bootstrapper.app.downloader.download_video(
            video_info=video_info,
            resolution=resolution,
            directory_path=directory_path,
        )
    except ResolutionUnavailable as e:
        return jsonify({"message": str(e), "available": e.available}), 400
    except Exception as e:
        logger.error(f"Video download failed for {video_info.id}: {e}")
        return jsonify({"message": f"Download failed: {str(e)}"}), 500

    return jsonify({"message": "Successfully downloaded", "file": path}), 200
