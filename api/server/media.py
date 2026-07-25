from dataclasses import asdict
from logging import getLogger

from flask import Blueprint, request, jsonify

from spots_cli.bootstrap import Container
from spots_cli.models import (
    InvalidURL,
    SongNotFound,
    SpotifyUnavailableError,
    YouTubeQuotaExceeded,
    YouTubeUnavailableError,
)

blueprint = Blueprint("media", __name__, url_prefix="/media")

bootstrapper = Container()

logger = getLogger(__name__)


@blueprint.route("/resolve", methods=["POST"])
def resolve():
    """Resolves a Spotify or YouTube URL into displayable metadata.

    Accepts:
        {"url": "<spotify track/playlist/album url, or youtube video/playlist url>"}

    Returns a MediaResourceSingle (a single matched song: provider metadata +
    matching YTVideoInfo, ready to hand to /download/single) or a
    MediaResourcePlaylist (a PlaylistInfo with parallel provider_metadata and
    youtube_metadata lists, ready to hand to /download/playlist).
    """
    json_data = request.get_json(silent=True) or {}
    url = json_data.get("url")

    if not url:
        return jsonify({"message": "Missing 'url'"}), 400

    try:
        resource = bootstrapper.app.resolver.resolve(url=url)
    except InvalidURL as e:
        return jsonify({"message": str(e)}), 400
    except SongNotFound as e:
        return jsonify({"message": str(e)}), 404
    except (SpotifyUnavailableError, YouTubeUnavailableError, YouTubeQuotaExceeded) as e:
        logger.error(f"Provider unavailable resolving {url}: {e}")
        return jsonify({"message": str(e)}), 503
    except Exception as e:
        logger.error(f"Failed to resolve {url}: {e}")
        return jsonify({"message": "Failed to resolve URL"}), 500

    return jsonify(asdict(resource)), 200


@blueprint.route("/search", methods=["GET"])
def search():
    """Plain-text YouTube search (no provider/metadata matching).

    Useful for the video-download flow, which only needs a YTVideoInfo (not
    matched Metadata) to call /download/video/resolutions and /download/video.

    Query params:
        q (str, required): search terms.
    """
    query = request.args.get("q")

    if not query:
        return jsonify({"message": "Missing query parameter 'q'"}), 400

    try:
        search_response = bootstrapper.domain.youtube_search.video_search(
            query=query, is_general_search=True
        )
    except SongNotFound:
        return jsonify({"results": [], "is_cached": False}), 200
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return jsonify({"message": "Search failed"}), 502

    return (
        jsonify(
            {
                "results": [asdict(video) for video in search_response.result],
                "is_cached": search_response.is_cached,
            }
        ),
        200,
    )
