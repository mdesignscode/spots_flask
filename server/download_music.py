#!/usr/bin/python3
"""Downloads a search"""

from typing import Dict, cast
from download_urls import playlist_downloader
from engine import storage
from flask import Blueprint, request, make_response
from json import loads
from models.get_spotify_track import Metadata
from models.youtube_to_spotify import ProcessYoutubeLink
from os import chdir


blueprint = Blueprint("download", __name__, url_prefix="/download")


@blueprint.route("/single", methods=["POST"])
def download_song():
    if request.method == "POST":
        from . import chdir_to_music

        root_dir = chdir_to_music()

        try:
            # Access json data
            raw_data = cast(Dict[str, str], request.json)
            # load json data
            json_data = loads(raw_data["metadata"])
        except:
            json_data = request.form

        # create a metadata object
        metadata = Metadata(
            json_data["title"],
            json_data["artist"],
            json_data["link"],
            json_data["cover"],
            json_data["tracknumber"],
            json_data["album"],
            json_data["lyrics"],
            json_data["release_date"],
        )

        youtube_url = metadata.link if "youtu" in metadata.link else ""

        youtube = ProcessYoutubeLink(youtube_url, metadata=metadata)

        try:
            youtube.download_title()

            storage.save()

            chdir(root_dir)

            return f"<p>Successfully downloaded <strong>{metadata.artist} - {metadata.title}</strong></p>"
        except Exception as e:
            return f"Failed to download: {e}"

    else:
        return "Only POST method allowed"


@blueprint.route("/artist", methods=["POST"])
@blueprint.route("/playlist", methods=["POST"])
def download_playlist():
    from . import chdir_to_music

    root_dir = chdir_to_music()

    json_dict = cast(Dict[str, str], request.json)
    json_data = json_dict["selected_songs"]
    playlist_name = json_dict["playlist_name"]

    selected_songs = [Metadata(**loads(song)) for song in json_data]

    exceptions = playlist_downloader(selected_songs, playlist_name)

    storage.save()

    chdir(root_dir)

    if len(exceptions):
        exceptions_response = "\n".join(
            [f"<p>{exception}</p>" for exception in exceptions]
        )
        response = f"""<div id='response'>
            <h2>The download process finished with the following results:</h2>
            {exceptions_response}
        </div>"""
        return make_response(response, 201)
    else:
        response = make_response(f"Successfully downloaded {playlist_name}", 201)
        return response
