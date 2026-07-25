from flask import Flask, jsonify
from flask_cors import CORS
from logging import getLogger
from pathlib import Path

from spots_cli.bootstrap import Container
from spots_cli.utils import get_config_path
from server.download_music import blueprint as download_music_blueprint
from server.download_video import blueprint as download_video_blueprint
from server.media import blueprint as media_blueprint
from server.pages import blueprint as pages_blueprint

app = Flask(__name__, static_url_path="/static")
app.register_blueprint(download_music_blueprint)
app.register_blueprint(download_video_blueprint)
app.register_blueprint(media_blueprint)
app.register_blueprint(pages_blueprint)
CORS(app)

bootstrapper = Container()

logger = getLogger(__name__)


@app.route("/status")
def status():
    return jsonify(
        {"config": str(get_config_path()),
         "status": "It's alive!", "path": str(Path())}
    )
