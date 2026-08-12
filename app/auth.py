"""Autenticacao, perfis de acesso e regras de permissao.

Este modulo e a fonte unica de verdade sobre "quem pode o que". As telas
consultam `pode()` para esconder o que o usuario nao acessa, e as rotas usam
`@requer()` para bloquear de fato - esconder botao nao e seguranca.

Perfis
------
SUPERADMIN  Acesso total, inclusive gestao de usuarios (criar/editar/excluir).
ADMIN       Operacao completa da loja, mas nao mexe em usuarios.
VENDEDOR    Vende, atende cliente e recebe crediario. Nao ve custo/margem,
            nao movimenta estoque e so enxerga as proprias vendas.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import abort, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .utils import agora_iso

# --- catalogo de perfis -----------------------------------------------------

PAPEIS = {
    "SUPERADMIN": {
        "rotulo": "Super administrador",
        "cor": "danger",
        "descricao": "Acesso irrestrito a todas as telas, incluindo a gestao de usuarios.",
    },
    "ADMIN": {
        "rotulo": "Administrador",
        "cor": "primary",
        "descricao": "Gerencia produtos, estoque, vendas, crediario e relatorios da loja.",
    },
    "VENDEDOR": {
        "rotulo": "Vendedor",
        "cor": "success",
        "descricao": "Registra vendas, atende clientes e recebe parcelas do crediario.",
    },
}

# --- matriz de permissoes ---------------------------------------------------
# Cada permissao lista os perfis que a possuem. Alterar aqui muda o sistema
# inteiro: navegacao, botoes e bloqueio das rotas.
PERMISSOES = {
    # Gestao de usuarios - exclusiva do super administrador
    "usuarios.gerenciar":  ("SUPERADMIN",),

    # Produtos
    "produtos.ver":        ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "produtos.editar":     ("SUPERADMIN", "ADMIN"),
    "custos.ver":          ("SUPERADMIN", "ADMIN"),

    # Notas Fiscais e movimentacoes de produtos
    "estoque.ver":         ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "estoque.movimentar":  ("SUPERADMIN", "ADMIN"),

    # Notas fiscais (cabecalho das movimentacoes de entrada/baixa/devolucao)
    "notas_fiscais.ver":   ("SUPERADMIN", "ADMIN", "VENDEDOR"),

    # Sacolas (consignacao externa) - a gerencia monta e acerta; o vendedor
    # so acompanha o que esta com ele.
    "sacolas.ver":         ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "sacolas.gerenciar":   ("SUPERADMIN", "ADMIN"),

    # Clientes
    "clientes.ver":        ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "clientes.editar":     ("SUPERADMIN", "ADMIN", "VENDEDOR"),

    # Vendedores
    "vendedores.ver":      ("SUPERADMIN", "ADMIN"),
    "vendedores.editar":   ("SUPERADMIN", "ADMIN"),

    # Vendas
    "vendas.criar":        ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "vendas.ver_todas":    ("SUPERADMIN", "ADMIN"),
    "vendas.cancelar":     ("SUPERADMIN", "ADMIN"),

    # Crediario
    "crediario.ver":       ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "crediario.receber":   ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "crediario.estornar":  ("SUPERADMIN", "ADMIN"),

    # Relatorios e painel
    "relatorios.ver":      ("SUPERADMIN", "ADMIN"),
    "relatorios.comissoes": ("SUPERADMIN", "ADMIN", "VENDEDOR"),
    "painel.gerencial":    ("SUPERADMIN", "ADMIN"),
}

# Resumo por perfil, exibido na tela de usuarios.
REGRAS_POR_PAPEL = {
    "SUPERADMIN": [
        ("Usuarios", "Cria, edita, ativa/desativa e exclui usuarios de qualquer perfil"),
        ("Produtos", "Cadastra, edita e ve precos de custo e margem, com grade por tamanho"),
        ("Notas Fiscais", "Entrada de NF, devolucao ao fornecedor, movimentacoes e listagem de NFs"),
        ("Sacolas", "Monta sacolas para vendedores e registra o acerto"),
        ("Vendas", "Registra, consulta todas as vendas da loja e cancela"),
        ("Crediario", "Recebe e estorna parcelas"),
        ("Relatorios", "Comissoes de todos os vendedores e posicao de estoque"),
    ],
    "ADMIN": [
        ("Usuarios", "Sem acesso - somente o super administrador gerencia usuarios"),
        ("Produtos", "Cadastra, edita e ve precos de custo e margem, com grade por tamanho"),
        ("Notas Fiscais", "Entrada de NF, devolucao ao fornecedor, movimentacoes e listagem de NFs"),
        ("Sacolas", "Monta sacolas para vendedores e registra o acerto"),
        ("Vendas", "Registra, consulta todas as vendas da loja e cancela"),
        ("Crediario", "Recebe e estorna parcelas"),
        ("Relatorios", "Comissoes de todos os vendedores e posicao de estoque"),
    ],
    "VENDEDOR": [
        ("Usuarios", "Sem acesso"),
        ("Produtos", "Somente consulta - nao ve preco de custo nem margem"),
        ("Notas Fiscais", "Consulta notas fiscais e movimentacoes, mas nao registra entradas ou devolucoes"),
        ("Sacolas", "Ve as proprias sacolas (o que saiu, vendeu e devolveu), sem montar ou acertar"),
        ("Vendas", "Registra vendas em seu proprio nome e ve apenas as suas"),
        ("Crediario", "Recebe parcelas; estorno so com um administrador"),
        ("Relatorios", "Apenas a propria comissao do mes"),
    ],
}


# --- usuario da sessao ------------------------------------------------------

def usuario_atual():
    """Usuario logado nesta requisicao, ou None.

    O resultado fica em cache em `g` para nao repetir a consulta, mas o cache
    e sempre validado contra o id da sessao: um contexto de aplicacao
    reaproveitado jamais entrega o usuario de outra sessao.
    """
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None

    cache = g.get("_usuario_cache")
    if cache is not None and cache[0] == usuario_id:
        return cache[1]

    usuario = db.query(
        """SELECT u.*, v.nome AS vendedor_nome
           FROM usuarios u
           LEFT JOIN vendedores v ON v.id = u.vendedor_id
           WHERE u.id = ? AND u.ativo = 1""",
        (usuario_id,),
        one=True,
    )
    g._usuario_cache = (usuario_id, usuario)
    return usuario


def pode(permissao):
    """True se o usuario logado tem a permissao informada."""
    usuario = usuario_atual()
    if usuario is None:
        return False
    return usuario["papel"] in PERMISSOES.get(permissao, ())


def meu_vendedor_id():
    """Cadastro de vendedor vinculado ao usuario logado (None se nao houver)."""
    usuario = usuario_atual()
    return usuario["vendedor_id"] if usuario else None


def autenticar(login, senha):
    """Valida as credenciais. Retorna a linha do usuario ou None."""
    usuario = db.query(
        "SELECT * FROM usuarios WHERE usuario = ?", ((login or "").strip().lower(),), one=True
    )
    if usuario is None or not usuario["ativo"]:
        return None
    if not check_password_hash(usuario["senha_hash"], senha or ""):
        return None
    return usuario


def _chave_tentativa(login, endereco_ip):
    origem = "%s|%s" % ((login or "").strip().lower(), endereco_ip or "desconhecido")
    return hashlib.sha256(origem.encode("utf-8")).hexdigest()


def _agora_utc():
    return datetime.now(timezone.utc)


def login_bloqueado(login, endereco_ip):
    """Informa se o par usuario/IP ainda esta temporariamente bloqueado."""
    chave = _chave_tentativa(login, endereco_ip)
    registro = db.query(
        "SELECT bloqueado_ate FROM tentativas_login WHERE chave = ?", (chave,), one=True
    )
    if not registro or not registro["bloqueado_ate"]:
        return False
    try:
        bloqueado_ate = datetime.fromisoformat(registro["bloqueado_ate"])
    except ValueError:
        db.execute("DELETE FROM tentativas_login WHERE chave = ?", (chave,))
        return False
    if bloqueado_ate > _agora_utc():
        return True
    db.execute("DELETE FROM tentativas_login WHERE chave = ?", (chave,))
    return False


def registrar_falha_login(login, endereco_ip):
    """Registra falha e bloqueia temporariamente ao atingir o limite."""
    from flask import current_app

    chave = _chave_tentativa(login, endereco_ip)
    agora = _agora_utc()
    registro = db.query(
        "SELECT tentativas FROM tentativas_login WHERE chave = ?", (chave,), one=True
    )
    tentativas = (registro["tentativas"] if registro else 0) + 1
    bloqueado_ate = None
    if tentativas >= current_app.config["LOGIN_MAX_TENTATIVAS"]:
        bloqueado_ate = agora + timedelta(
            minutes=current_app.config["LOGIN_BLOQUEIO_MINUTOS"]
        )
    db.execute(
        """INSERT INTO tentativas_login
               (chave, tentativas, primeira_em, ultima_em, bloqueado_ate)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(chave) DO UPDATE SET
               tentativas = excluded.tentativas,
               ultima_em = excluded.ultima_em,
               bloqueado_ate = excluded.bloqueado_ate""",
        (
            chave,
            tentativas,
            agora.isoformat(timespec="seconds"),
            agora.isoformat(timespec="seconds"),
            bloqueado_ate.isoformat(timespec="seconds") if bloqueado_ate else None,
        ),
    )
    return bloqueado_ate is not None


def limpar_falhas_login(login, endereco_ip):
    db.execute(
        "DELETE FROM tentativas_login WHERE chave = ?",
        (_chave_tentativa(login, endereco_ip),),
    )


def iniciar_sessao(usuario):
    session.clear()
    session["usuario_id"] = usuario["id"]
    session.permanent = False
    db.execute(
        "UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?", (agora_iso(), usuario["id"])
    )


def encerrar_sessao():
    session.clear()
    g.pop("_usuario_cache", None)


def hash_senha(senha):
    return generate_password_hash(senha)


# --- decoradores ------------------------------------------------------------

def login_obrigatorio(view):
    @wraps(view)
    def envolvida(*args, **kwargs):
        if usuario_atual() is None:
            return redirect(url_for("auth.login", proximo=request.full_path))
        return view(*args, **kwargs)

    return envolvida


def requer(*permissoes):
    """Bloqueia a rota se o usuario nao tiver TODAS as permissoes listadas."""

    def decorador(view):
        @wraps(view)
        def envolvida(*args, **kwargs):
            if usuario_atual() is None:
                return redirect(url_for("auth.login", proximo=request.full_path))
            for permissao in permissoes:
                if not pode(permissao):
                    abort(403)
            return view(*args, **kwargs)

        return envolvida

    return decorador


def init_app(app):
    """Exige login em tudo, menos nas rotas publicas, e expoe helpers ao Jinja."""
    publicas = {"auth.login", "saude.verificar", "static"}

    @app.before_request
    def exige_login():
        if request.endpoint in publicas:
            return None
        if usuario_atual() is None:
            return redirect(url_for("auth.login", proximo=request.full_path))
        return None

    @app.context_processor
    def injeta_sessao():
        return {
            "usuario": usuario_atual(),
            "pode": pode,
            "PAPEIS": PAPEIS,
        }
