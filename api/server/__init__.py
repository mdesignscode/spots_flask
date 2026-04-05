from flask import Flask, request, jsonify
from flask_cors import CORS
from logging import getLogger
from typing import Dict, Literal, TypedDict, cast

from spots_cli.bootstrap import Container
from spots_cli.clients import SecretsManager
from spots_cli.models import (
    SongNotFound,
    YouTubeQuotaExceeded,
    MediaResourceSingle,
    Metadata,
    YTVideoInfo,
    InvalidURL,
    PlaylistInfo,
    MediaResourcePlaylist,
)
from server.download_music import blueprint

app = Flask(__name__, static_url_path="/static")
app.register_blueprint(blueprint)
CORS(app)

bootstrapper = Container()

logger = getLogger(__name__)


class SingleMetadata(TypedDict):
    provider_metadata: Metadata
    youtube_metadata: YTVideoInfo


class PlaylistResponseInfo(TypedDict):
    name: str
    cover: str
    artist: str | None
    metadata: list[SingleMetadata]


class PlaylistResponse(TypedDict):
    playlist_info: PlaylistResponseInfo
    resource: Literal["playlist"]
    action: str


class ArtistResponse(TypedDict):
    name: str
    cover: str
    playlist_info: list[PlaylistResponseInfo]
    resource: Literal["playlist"]
    action: str


class SingleResponse(TypedDict):
    video_info: YTVideoInfo
    metadata: Metadata
    resource: Literal["single"]
    youtube_title: str
    action: str


@app.route("/get-user")
def get_user():
    if not bootstrapper.clients.spotify:
        return (
            jsonify(
                {
                    "error": "Spotify features unavailable. Sign in to use Spotify features."
                }
            ),
            401,
        )
    username = bootstrapper.clients.spotify.get_user()

    return jsonify({"username": username})


@app.route("/status")
def status():
    return jsonify({"message": "OK"})


@app.route("/transfer_likes", methods=["POST"])
def transfer_likes():
    try:
        bootstrapper.app.youtube_user_playlist.transfer_spotify_likes_to_yt()
    except YouTubeQuotaExceeded:
        return jsonify({"message": "Quota exceeded"})
    except SongNotFound:
        return jsonify({"message": "No Spotify likes"}), 500

    return "Added to likes"


@app.route("/user_playlist/<action>", methods=["POST"])
def user_playlist(action: str):
    # Access form data
    json_dict = cast(Dict[str, str], request.json)
    tracks = json_dict["tracks"]

    response = "\n".join(f"<p>{track[0]}</p>" for track in tracks)

    username = SecretsManager.read(key="username")
    response += f"\n<p>Removed from {username} playlist"

    bootstrapper.app.spotify_playlist_modify.modify_saved_tracks_playlist(
        action, ",".join([track[1] for track in tracks])
    )

    return "No songs removed" if not query else response


@app.route("/query/<action>", methods=["GET"])
def query(action: str):
    query = request.args.get("q")
    essentials_playlist = request.args.get("essentials_playlist")
    username = request.args.get("username")

    if not query:
        if not username:
            return jsonify({"error": "Search Query Missing"}), 400
        else:
            query = ""

    logger.info(f"Performing {action} on {query}...")

    match action:
        # ---- search for a title on spotify ---- #
        case "search":
            # search on spotify
            try:
                spotify_result = bootstrapper.domain.provider_search.search_track(query)
            except SongNotFound as e:
                spotify_result = None

            except Exception as e:
                # catch edge case for future handling
                logger.error(f"Spotify search error: {e}")
                return jsonify({"error": str(e)}), 503

            metadata = spotify_result

            # search on youtube
            search_title = metadata.full_title if metadata else query

            try:
                youtube_result = bootstrapper.domain.youtube_search.video_search(
                    query=search_title, is_general_search=True
                )
            except SongNotFound:
                return jsonify({"message": f"{search_title} not available"}), 500

            # find best match
            # cached result will be the only item in list
            if youtube_result.is_cached:
                best_match = youtube_result.result[0]
            else:
                best_match = None

                if not metadata:
                    best_match = youtube_result.result[0]

                else:
                    for result in youtube_result.result:
                        # clean uploader and title first
                        cleaned = bootstrapper.core.extractor.extract_artist_and_title(
                            video_info=result, metadata=metadata
                        )
                        result.full_title = cleaned

                        tracks_match = bootstrapper.core.matcher.match_tracks(
                            video_info=result, metadata=metadata
                        )

                        if tracks_match:
                            best_match = result
                            break

            if not best_match:
                return jsonify({"message": f"{search_title} not available"}), 500

            youtube_title = best_match.full_title
            if not metadata:
                metadata = bootstrapper.domain.youtube_metadata.get(best_match)

            search_response: SingleResponse = {
                "video_info": best_match,
                "metadata": metadata,
                "resource": "single",
                "youtube_title": youtube_title,
                "action": action,
            }

            bootstrapper.core.storage.new(
                query=youtube_title, result=best_match, query_type="youtube"
            )
            bootstrapper.core.storage.save()

            return jsonify(search_response)
        # ---- download url ----
        case "download":
            try:
                resolved_media = bootstrapper.app.resolver.resolve(url=query)
            except InvalidURL:
                return jsonify({"error": f"No results for {query}"}), 500

            match resolved_media.resource_type:
                # --- handle single ---
                case "single":
                    # handle single only
                    resolved_media = cast(MediaResourceSingle, resolved_media)
                    if not resolved_media.metadata or not resolved_media.video_info:
                        return jsonify({"error": f"No results for {query}"}), 500

                    download_response: SingleResponse = {
                        "video_info": resolved_media.video_info,
                        "metadata": resolved_media.metadata,
                        "resource": "single",
                        "youtube_title": resolved_media.video_info.full_title,
                        "action": action,
                    }

                    return jsonify(download_response)

                # ---- handle playlist ----
                case "playlist":
                    resolved_media = cast(MediaResourcePlaylist, resolved_media)

                    combined_metadata = zip(
                        resolved_media.playlist_info.provider_metadata,
                        resolved_media.playlist_info.youtube_metadata,
                    )
                    playlist_metadata: list[SingleMetadata] = []
                    for provider, youtube in combined_metadata:
                        single_metadata: SingleMetadata = {
                            "youtube_metadata": youtube,
                            "provider_metadata": provider,
                        }
                        playlist_metadata.append(single_metadata)

                    playlist_info: PlaylistResponseInfo = {
                        "metadata": playlist_metadata,
                        "name": resolved_media.playlist_info.name,
                        "cover": resolved_media.playlist_info.cover,
                        "artist": resolved_media.playlist_info.artist,
                    }

                    playlist_info = get_playlist_info(
                        playlist=resolved_media.playlist_info
                    )
                    playlist_response: PlaylistResponse = {
                        "action": action,
                        "resource": "playlist",
                        "playlist_info": playlist_info,
                    }
                    return jsonify(playlist_response)

        case "artist":
            artist_result = bootstrapper.app.spotify_playlist_compiler.artist_albums(
                artist=query, essentials_playlist=essentials_playlist
            )

            if not artist_result:
                return jsonify({"error": f"No results for {query}"}), 500

            all_playlist_info: list[PlaylistResponseInfo] = []
            for playlist in artist_result.playlist:
                playlist_info = get_playlist_info(playlist)
                all_playlist_info.append(playlist_info)

            artist_response: ArtistResponse = {
                "playlist_info": all_playlist_info,
                "resource": "playlist",
                "action": action,
                "name": artist_result.name,
                "cover": artist_result.cover,
            }

            return jsonify(artist_response)

        case "saved_tracks":
            try:
                saved_tracks = (
                    bootstrapper.app.spotify_playlist_compiler.user_saved_tracks()
                )
            except SongNotFound:
                return jsonify({"error": "No saved tracks found"}), 500

            playlist_info = get_playlist_info(saved_tracks)
            saved_playlist_response: PlaylistResponse = {
                "action": action,
                "resource": "playlist",
                "playlist_info": playlist_info,
            }

            return jsonify(saved_playlist_response)

        case _:
            return (
                jsonify(
                    {"error": "Only `Download` `Artist, or `Search` actions allowed"}
                ),
                400,
            )


def get_playlist_info(playlist: PlaylistInfo) -> PlaylistResponseInfo:
    playlist_metadata: list[SingleMetadata] = []
    for provider, youtube in zip(playlist.provider_metadata, playlist.youtube_metadata):
        playlist_metadata.append(
            {
                "provider_metadata": provider,
                "youtube_metadata": youtube,
            }
        )

    playlist_info: PlaylistResponseInfo = {
        "name": playlist.name,
        "cover": playlist.cover,
        "metadata": playlist_metadata,
        "artist": "",
    }
    return playlist_info
