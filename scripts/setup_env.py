from os.path import exists
from typing import Literal

FILENAME = ".env"


def save_env(variables: dict[str, str]):
    file_data = ""

    for k, v in variables.items():
        file_data += f"{k}={v}\n"

    with open(FILENAME, "w") as f:
        f.write(file_data)


def required_input(prompt: str):
    value = ""

    while not value:
        value = input(f"[REQUIRED] {prompt}: ").strip()

    return value


def optional_input(prompt: str, default: str | None = None):
    value = input(f"[OPTIONAL] {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return value or default


def main():
    if exists(FILENAME):
        setup_again = input(
            "Environment variables already exist.\n"
            "Would you like to reconfigure them? (press Enter to cancel): "
        ).strip()

        if not setup_again:
            print("Setup cancelled.\n")
            return

    print("\n=== Environment Configuration ===\n")

    static_cover_name = "single-cover.jpg"
    flask_port = 5000
    main_provider: Literal["deezer", "spotify"] = "deezer"
    spotify_features_available = "False"
    youtube_account_features_available = "False"

    variables_map = {
        "flask_port": flask_port,
        "static_cover_name": static_cover_name,
        "spotify_features_available": spotify_features_available,
        "youtube_account_features_available": youtube_account_features_available,
        "main_provider": main_provider,
    }

    print("---- Spotify Configuration ----")
    has_spotify_membership = input(
        "Do you have a paid Spotify API membership? (required for Spotify features) [y/N]: "
    ).strip().lower()

    if has_spotify_membership == "y":
        spotify_username = required_input("Spotify username")
        spotify_client_id = required_input("Spotify client ID")
        spotify_client_secret = required_input("Spotify client secret")

        default_redirect = "https://open.spotify.com/?"
        spotify_redirect_uri = optional_input(
            "Spotify redirect URI", default_redirect
        )

        variables_map["username"] = spotify_username
        variables_map["SPOTIPY_CLIENT_ID"] = spotify_client_id
        variables_map["SPOTIPY_CLIENT_SECRET"] = spotify_client_secret
        variables_map["SPOTIPY_REDIRECT_URI"] = spotify_redirect_uri

        variables_map["spotify_features_available"] = "True"
        variables_map["main_provider"] = "spotify"

    print("\n---- Genius (Lyrics) Configuration ----")
    has_genius_key = input(
        "Do you have a Genius API key? (optional, for lyrics) [y/N]: "
    ).strip().lower()

    if has_genius_key == "y":
        genius_key = required_input("Genius API key")
        variables_map["lyricsgenius_key"] = genius_key

    print("\n---- YouTube Configuration ----")
    use_youtube_features = input(
        "Enable YouTube account features (likes, library access)? [y/N]: "
    ).strip().lower()

    if use_youtube_features == "y":
        cookies_path = required_input(
            "Enter path to YouTube cookies file (e.g. ./Music/cookies.txt)"
        )

        variables_map["YOUTUBE_COOKIES_PATH"] = cookies_path
        variables_map["youtube_account_features_available"] = "True"

    save_env(variables_map)

    print("\n✅ Environment variables have been successfully configured.\n")


if __name__ == "__main__":
    main()
