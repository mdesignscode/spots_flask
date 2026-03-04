from os import path


class HistoryManager:
    def __init__(self):
        self.history_file = "./Music/.spots_download_history.txt"

        # Check if the file exists, otherwise create it
        if not path.isfile(self.history_file):
            with open(self.history_file, "w", newline=""):
                pass

    def read(self, title: str) -> bool:
        """Checks if a title is in history

        Args:
            title (str, optional): The title to be checked.
        """

        title_exists = False

        with open(self.history_file, "r") as file:
            history = file.read().split("\n")
            for song in history:
                if title == song:
                    title_exists = True

        return title_exists

    def write(self, title: str):
        """Adds a downloaded song's title to history

        Args:
            title (str, optional): The title to be added.
        """
        with open(self.history_file, "a", newline="") as file:
            file.write(f"{title}\n")

