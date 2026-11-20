"""Start the app:   python run.py      then open  http://127.0.0.1:5000"""
import threading
import webbrowser

from app import create_app
from app.settings import load_settings

if __name__ == "__main__":
    s = load_settings()
    url = f"http://{s['host']}:{s['port']}"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()      # open the browser for you
    create_app().run(host=s["host"], port=int(s["port"]), debug=False)
