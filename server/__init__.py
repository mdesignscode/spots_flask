"""Spots Web App"""

from download_urls import convert_url, search_on_youtube, search_artist_on_yt
from flask import Flask, request, url_for, jsonify
from flask_cors import CORS
from logging import error, info
from models.errors import SongNotFound
from models.metadata import Metadata
from models.process_youtube_link import ProcessYoutubeLink
from os import getenv
from requests.exceptions import ConnectionError
from server.download_music import blueprint
from services.youtube_search_service import YoutubeSearchService
from typing import Dict, cast
from tenacity import stop_after_delay
from engine.retry import retry
from urllib3.exceptions import NameResolutionError


app = Flask(__name__, static_url_path="/static")
app.register_blueprint(blueprint)
CORS(app)

@app.route("/update-yt-likes")
def update_yt_likes():
    from engine import storage
    from json import load, dumps
    from models.spotify_worker import SpotifyWorker

    sp = SpotifyWorker()
    favs = sp.user_saved_tracks()
    print(favs)

    # def open_file(path = "./Music/.metadata.json"):
    #     with open(path, "r") as f:
    #         return load(f)
    #
    # def process_ids(ids):
    #     from services.youtube_search_service import YoutubeSearchService
    #     p_len = len(ids)
    #
    #     searcher = YoutubeSearchService()
    #     yt_titles = []
    #
    #     for index, id in enumerate(ids):
    #         print(f"**Processing id {index + 1}/{p_len}")
    #         watch_url = f"https://www.youtube.com/watch?v={id}"
    #         if storage.get(watch_url, "yt_likes"):
    #             print("Already processed")
    #             continue
    #
    #         try:
    #             metadata = searcher.process_youtube_url(watch_url)
    #         except SongNotFound:
    #             continue
    #
    #         title = f"{metadata.artist} - {metadata.title}"
    #         yt_titles.append(title)
    #
    #         storage.new(title, query_type="yt_likes")
    #         storage.new(watch_url, query_type="yt_likes")
    #         if (index % 10 == 0) or (index == (p_len - 1)):
    #             storage.save()
    #
    #     return yt_titles
    #
    # def main():
    #     ids = open_file("liked_songs.json")
    #     process_ids(ids)
    #
    # main()
    return "updated likes"

@retry(stop=stop_after_delay(max_delay=30))
@app.route("/get-user")
def home():
    from models import spotify_client

    username = spotify_client.get_user()

    return jsonify({"username": username})


@app.route("/status")
def status():
    return jsonify({"message": "OK"})


@retry(stop=stop_after_delay(max_delay=120))
@app.route("/transfer_likes", methods=["POST"])
def transfer_likes():
    youtube = ProcessYoutubeLink()
    try:
        youtube.transfer_spotify_likes_to_yt()
    except SongNotFound:
        return jsonify({"message": "No Spotify likes"})

    return "Added to likes"


@retry(stop=stop_after_delay(max_delay=120))
@app.route("/user_playlist/<action>", methods=["POST"])
def user_playlist(action: str):
    from models import spotify_client

    # Access form data
    json_dict = cast(Dict[str, str], request.json)
    tracks = json_dict["tracks"]

    response = "\n".join(f"<p>{track[0]}</p>" for track in tracks)

    response += f"\n<p>Removed from {getenv('username')} playlist"

    spotify_client.modify_saved_tracks_playlist(
        action, ",".join([track[1] for track in tracks])
    )

    return "No songs removed" if not query else response


# @retry(stop=stop_after_delay(max_delay=60))
@app.route("/query/<action>", methods=["GET"])
def query(action: str):
    from models import spotify_client
    from engine import storage

    query = request.args.get("q")
    essentials_playlist = request.args.get("essentials_playlist")
    single_arg = request.args.get("single")
    single = single_arg == "true"
    username = request.args.get("username")

    if not query:
        if not username:
            return jsonify({"error": "Search Query Missing"}), 400
        else:
            query = ""

    info(f"Performing {action} on {query}...")

    # catch network error
    try:
        # validate token
        spotify_client.get_user()

        match action:
            # ---- search for a title on spotify ---- #
            case "search":
                try:
                    result = spotify_client.search_track(query, single)
                    if not result:
                        return jsonify({"message": "No search results"})
                    info(f"Spotify search: {result[0].title} by {result[0].artist}")

                except SongNotFound as e:
                    return jsonify({"error": str(e)})

                except Exception as e:
                    # catch edge case for future handling
                    error(f"Spotify search error: {e}")
                    raise e

                if not result:
                    return jsonify({"error": f"No results for {query}"})

                metadata = result[0]

                # search for title on youtube
                youtube = YoutubeSearchService()
                artist, title, filesize = youtube.process_spotify_title(metadata)
                youtube_title = f"{artist} - {title}"

                # search for recommended tracks on youtube
                recommended_tracks = []
                if result[1]:
                    recommended_tracks = search_on_youtube(result[1])

                storage.save()

                return jsonify(
                    {
                        "data": metadata.__dict__,
                        "size": filesize,
                        "resource": "single",
                        "title": youtube_title,
                        "action": action,
                        "recommended_tracks": recommended_tracks,
                    }
                )
            # ---- download url ----
            case "download":
                # process the url
                converter = convert_url(query, single)

                if not converter:
                    return jsonify({"error": f"No results for {query}"}), 500

                match converter["resource_type"]:
                    # --- handle single ---
                    case "single":
                        # handle single only
                        metadata = cast(Metadata, converter["metadata"]["single"])

                        # TODO: search for recommended tracks on youtube
                        recommended_tracks = []
                        # if not single:
                        #    recommended_tracks = search_on_youtube(results[1])

                        return jsonify(
                            {
                                "data": metadata.__dict__,
                                "resource": "single",
                                "title": converter["youtube_title"],
                                "action": action,
                                "recommended_tracks": recommended_tracks,
                                "size": converter["filesize"],
                            }
                        )

                    # ---- handle playlist ----
                    case "playlist":
                        playlist_info = converter["playlist_info"]
                        album_data = playlist_info["album_data"]
                        title = album_data["name"]
                        return jsonify(
                            {
                                "playlist": playlist_info["playlist"],
                                "data": album_data,
                                "resource": "playlist",
                                "title": title,
                                "action": action,
                            }
                        )

            case "artist":
                result = spotify_client.artist_albums(query, essentials_playlist)

                if not result:
                    return jsonify({"error": f"No results for {query}"}), 500

                artist_name = result[1]["name"]
                artist_cover = result[1]["cover"]

                albums = []

                # search for artist on YT
                yt_playlist = search_artist_on_yt(artist_name, artist_cover)

                # record to avoid duplicates
                table = {}

                # combine scraped playlist and youtube search
                scraped_playlist = result[0][-1]
                artist_playlist = scraped_playlist[0] + yt_playlist
                artist_playlist_details = scraped_playlist[1]

                # add combined playlist to albums list
                all_albums = result[0][:-1]
                all_albums.append((artist_playlist, artist_playlist_details))

                for album in all_albums:
                    playlist = []
                    spotify_playlist = album[0]
                    yt_list = search_on_youtube(spotify_playlist)
                    for yt_result in yt_list:
                        yt_title = yt_result[0]

                        # see if song has been recorded
                        in_table = table.get(yt_title)

                        if not in_table:
                            table[yt_title] = True

                            playlist.append(yt_result)

                    albums.append({"album": album[1], "playlist": playlist})

                # filter out albums with no songs
                albums = list(filter(lambda x: len(x["playlist"]), albums))

                return jsonify(
                    {
                        "data": result[1],
                        "resource": "artist",
                        "albums": albums,
                        "action": action,
                    }
                )

            case "saved_tracks":
                saved_tracks = spotify_client.user_saved_tracks()
                storage.save()

                if saved_tracks:
                    cover = url_for("static", filename="avatar.jpg")
                    data = {"cover": cover, "name": username}

                    return jsonify(
                        {
                            "data": data,
                            "resource": "saved_tracks",
                            "playlist": search_on_youtube(saved_tracks),
                            "action": action,
                        }
                    )

                else:
                    return jsonify({"error": "No saved tracks found"}), 500

            case _:
                return (
                    jsonify(
                        {
                            "error": "Only `Download` `Artist, or `Search` actions allowed"
                        }
                    ),
                    400,
                )
    except (ConnectionError, NameResolutionError) as e:
        storage.save()
        return jsonify({"error": str(e)}), 500

