from os.path import exists

FILENAME = ".env"

def save_env(variables: dict[str, str]):
    file_data = ""

    for k, v in variables.items():
        data = f"{k}={v}\n"
        file_data += data

    with open(FILENAME, "w") as f:
        f.write(file_data)

def required_input(prompt: str):
    required_value = ""

    while not required_value:
        required_value = input(f"[Required] {prompt} ")

    return required_value


def main():
    if exists(FILENAME):
        setup_again = input("Environment variables already set, run setup again? Leave empty for no. ")
        if not setup_again:
            print("Aborting...\n")
            return

    print("Setting up environment variables...")
    static_cover_name = "single-cover.jpg"
    flask_port = 5000

    variables_map = {
        "flask_port": flask_port,
        "static_cover_name": static_cover_name,
    }

    has_spotify_membership = input(
        "Do u have a paid Spotify API membership? Required for Spotify actions. Leave empty for no. "
    )
    if has_spotify_membership:
        # get values
        spotify_username = required_input("Enter Spotify username")
        spotify_client_id = required_input("Enter Spotify client id:")
        spotify_client_secret = required_input("Enter Spotify client secret:")
        common_redirect_uri = "https://open.spotify.com/?"
        spotify_redirect_uri = (
            input(
                f"Enter Spotify redirect uri: Leave empty to use [{common_redirect_uri}] "
            )
            or common_redirect_uri
        )

        # set values
        variables_map["username"] = spotify_username
        variables_map["SPOTIPY_CLIENT_ID"] = spotify_client_id
        variables_map["SPOTIPY_CLIENT_SECRET"] = spotify_client_secret
        variables_map["SPOTIPY_REDIRECT_URI"] = spotify_redirect_uri

    has_genius_key = input(
        "Do u have a Genius API key? Used as optional lyrics provider. Leave empty for no. "
    )
    if has_genius_key:
        genius_key = required_input("Enter Genius API key:")
        variables_map["lyricsgenius_key"] = genius_key

    save_env(variables_map)
    print("Environment variables setup complete\n")

if __name__ == "__main__":
    main()

