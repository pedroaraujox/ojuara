# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Ojuara — a local web system for managing a lingerie retail store (portfolio
project for Outbox Tech): product catalog, stock tied to Nota Fiscal (NF),
sales with crediário (installments), clients, salespeople, commissions, and
external consignment ("sacolas"). Flask + raw SQLite (no ORM) + server-rendered
Jinja + vanilla JS. Runs 100% locally, no Docker, no external DB server. Not a
git repository. Portuguese is the language of the domain, the UI, and almost
all identifiers/comments in the code — keep new code consistent with that.

`README.md` is the user-facing doc (setup, features, permission matrix, data
model) — read it for product behavior. This file is about the engineering
patterns you need before touching multiple files at once.

## Commands

Documentation is indexed at `docs/README.md`. Changes to behavior,
configuration, routes, permissions, infrastructure, backup or operations must
update the corresponding canonical document in the same change.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

- Single dependency: `Flask==3.0.3` (see `requirements.txt`). No build step, no bundler, no linter/formatter configured.
- The SQLite file (`data/ojuara.db`) and its schema are created automatically on first run. Demo data seeds automatically unless `OJUARA_SEED=0` is set.
- To reset to an empty database (schema + superadmin only, no demo data): delete `data/ojuara.db` and run with `$env:OJUARA_SEED="0"; python run.py`.
- `run.py` hardcodes `debug=True` — intentional for local dev, and it means the reloader spawns a child process; don't rely on the parent PID when killing a stray server.

**There is no automated test suite committed to the repo.** The way this codebase has actually been verified while building each feature is ad-hoc smoke scripts using Flask's `test_client()` — spin up `create_app()`, hit routes with `client.get/post`, assert on response status/body and on DB state via `app.app_context()` + the `db` module. Always run such a script against a **freshly deleted `data/ojuara.db`** so seed data is deterministic:

```python
from app import create_app
app = create_app()
with app.test_client() as c:
    c.post("/login", data={"usuario": "superadmin", "senha": "Ojuara@2026"})
    r = c.get("/produtos/")
    assert r.status_code == 200
```

When changing business logic (`services.py`, `auth.py`), write/run a throwaway script like this rather than trusting a manual click-through — it's the established way to catch regressions here (grade/tamanho resolution, NF grouping, "tudo ou nada" batch validation, permission matrix per role, sacola reconciliation math are all easy to silently break).

## Architecture

### App factory & layout
`app/__init__.py` builds the Flask app (`create_app()`), wires `db.init_app`, `auth.init_app`, registers one blueprint per module under `app/routes/`, and registers 404/403/500 handlers rendering `templates/erro.html`. Every route lives in a blueprint; there are no routes directly on `app`.

- `app/db.py` — raw `sqlite3`, one connection per request via Flask `g`, `row_factory=sqlite3.Row`. `query()`/`execute()`/`escalar()` are the only DB helpers; no ORM, no query builder.
- `app/schema.sql` — full DDL, executed with `CREATE TABLE IF NOT EXISTS` on every startup (safe re-run, but never mutates an existing table).
- **Schema migrations**: since `CREATE TABLE IF NOT EXISTS` can't add columns to a table that already exists, `db.py` has a `MIGRACOES_COLUNAS` dict + `_migrar_colunas()` that runs `PRAGMA table_info` and `ALTER TABLE ... ADD COLUMN` for anything missing, every startup. **Any new column added to an existing table must be registered there**, or an already-deployed database silently won't get it (this has bitten this project before — see the `clientes`/`vendedores` entries for the pattern).
- `app/services.py` — all business logic (stock movement, NF handling, sales, crediário, sacolas) lives here, not in routes. Routes parse the request, call a service function, and flash/redirect. `ErroNegocio` is the one exception type services raise for user-facing validation failures; routes catch it and `flash()` the message.
- `app/utils.py` — form parsing (`to_int`, `to_decimal`), date helpers, BR currency/date Jinja filters, code/size normalization, CPF helpers.
- `app/seed.py` — demo data (gated by `OJUARA_SEED`) and `garantir_superadmin()`, which runs unconditionally on every startup so the app is never unreachable.

### Auth & permissions (`app/auth.py`)
Three roles — `SUPERADMIN`, `ADMIN`, `VENDEDOR` — defined by a single `PERMISSOES` dict mapping permission strings to the roles allowed. `@requer("permissao", ...)` decorates routes and **is the actual enforcement**; `pode("permissao")` is used in Jinja only to hide UI. Never add a permission check only in a template — a route without `@requer(...)` is reachable by anyone logged in. `usuario_atual()` caches the current user on `g` but always re-validates against `session["usuario_id"]` first (a prior bug let a stale `g` cache leak an identity across requests with no session — don't reintroduce that shortcut).

VENDEDOR-role data scoping is enforced server-side, not just filtered in queries: e.g. a sale POSTed with someone else's `vendedor_id` is silently rewritten to the logged-in vendor's own id, and fetching another vendor's sale/sacola by URL returns 403.

### Core domain model: NF-first stock, grade by size, sacolas
Three ideas run through most of the stock/product code and are easy to violate without knowing them:

1. **Product = `(codigo_fabricante, tamanho, cor)`, not just code.** The code read from the label identifies the model and is intentionally shared by its sizes and colors. Each size/color combination is a separate stock row. `services._resolver_produto(codigo, tamanho, cor)` is the one place that resolves an exact variant. Reuse it rather than re-querying `produtos` directly — `validar_lote()` and the sale price lookup depend on consistent resolution.
2. **Stock never changes outside a Nota Fiscal.** `notas_fiscais` is a header row keyed by `(numero, tipo)`; `obter_ou_criar_nota_fiscal()` is idempotent so repeated lançamentos into the same NF number accumulate instead of duplicating the header. The product catalog form (`routes/produtos.py`) does **not** touch stock at all — every product is born with `estoque = 0`; stock only moves through `services.movimentar()` / `aplicar_lote()`, always with a `nota_fiscal_id`. Entrada uses `estoque/entrada_nf.html`, where exact catalog variants are selected and only quantity is entered. `estoque/baixa.html` remains the batch template for baixa/devolucao. Validation is all-or-nothing (`validar_lote` returns `(validos, erros)` — if `erros` is non-empty, nothing gets applied, ever).
3. **Sacolas (external consignment) are drawn from a specific active NF, not from general stock.** `notas_fiscais.ativa` controls eligibility. `produtos_disponiveis_na_nf()` caps what a sacola can take to `min(recebido nessa NF, estoque atual do produto)`. `registrar_acerto_sacola()` takes incremental vendido/devolvido quantities per item, guards against acertando more than is currently `em_posse`, and auto-closes the sacola to `ACERTADA` only when every item is fully accounted for.
4. **Every new sale consumes the selected seller's bag, never general stock.** `produtos_disponiveis_vendedor()` requires an open sacola tied to an active entrada NF and exposes only the remaining `quantidade_saida - quantidade_vendida - quantidade_devolvida`. `registrar_venda()` revalidates this rule server-side, allocates FIFO through `venda_sacola_alocacoes`, and increments `sacola_itens.quantidade_vendida` without another stock movement (stock already left on `SAIDA_SACOLA`). Cancellation reverses those allocations back into the bag; only legacy sales without allocations use an `ESTORNO` stock movement.

### Frontend
Server-rendered Jinja (`app/templates/`, one directory per blueprint) + Bootstrap 5.3 (CDN) + one hand-written JS file, `app/static/js/app.js`. Its `GradeLote` class is the batch-entry grid reused across estoque (entrada/baixa/devolução), vendas and sacolas: code (typed or read by camera) → live variant lookup via `/api/produtos/<codigo>` → size picker → color picker → quantity → Enter advances to the next row. Product-label scanning accepts exactly five numeric digits; on new-product registration, OCR also suggests the printed model name while leaving it editable.

**Theming (`app/static/css/estilo.css`)**: light/dark is controlled by `data-bs-theme` on `<html>`, toggled by `#botao-tema` (wired in `app.js`) and persisted to `localStorage`; `_head_tema.html` (included by both `base.html` and the standalone `auth/login.html`) sets the attribute *before* Bootstrap/CSS load so there's no flash of the wrong theme. Non-obvious Bootstrap 5.3 gotcha discovered while building this: several components (`.card`, `.dropdown-menu`, `.list-group-item`) redeclare their own CSS variable (`--bs-card-bg`, `--bs-dropdown-bg`, `--bs-list-group-bg`) *locally on the component's own class*, so overriding it at `:root`/`[data-bs-theme]` has no effect — you have to redeclare it at the same selector Bootstrap uses (e.g. `.card { --bs-card-bg: ...; }`). Contextual table/row variants (`.table-light`, `.table-secondary`, `.table-danger`) are similarly *not* theme-aware in vanilla Bootstrap and need an explicit `[data-bs-theme="dark"] .table-light { --bs-table-bg: ...; }` override. If you add a new component that looks "stuck" in one theme, this is almost certainly why.

`login.html` is the only template that doesn't extend `base.html` (it's a standalone full-page layout); `erro.html` and everything else does.
