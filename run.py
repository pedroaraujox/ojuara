"""Ponto de entrada do sistema Ojuara.

Uso:
    python run.py

O servidor sobe em http://127.0.0.1:5000 e o banco SQLite e criado
automaticamente na primeira execucao.
"""

import os

from app import create_app

app = create_app()


if __name__ == "__main__":
    # A depuracao precisa ser habilitada explicitamente e nunca e usada pelo
    # inicializador de producao (servidor_producao.py + Waitress).
    debug = os.environ.get("OJUARA_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug)
