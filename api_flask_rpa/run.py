from flask import Flask
from config import settings
from app.blueprints.gestion_bp import bp as gestion_bp
from app.blueprints.health_bp import bp as health_bp
import os


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(gestion_bp, url_prefix="/api/gestion")

    # ensure folders
    os.makedirs(settings.SCREENSHOT_PATH, exist_ok=True)
    os.makedirs(settings.PDF_DIR, exist_ok=True)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
