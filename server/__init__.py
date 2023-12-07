#!/usr/bin/python3
"""Spots Web App"""

from typing import Dict, cast
from download_urls import convert_url
from flask import Flask, render_template, request, redirect, url_for
from json import dumps
from models.errors import SongNotFound
from models.metadata import Metadata
from server.download_music import blueprint
from flask import render_template, request
from models.get_spotify_track import GetSpotifyTrack
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
        spotify = GetSpotifyTrack()
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
            for result in result[1]:
                youtube = ProcessYoutubeLink(metadata=result, search_title=query)
                title = youtube.get_title()
                yt_title = f"{title[0]} - {title[1]}"
                recommended_tracks.append((yt_title, result.__dict__, title[2]))

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
        converter = convert_url(query)

        if not converter:
            return f"<h2>No results for {query}</h2>"

        match converter[0]:
            # handle single
            case "single":
                return render_template(
                    "query.html",
                    data=converter[2],
                    resource="single",
                    title=converter[1],
                    action=action,
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
        spotify = GetSpotifyTrack()
        result = spotify.artist_albums(query)

        if not result:
            return f"No results for {query}"

        albums = []
        # record to avoid duplicates
        table = {}

        for album in result[0]:
            playlist = []
            for metadata in album[0]:
                try:
                    # search for spotify track on youtube
                    youtube = ProcessYoutubeLink(metadata=metadata)
                    youtube_result = youtube.get_title()
                    yt_title = f"{youtube_result[0]} - {youtube_result[1]}"

                    # see if song has been recorded
                    in_table = table.get(yt_title)

                    if not in_table:
                        table[yt_title] = True

                        playlist.append(
                            (yt_title, dumps(metadata.__dict__), youtube_result[2])
                        )

                except SongNotFound:
                    pass
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
        return redirect(redirect_url)

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
