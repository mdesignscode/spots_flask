from bootstrap.container import Container
from clients.secrets_manager import SecretsManager
from engine.persistence_model import storage
from engine.retry import retry
from flask import Flask, request, url_for, jsonify
from flask_cors import CORS
from logging import error, info
from models.errors import SongNotFound, YouTubeQuotaExceeded
from models.media_resource import MediaResourceSingle
from models.metadata import Metadata
from models.playlist_info import PlaylistInfo
from models.yt_video_info import YTVideoInfo
from requests.models import InvalidURL
from server.download_music import blueprint
from tenacity import stop_after_delay
from typing import Dict, Literal, TypedDict, cast


app = Flask(__name__, static_url_path="/static")
app.register_blueprint(blueprint)
CORS(app)

bootstrapper = Container()
bootstrapper.setup_container()


class PlaylistResponse(TypedDict):
    playlist_info: PlaylistInfo
    resource: Literal["playlist"]
    action: str


class ArtistResponse(TypedDict):
    name: str
    cover: str
    playlist_info: list[PlaylistInfo]
    resource: Literal["playlist"]
    action: str


class SingleResponse(TypedDict):
    video_info: YTVideoInfo
    metadata: Metadata
    resource: Literal["single"]
    youtube_title: str
    action: str


@retry(stop=stop_after_delay(max_delay=30))
@app.route("/get-user")
def get_user():
    username = bootstrapper.clients.spotify.get_user()

    return jsonify({"username": username})


@app.route("/status")
def status():
    return jsonify({"message": "OK"})


@retry(stop=stop_after_delay(max_delay=120))
@app.route("/transfer_likes", methods=["POST"])
def transfer_likes():
    try:
        bootstrapper.app.youtube_user_playlist.transfer_spotify_likes_to_yt()
    except YouTubeQuotaExceeded:
        return jsonify({"message": "Quota exceeded"})
    except SongNotFound:
        return jsonify({"message": "No Spotify likes"}), 500

    return "Added to likes"


@retry(stop=stop_after_delay(max_delay=120))
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


# @retry(stop=stop_after_delay(max_delay=60))
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

    info(f"Performing {action} on {query}...")

    match action:
        # ---- search for a title on spotify ---- #
        case "search":
            # search on spotify
            try:
                spotify_result = bootstrapper.domain.spotify_search.search_track(query)
            except SongNotFound as e:
                return jsonify({"error": str(e)}), 500

            except Exception as e:
                # catch edge case for future handling
                error(f"Spotify search error: {e}")
                return jsonify({"error": str(e)}), 503

            metadata = spotify_result

            # search on youtube
            spotify_title = metadata.full_title

            try:
                youtube_result = bootstrapper.domain.youtube_search.video_search(
                    query=spotify_title, is_general_search=True
                )
            except SongNotFound:
                return jsonify({"message": f"{spotify_title} not available"}), 500

            # find best match
            # cached result will be the only item in list
            if youtube_result.is_cached:
                best_match = youtube_result.result[0]
            else:
                best_match = None

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
                return jsonify({"message": f"{spotify_title} not available"}), 500

            youtube_title = best_match.full_title

            search_response: SingleResponse = {
                "video_info": best_match,
                "metadata": metadata,
                "resource": "single",
                "youtube_title": youtube_title,
                "action": action,
            }

            storage.new(query=youtube_title, result=best_match, query_type="ytdl")
            storage.save()

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
                    playlist_response: PlaylistResponse = {
                        "action": action,
                        "resource": "playlist",
                        "playlist_info": resolved_media.playlist_info,
                    }
                    return jsonify(playlist_response)

        case "artist":
            artist_result = bootstrapper.app.spotify_playlist_compiler.artist_albums(
                artist=query, essentials_playlist=essentials_playlist
            )

            if not artist_result:
                return jsonify({"error": f"No results for {query}"}), 500

            artist_response: ArtistResponse = {
                "playlist_info": artist_result.playlist,
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

            playlist_response = {
                "action": action,
                "resource": "playlist",
                "playlist_info": saved_tracks,
            }

            return jsonify(playlist_response)

        case _:
            return (
                jsonify(
                    {"error": "Only `Download` `Artist, or `Search` actions allowed"}
                ),
                400,
            )

