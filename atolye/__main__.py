"""python3 -m atolye"""

import argparse

from .llm import choose_provider
from .server import WorkshopServer


def main():
    parser = argparse.ArgumentParser(description="Burs Başvuru Cümle Atölyesi")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--demo", action="store_true", help="Yerel demo sağlayıcısını kullan")
    args = parser.parse_args()
    with WorkshopServer((args.host, args.port), choose_provider(args.demo)) as server:
        print(f"Atölye http://{args.host}:{server.server_port} adresinde hazır.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
