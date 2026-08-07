"""Executa backup ao iniciar e repete no intervalo configurado."""

import os
import time

from backup_sqlite import criar_backup


INTERVALO = int(os.environ.get("OJUARA_BACKUP_INTERVALO_SEGUNDOS", "86400"))


def main():
    if INTERVALO < 3600:
        raise ValueError("O intervalo de backup precisa ser de pelo menos uma hora.")
    while True:
        destino = criar_backup()
        print("Backup concluido: %s" % destino, flush=True)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
