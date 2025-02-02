#!/usr/bin/python3
"""Spots Web App"""

from download_urls import convert_url, search_on_youtube, search_artist_on_yt
from engine import storage
from flask import Flask, request, url_for, jsonify
from flask_cors import CORS
from logging import error, info
from models import spotify_model
from models.errors import SongNotFound
from models.metadata import Metadata
from models.spotify_worker import SpotifyWorker
from models.youtube_to_spotify import ProcessYoutubeLink
from os import chdir, getcwd, getenv, makedirs, chdir
from os.path import join, exists, basename
from requests.exceptions import ConnectionError
from server.download_music import blueprint
from typing import Dict, List, Tuple, cast
from tenacity import retry, stop_after_delay, RetryError
from urllib3.exceptions import NameResolutionError


app = Flask(__name__, static_url_path="/static")
app.register_blueprint(blueprint)
CORS(app)

@retry(stop=stop_after_delay(max_delay=60))
@app.route("/get-user")
def home():
    username = spotify_model.get_user()

    return jsonify({ "username": username })


@retry(stop=stop_after_delay(max_delay=120))
@app.route("/user_playlist/<action>", methods=["POST"])
def user_playlist(action: str):
    if request.method != "POST":
        return "Only POST method allowed"

    # Access form data
    json_dict = cast(Dict[str, str], request.json)
    tracks = json_dict["tracks"]
    spotify = SpotifyWorker()

    response = "\n".join(f"<p>{track[0]}</p>" for track in tracks)

    response += f"\n<p>Removed from {getenv('username')} playlist"

    spotify.modify_saved_tracks_playlist(
        action, ",".join([track[1] for track in tracks])
    )

    return "No songs removed" if not query else response


# @retry(stop=stop_after_delay(max_delay=60))
@app.route("/query/<action>")
def query(action: str):
    root_dir = chdir_to_music()
    query = request.args.get("q")
    essentials_playlist = request.args.get("essentials_playlist")
    single_arg = request.args.get("single")
    single = single_arg == "true"
    username = request.args.get("username")

    if not query:
        if not username:
            return jsonify({ "message": "Search Query Missing" })
        else:
            query = ""

    info(f"Performing {action} on {query}...")

    # catch network error
    try:
        # validate token
        spotify_model.get_user()

        # search for a title on spotify
        match action:
            case "search":
                try:
                    result = spotify_model.search_track(query, single)
                    info(f"Spotify search: {result[0].title} by {result[0].artist}")

                except (SongNotFound, TypeError) as e:
                    return jsonify({ "message": str(e) })

                except Exception as e:
                    # catch edge case for future handling
                    error(f"Spotify search error: {e}")
                    raise e

                if not result:
                    return jsonify({ "message": f"No results for {query}" })

                metadata = result[0]

                # search for title on youtube
                youtube = ProcessYoutubeLink(metadata=metadata, search_title=query)
                youtube_result = youtube.get_title()
                youtube_title = f"{youtube_result[0]} - {youtube_result[1]}"

                # search for recommended tracks on youtube
                recommended_tracks = []
                if result[1]:
                    recommended_tracks = search_on_youtube(result[1])

                chdir(root_dir)

                return jsonify({
                    "data": metadata.__dict__,
                    "size": youtube_result[2],
                    "resource": "single",
                    "title": youtube_title,
                    "action": action,
                    "recommended_tracks": recommended_tracks,
                })

            case "download":
                # process the url
                converter = convert_url(query, single)

                if not converter:
                    return f"<h2>No results for {query}</h2>"

                match converter[0]:
                    # handle single
                    case "single":
                        # handle single only
                        metadata = cast(Metadata, converter[2])

                        # search for recommended tracks on youtube
                        recommended_tracks = []
                        #if not single:
                        #    recommended_tracks = search_on_youtube(results[1])

                        return jsonify({
                            "data": metadata.__dict__,
                            "resource": "single",
                            "title": converter[1],
                            "action": action,
                            "recommended_tracks": recommended_tracks,
                            "size": converter[3],
                        })

                    # handle playlist
                    case "playlist":
                        return jsonify({
                            "playlist": converter[1],
                            "data": converter[2],
                            "resource": "playlist",
                            "title": converter[1],
                            "action": action,
                        })

            case "artist":
                result = spotify_model.artist_albums(query, essentials_playlist)

                if not result:
                    return jsonify({ "message": f"No results for {query}" }), 500

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

                return jsonify({
                    "data": result[1],
                    "resource": "artist",
                    "albums": albums,
                    "action": action,
                })

            case "saved_tracks":
                saved_tracks = spotify_model.user_saved_tracks()
                storage.save()

                if saved_tracks:
                    cover = url_for("static", filename="avatar.jpg")
                    data = {"cover": cover, "name": username}

                    return jsonify({
                        "data": data,
                        "resource": "saved_tracks",
                        "playlist": search_on_youtube(saved_tracks),
                        "action": action,
                    })

                else:
                    return jsonify({ "error": "No saved tracks found" }), 500

            case _:
                return jsonify({
                    "error": "Only `Download` `Artist, or `Search` actions allowed"
                }), 400
    except (RetryError, ConnectionError, NameResolutionError) as e:
        storage.save()
        return jsonify({ "error": str(e) }), 500


def chdir_to_music() -> str:
    # Get the current working directory
    current_dir = getcwd()

    # Check if the current directory is 'spots'
    if basename(current_dir) == "spots_flask":
        # Create a folder named 'Music' if it doesn't exist
        music_folder = join(current_dir, "Music")
        if not exists(music_folder):
            makedirs(music_folder)

        # Change to the 'Music' folder
        chdir(music_folder)

    return current_dir

