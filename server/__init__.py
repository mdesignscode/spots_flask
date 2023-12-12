#!/usr/bin/python3
"""Spots Web App"""

from typing import Dict, List, Tuple, cast
from download_urls import convert_url, search_on_youtube
from flask import Flask, render_template, request, url_for
from models.metadata import Metadata
from server.download_music import blueprint
from flask import render_template, request
from models.spotify_worker import SpotifyWorker
from models.youtube_to_spotify import ProcessYoutubeLink
from os import chdir, getcwd, makedirs, chdir
from os.path import join, exists, basename


app = Flask(__name__, static_url_path="/static")
app.register_blueprint(blueprint)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/query/<action>")
async def query(action: str):
    root_dir = chdir_to_music()
    query = request.args.get("q")

    if not query:
        return "<h2>Search Query Missing</h2>"

    # search for a title on spotify
    if action == "search":
        spotify = SpotifyWorker()
        try:
            result = await spotify.search_track(query)
        except Exception as e:
            return str(e)

        if not result:
            return f"No results for {query}"

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

        return render_template(
            "query.html",
            data=metadata,
            size=youtube_result[2],
            resource="single",
            title=youtube_title,
            action=action,
            recommended_tracks=recommended_tracks,
        )

    elif action == "download":
        # process the url
        converter = await convert_url(query)

        if not converter:
            return f"<h2>No results for {query}</h2>"

        match converter[0]:
            # handle single
            case "single":
                results = cast(
                    Tuple[Metadata, List[Metadata] | None, int], converter[2]
                )

                # search for recommended tracks on youtube
                recommended_tracks = []
                if results[1]:
                    recommended_tracks = search_on_youtube(results[1])

                return render_template(
                    "query.html",
                    data=results[0].__dict__,
                    resource="single",
                    title=converter[1],
                    action=action,
                    recommended_tracks=recommended_tracks,
                    size=results[2],
                )

            # handle playlist
            case "playlist":
                return render_template(
                    "query.html",
                    playlist=converter[1],
                    data=converter[2],
                    resource="playlist",
                    title=converter[1],
                    action=action,
                )

    elif action == "artist":
        spotify = SpotifyWorker()
        result = spotify.artist_albums(query)

        if not result:
            return f"No results for {query}"

        albums = []
        # record to avoid duplicates
        table = {}

        for album in result[0]:
            playlist = []
            yt_list = search_on_youtube(album[0])
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

        return render_template(
            "query.html",
            data=result[1],
            resource="artist",
            albums=albums,
            action=action,
        )

    else:
        return "<h2>Only `Download` `Artist, or `Search` actions allowed</p>"


@app.route("/handle_query", methods=["POST"])
def handle_query():
    if request.method == "POST":
        # Access form data
        json_dict = cast(Dict[str, str], request.json)
        action = json_dict["action"]
        user_input = json_dict["user_input"]

        # Construct the redirect URL
        redirect_url = url_for("query", action=action, q=user_input)

        # Return a redirect response
        return redirect_url

    else:
        return "Only POST method allowed"


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
