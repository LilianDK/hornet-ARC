"""Startet den hornet-ARC-Dienst.

    python run.py              -> sucht ab Port 8765 einen freien Port und öffnet den Browser
    python run.py --port 9000  -> anderer Startport
    python run.py --no-browser -> Browser nicht automatisch öffnen
"""
import argparse
import os
import socket
import threading
import webbrowser

import uvicorn

DEFAULT_PORT = 8765


def port_in_use(port: int) -> bool:
    # 1) Antwortet dort schon etwas? (IPv4 und IPv6, da "localhost" auf beides zeigen kann)
    for fam, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((addr, port)) == 0:
                    return True
        except OSError:
            pass
    # 2) Lässt sich der Port binden? (fängt auch von Windows reservierte Ports ab)
    for addr in ("127.0.0.1", "0.0.0.0"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                s.bind((addr, port))
            except OSError:
                return True
    return False


def random_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pick_port(start: int) -> int:
    for p in range(start, start + 50):
        if not port_in_use(p):
            return p
    return random_free_port()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="hornet-ARC Projektreferenzen")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    port = pick_port(a.port)
    if port != a.port:
        print(f"Port {a.port} ist belegt, nutze stattdessen Port {port}.")
    url = f"http://127.0.0.1:{port}"
    print(f"\n  hornet-ARC läuft auf {url}\n  Beenden mit Strg+C\n")
    if not a.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
