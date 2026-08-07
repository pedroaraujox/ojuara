"""Cria uma copia consistente do SQLite e conserva os ultimos 30 dias."""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = Path(os.environ.get("OJUARA_DATABASE", RAIZ / "data" / "ojuara.db"))
DESTINO = Path(os.environ.get("OJUARA_BACKUP_DIR", RAIZ / "backups"))
RETENCAO_DIAS = int(os.environ.get("OJUARA_BACKUP_RETENCAO_DIAS", "30"))


def criar_backup():
    if not ORIGEM.is_file():
        raise FileNotFoundError("Banco do Ojuara nao encontrado: %s" % ORIGEM)

    DESTINO.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    temporario = DESTINO / ("ojuara-%s.db.tmp" % carimbo)
    definitivo = DESTINO / ("ojuara-%s.db" % carimbo)

    with closing(sqlite3.connect(ORIGEM)) as origem, closing(
        sqlite3.connect(temporario)
    ) as copia:
        origem.backup(copia)
        resultado = copia.execute("PRAGMA integrity_check").fetchone()[0]
        if resultado != "ok":
            raise RuntimeError("Backup reprovado no integrity_check: %s" % resultado)
        copia.commit()

    temporario.replace(definitivo)
    limite = datetime.now() - timedelta(days=RETENCAO_DIAS)
    for arquivo in DESTINO.glob("ojuara-*.db"):
        if datetime.fromtimestamp(arquivo.stat().st_mtime) < limite:
            arquivo.unlink()

    return definitivo


if __name__ == "__main__":
    print(criar_backup())
