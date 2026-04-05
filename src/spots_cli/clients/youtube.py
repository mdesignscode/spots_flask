import os
import pickle
from importlib.resources import files
from os.path import exists
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from spots_cli.utils import get_config_path

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
config_dir = get_config_path()
PICKLE_TOKEN = f"{config_dir}/token.pickle"


class YouTubeApiClient:
    """
    Service for interacting with the YouTube API

    Attributes:
        @service (Unknown): The youtube api service.

    Methods
        @like_video

    This service handles:
    - Adding a video to YouTube likes library
    """

    def __init__(self):
        """
        Initialize the YouTubeApiClient.

        Sets up the api client.
        """
        self.secrets_file = str(files("spots_cli.config").joinpath("client_secrets.json"))
        if not exists(self.secrets_file):
            raise RuntimeError("Provide path to cookies for YouTube account access.")

        self.service = self._build_service()

    def _build_service(self):
        """
        Build service for interacting with YouTube API

        Returns:
            Unknown: YouTube client.
        """
        creds = None
        if os.path.exists(PICKLE_TOKEN):
            with open(PICKLE_TOKEN, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.secrets_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(PICKLE_TOKEN, "wb") as f:
                pickle.dump(creds, f)

        return build("youtube", "v3", credentials=creds)
