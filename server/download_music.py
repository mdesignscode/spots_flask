#!/usr/bin/python3
"""Downloads a search"""

from typing import Dict, cast
from download_urls import playlist_downloader
from engine import storage
from flask import Blueprint, request, make_response, jsonify
from json import loads
from models.spotify_worker import Metadata
from models.youtube_to_spotify import ProcessYoutubeLink
from os import chdir
from tenacity import retry, stop_after_delay


blueprint = Blueprint("download", __name__, url_prefix="/download")

@retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/single", methods=["POST"])
def download_song():
    if request.method == "POST":
        from . import chdir_to_music

        root_dir = chdir_to_music()

        try:
            # Access json data
            json_data = cast(Dict[str, str], request.json)
        except Exception:
            json_data = request.form

        # Validate required fields
        required_fields = [
            "title", "artist", "link", "cover",
            "tracknumber", "album", "lyrics", "release_date"
        ]
        missing_fields = [field for field in required_fields if field not in json_data]
        if missing_fields:
            return jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # Create a metadata object
        metadata = Metadata(
            json_data.get("title"),
            json_data.get("artist"),
            json_data.get("link"),
            json_data.get("cover"),
            json_data.get("tracknumber"),
            json_data.get("album"),
            json_data.get("lyrics"),
            json_data.get("release_date"),
        )

        youtube_url = metadata.link if "youtu" in metadata.link else ""

        youtube = ProcessYoutubeLink(youtube_url, metadata=metadata)

        try:
            youtube.download_title()
            storage.save()
            chdir(root_dir)
            return jsonify({"message": "Successfully downloaded"}), 200
        except Exception as e:
            return jsonify({"message": f"Download failed: {str(e)}"}), 500
    else:
        return jsonify({"message": "Only POST method allowed"}), 405


# @retry(stop=stop_after_delay(max_delay=120))
@blueprint.route("/artist", methods=["POST"])
@blueprint.route("/playlist", methods=["POST"])
def download_playlist():
    query = request.args.get("artist")

    from . import chdir_to_music

    root_dir = chdir_to_music()

    json_dict = cast(Dict[str, str], request.json)
    json_data = json_dict["selected_songs"]
    playlist_name = json_dict["playlist_name"]

    selected_songs = [Metadata(**song) for song in json_data]

    exceptions = playlist_downloader(selected_songs, playlist_name, bool(query))

    storage.save()

    chdir(root_dir)

    return jsonify({ "message": exceptions if len(exceptions) else [f"Successfully downloaded {playlist_name}"] })

