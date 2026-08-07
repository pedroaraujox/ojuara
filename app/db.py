"""Camada de acesso ao SQLite.

O banco e o esquema sao criados automaticamente na primeira execucao
(ver `init_app`), sem necessidade de migracoes ou servidor externo.
"""

import os
import sqlite3

from flask import current_app, g

SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    """Conexao por requisicao, com linhas acessiveis por nome de coluna."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    linhas = cur.fetchall()
    cur.close()
    if one:
        return linhas[0] if linhas else None
    return linhas


def execute(sql, params=()):
    """Executa e comita, retornando o lastrowid."""
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    rowid = cur.lastrowid
    cur.close()
    return rowid


def escalar(sql, params=(), padrao=0):
    linha = query(sql, params, one=True)
    if linha is None or linha[0] is None:
        return padrao
    return linha[0]


# Colunas adicionadas em versoes recentes do esquema. `CREATE TABLE IF NOT
# EXISTS` nao altera tabelas ja existentes, entao um banco criado por uma
# versao anterior do sistema precisa ganhar essas colunas via ALTER TABLE
# para nao perder os dados ja cadastrados.
MIGRACOES_COLUNAS = {
    "notas_fiscais": [
        ("ativa", "INTEGER NOT NULL DEFAULT 1"),
    ],
    "clientes": [
        ("data_nascimento", "TEXT NOT NULL DEFAULT ''"),
    ],
    "vendedores": [
        ("data_nascimento", "TEXT NOT NULL DEFAULT ''"),
        ("cpf", "TEXT NOT NULL DEFAULT ''"),
        ("rg", "TEXT NOT NULL DEFAULT ''"),
        ("cep", "TEXT NOT NULL DEFAULT ''"),
        ("rua", "TEXT NOT NULL DEFAULT ''"),
        ("numero", "TEXT NOT NULL DEFAULT ''"),
        ("bairro", "TEXT NOT NULL DEFAULT ''"),
        ("cidade", "TEXT NOT NULL DEFAULT ''"),
        ("uf", "TEXT NOT NULL DEFAULT ''"),
    ],
    "sacolas": [
        ("nota_fiscal_id", "INTEGER REFERENCES notas_fiscais (id)"),
    ],
}


# Colunas removidas em versoes recentes do esquema (o conceito virou obsoleto
# ou migrou para outra tabela). Um banco criado por uma versao anterior
# precisa perder essas colunas via ALTER TABLE ... DROP COLUMN (suportado
# desde o SQLite 3.35) para o esquema ficar identico ao de uma instalacao nova.
MIGRACOES_REMOCOES = {
    # Fornecedor virou um dado da Nota Fiscal (notas_fiscais.fornecedor), nao
    # mais do produto: o catalogo passou a ser puramente descritivo.
    "produtos": ["fornecedor", "codigo_barras"],
}


def _tabela_existe(conexao, tabela):
    return (
        conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)
        ).fetchone()
        is not None
    )


def _migrar_colunas(conexao):
    for tabela, colunas in MIGRACOES_COLUNAS.items():
        if not _tabela_existe(conexao, tabela):
            continue  # tabela nova: o executescript a seguir ja cria com as colunas certas
        existentes = {linha[1] for linha in conexao.execute("PRAGMA table_info(%s)" % tabela)}
        for nome, definicao in colunas:
            if nome not in existentes:
                conexao.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabela, nome, definicao))


def _remover_colunas(conexao):
    for tabela, colunas in MIGRACOES_REMOCOES.items():
        if not _tabela_existe(conexao, tabela):
            continue
        existentes = {linha[1] for linha in conexao.execute("PRAGMA table_info(%s)" % tabela)}
        for nome in colunas:
            if nome in existentes:
                conexao.execute("ALTER TABLE %s DROP COLUMN %s" % (tabela, nome))


def init_db(app):
    """Cria o arquivo do banco e as tabelas caso ainda nao existam."""
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    with open(SCHEMA, "r", encoding="utf-8") as arquivo:
        script = arquivo.read()

    conexao = sqlite3.connect(app.config["DATABASE"])
    # As migracoes rodam ANTES do executescript: o schema.sql pode conter
    # indices sobre colunas novas (ex.: idx_sacolas_nf), e criar esses
    # indices so funciona se a coluna ja existir na tabela.
    _migrar_colunas(conexao)
    _remover_colunas(conexao)
    conexao.executescript(script)
    conexao.commit()
    conexao.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app)

    from .seed import garantir_superadmin, popular_demo

    with app.app_context():
        if app.config.get("SEED_DEMO"):
            popular_demo()
        # Roda sempre: sem super administrador ninguem entra no sistema.
        garantir_superadmin(app)
