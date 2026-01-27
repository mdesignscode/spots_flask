from models.errors import TitleExistsError
from os import path


class AddToHistoryService:
    @staticmethod
    def add_to_download_history(title: str = "", add_title: bool = False):
        """Adds a downloaded song's title to history

        Args:
            title (str, optional): The title to be added. Defaults to ''.
            add_title (bool, optional): If False, only checks if title already exists. Defaults to False.

        Raises:
            TitleExistsError: if title already in downloads history
        """
        history_file = "./Music/.spots_download_history.txt"

        # Check if the file exists, otherwise create it
        if not path.isfile(history_file):
            with open(history_file, "w", newline=""):
                pass

        # Check if the title already exists in the file
        with open(history_file, "r") as file:
            history = file.read().split("\n")
            for song in history:
                if title == song:
                    raise TitleExistsError(title)

        # Add the title to the file
        if add_title:
            with open(history_file, "a", newline="") as file:
                file.write(f"{title}\n")

