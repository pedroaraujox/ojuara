"""Servidor local de producao, publicado somente pelo Cloudflare Tunnel."""

import os

os.environ.setdefault("OJUARA_AMBIENTE", "producao")
os.environ.setdefault("OJUARA_SEED", "0")

from waitress import serve

from app import create_app


def main():
    app = create_app()
    porta = int(os.environ.get("OJUARA_PORTA", "5000"))
    serve(
        app,
        host="127.0.0.1",
        port=porta,
        threads=4,
        clear_untrusted_proxy_headers=True,
    )


if __name__ == "__main__":
    main()
