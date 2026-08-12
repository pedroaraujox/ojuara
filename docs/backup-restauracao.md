# Backup e restauração

## Política atual

- Backup SQLite consistente ao iniciar o serviço de backup.
- Repetição padrão a cada 24 horas.
- Retenção local padrão de 30 dias.
- Integridade verificada por `PRAGMA integrity_check` durante a cópia.
- Dev e produção possuem diretórios separados.

Um backup na mesma VM não protege contra perda total da máquina. Copie
periodicamente backups de produção para armazenamento externo protegido.

## Verificar um backup

```bash
python3 - <<'PY'
import sqlite3
caminho = "/opt/ojuara-producao/backups/ARQUIVO.db"
with sqlite3.connect(f"file:{caminho}?mode=ro", uri=True) as db:
    print(db.execute("PRAGMA integrity_check").fetchone()[0])
PY
```

O resultado obrigatório é `ok`.

## Restauração de produção

Use somente após confirmar o arquivo, seu ambiente e a necessidade da
restauração. A operação substitui o banco ativo.

1. Ative modo de manutenção no Proxy Host ou interrompa o acesso dos usuários.
2. Pare aplicação e backup de produção pelo Portainer.
3. Crie uma cópia de segurança do banco atual.
4. Valide o backup escolhido com `integrity_check`.
5. Copie o backup para `/opt/ojuara-producao/data/ojuara.db`.
6. Aplique proprietário `10001:10001` e modo `640`.
7. Inicie a Stack, aguarde `healthy` e execute testes funcionais.

Exemplo dos passos de arquivo, substituindo caminhos explicitamente:

```bash
sudo cp /opt/ojuara-producao/data/ojuara.db /opt/ojuara-producao/backups/pre-restauracao.db
sudo cp /opt/ojuara-producao/backups/ARQUIVO_VALIDADO.db /opt/ojuara-producao/data/ojuara.db
sudo chown 10001:10001 /opt/ojuara-producao/data/ojuara.db
sudo chmod 640 /opt/ojuara-producao/data/ojuara.db
```

Não restaure backup de dev em produção. Registre data, motivo, arquivo e
resultado da validação.

## Teste periódico

Trimestralmente, restaure uma cópia em ambiente isolado, faça login e consulte
produtos, clientes, vendas e NFs. Backup sem teste de restauração é apenas uma
hipótese de recuperação.
