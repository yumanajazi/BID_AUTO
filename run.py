
"""Start the app locally or on Render."""

import os
import threading
import webbrowser

from app import create_app
from app.settings import load_settings


if __name__ == "__main__":
    s = load_settings()

    # Render provides PORT automatically.
    port = int(os.environ.get("PORT", s.get("port", 5000)))

    # Always bind to 0.0.0.0 on Render.
    host = "0.0.0.0"

    # Open browser only when running locally.
    if not os.environ.get("RENDER"):
        url = f"http://127.0.0.1:{port}"
        threading.Timer(
            1.2,
            lambda: webbrowser.open(url)
        ).start()

    # Start Flask application.
    create_app().run(
        host=host,
        port=port,
        debug=False
    )
