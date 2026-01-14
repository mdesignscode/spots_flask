class YTVideoInfo:
    def __init__(
        self,
        id: str,
        title: str,
        uploader: str,
        audio_ext: str,
        filesize: int,
    ):
        self.id = id
        self.title = title
        self.uploader = uploader
        self.audio_ext = audio_ext
        self.filesize = filesize
