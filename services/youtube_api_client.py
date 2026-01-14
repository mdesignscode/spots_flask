import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


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
        self.service = self._build_service()

    def _build_service(self):
        """
        Build service for interacting with YouTube API

        Returns:
            Unknown: YouTube client.
        """
        creds = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secrets.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)

        return build("youtube", "v3", credentials=creds)

    def like_video(self, video_id: str):
        """
        Adds a youtube video to the users liked library

        Args:
            video_id (str): The id of the video.

        Returns:
            None
        """
        self.service.videos().rate(id=video_id, rating="like").execute()
