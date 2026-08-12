# Guia de desenvolvimento

## Pré-requisitos

- Python 3.10 ou superior; produção usa Python 3.12.
- Docker Desktop para validação equivalente à produção.
- Git.

## Execução local com Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Acesse `http://127.0.0.1:5000`. O modo local cria dados demonstrativos por
padrão. Para banco vazio, defina `OJUARA_SEED=0` antes da primeira execução.

## Execução local com Docker

Copie `.env.example` para `.env`, substitua os valores secretos e execute:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

O Compose local usa volumes Docker e publica `5000` apenas para desenvolvimento.
O arquivo de Portainer é `compose.portainer.yaml` e não deve ser usado como
substituto do Compose local.

## Fluxo de mudança

1. Trabalhe na branch `desenvolvimento`.
2. Preserve alterações locais não relacionadas.
3. Mantenha regras em `services.py` e proteção HTTP em `auth.py`/decoradores.
4. Atualize schema e `MIGRACOES_COLUNAS` quando adicionar colunas.
5. Execute um smoke test com `create_app()` e banco novo.
6. Execute obrigatoriamente `docker compose up --build -d`.
7. Confirme o serviço `app` como `healthy`.
8. Valide em dev antes de promover o mesmo commit para `producao`.

## Smoke test mínimo

```python
from app import create_app

app = create_app()
with app.test_client() as cliente:
    assert cliente.get("/saude").status_code == 200
    assert cliente.get("/login").status_code == 200
```

Para regras críticas, valide também estado do banco: resolução de grade,
movimentação por NF, lote tudo-ou-nada, sacola, venda e cancelamento.

## Convenções

- Código, interface e domínio em português.
- SQL parametrizado; não interpolar entrada do usuário.
- POST para mudanças de estado.
- `ErroNegocio` para validações apresentadas ao usuário.
- Não versionar `.env`, bancos, backups, logs, OCR treinado ou `outputs/`.
