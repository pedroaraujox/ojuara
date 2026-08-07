"""Servidor de producao para execucao local ou em container."""

import os

os.environ.setdefault("OJUARA_AMBIENTE", "producao")
os.environ.setdefault("OJUARA_SEED", "0")

from waitress import serve

from app import create_app


def main():
    app = create_app()
    host = os.environ.get("OJUARA_HOST", "127.0.0.1")
    porta = int(os.environ.get("OJUARA_PORTA", "5000"))
    serve(
        app,
        host=host,
        port=porta,
        threads=4,
        clear_untrusted_proxy_headers=True,
    )


if __name__ == "__main__":
    main()
