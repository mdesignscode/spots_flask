#!/usr/bin/python3
"""Recursively adds user's downloaded songs to spots history file"""

from os import listdir, path, getcwd
from sys import argv
from mutagen.id3 import ID3
from mutagen.mp3 import MP3, HeaderNotFoundError


def update_history(file_path):
    """Update history file with song information"""
    try:
        song = MP3(file_path, ID3)
        artist = song.get("TPE1", "")
        artist = f"{artist} - " if artist else ""
        title = song.get("TIT2", "")
        song_name = f"{artist}{title}"
        if title:
            with open(history_file, "a", newline="") as history:
                history.write(f"{song_name}\n")
    except (HeaderNotFoundError, KeyError):
        pass


def process_directory(directory):
    """Process all MP3 files in a directory"""
    for item in listdir(directory):
        item_path = path.join(directory, item)
        if path.isdir(item_path):
            process_directory(item_path)  # Recursively process subdirectories
        elif item_path.lower().endswith(".mp3"):
            update_history(item_path)


if __name__ == "__main__":
    if len(argv) < 2:
        print("Usage: python add_to_history.py folder_path")
        exit(1)

    folder = argv[1]

    if path.exists(folder):
        print("Updating Spots downloads history...")
        spots_path = getcwd()
        history_file = f"{spots_path}/Music/.spots_download_history.txt"

        process_directory(folder)

        print("Spots downloads history updated!")
    else:
        print("Folder not found.")
