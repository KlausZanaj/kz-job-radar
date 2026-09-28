"""Start locally: py -3 start.py (Windows) or python3 start.py."""
import threading
import webbrowser

from jobradr.server import serve


if __name__ == "__main__":
    print("KZ Job Radar: http://127.0.0.1:8765")
    print("Lascia aperta questa finestra per il monitoraggio orario. CTRL+C per fermare.")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    serve()
