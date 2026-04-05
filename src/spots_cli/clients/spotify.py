from dotenv import load_dotenv
from logging import getLogger
from os import getenv
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy import Spotify
from spotipy.util import prompt_for_user_token

load_dotenv()

logger = getLogger(__name__)

DEFAULT_USER_SCOPE = "user-library-read"


class SpotifyClient:
    """A class to retrieve metadata for a spotify track, album or playlist

    Attributes:
        track_url (str): The spotify url to be processed
    """

    def __init__(self) -> None:
        """Initializes a spotify.spotify"""

        auth_manager = SpotifyClientCredentials()
        self.client = Spotify(auth_manager=auth_manager)

    def get_user(self) -> str | None:
        """Retrieves the current user

        Returns:
            str: The user's display name
        """
        if not getenv("username"):
            return None

        user = None

        try:
            self.signin()
            user = self.client.current_user()
        except SpotifyException as e:
            logger.error(f"An error occured while signin user in::\n\t{e.msg}")

        if user:
            return user["display_name"]

        return None

    def signin(self) -> None:
        """signs into a user's spotify account"""
        # sign user in if username present in env
        username = getenv("username")
        if not username:
            logger.info("Set Spotify `username` in `.env`")
            raise Exception("No `username` declared in environment variables")

        scope = getenv("scope") or DEFAULT_USER_SCOPE

        logger.info(f"Signing in to {username} on Spotify with scope: {scope}")

        try:
            # throws error if user not signed in
            self.client.current_user()
            return
        except SpotifyException as e:
            if e.code == -1:
                token = prompt_for_user_token(username, scope)
            else:
                raise

        if token:
            logger.info("Signed in")
            self.client = Spotify(auth=token)

            return
        else:
            raise Exception("Can't get token for", username)
