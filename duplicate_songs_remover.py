#!/usr/bin/python3
"""Removes all duplicate mp3 files"""

from os import listdir, path, getcwd, remove
from sys import argv
from mutagen.id3 import ID3
from mutagen.mp3 import MP3, HeaderNotFoundError


original_songs = {}

i = 0


def process_song(file_path):
    """Removes a song if it is a duplicate"""
    try:
        song = MP3(file_path, ID3)
        artist = song.get("TPE1", "")
        artist = f"{artist} - " if artist else ""
        title = song.get("TIT2", "")
        song_name = f"{artist}{title}"

        original = original_songs.get(song_name)
        if original:
            remove(file_path)
        else:
            original_songs[song_name] = file_path
    except (HeaderNotFoundError, KeyError):
        pass


def process_directory(directory):
    """Process all MP3 files in a directory"""
    contents = listdir(directory)
    contents.sort(reverse=True)

    for item in contents:
        print(f"[{globals()['i']}] Scanning: {item}")
        globals()["i"] += 1
        item_path = path.join(directory, item)
        if path.isdir(item_path):
            process_directory(item_path)  # Recursively process subdirectories
        elif item_path.lower().endswith(".mp3"):
            process_song(item_path)


if __name__ == "__main__":
    if len(argv) < 2:
        print("Usage: python duplicate_songs_remover.py folder_path")
        exit(1)

    folder = argv[1]

    if path.exists(folder):
        print("Searching for duplicate songs...")
        spots_path = getcwd()
        history_file = f"{spots_path}/Music/.spots_download_history.txt"

        process_directory(folder)

        print("Duplicate songs removed!")
    else:
        print("Folder not found.")
