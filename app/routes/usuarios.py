"""Gestao de usuarios - exclusiva do perfil SUPERADMIN."""

import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import PAPEIS, REGRAS_POR_PAPEL, hash_senha, requer, usuario_atual
from ..utils import agora_iso, to_int

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@bp.route("/")
@requer("usuarios.gerenciar")
def listar():
    usuarios = db.query(
        """SELECT u.*, v.nome AS vendedor_nome
           FROM usuarios u
           LEFT JOIN vendedores v ON v.id = u.vendedor_id
           ORDER BY
             CASE u.papel WHEN 'SUPERADMIN' THEN 0 WHEN 'ADMIN' THEN 1 ELSE 2 END,
             u.nome"""
    )
    return render_template(
        "usuarios/listar.html",
        usuarios=usuarios,
        regras=REGRAS_POR_PAPEL,
        eu=usuario_atual(),
    )


@bp.route("/novo", methods=["GET", "POST"])
@requer("usuarios.gerenciar")
def novo():
    if request.method == "POST":
        dados = _le_formulario(request.form)
        senha = request.form.get("senha") or ""
        erro = _valida(dados) or _valida_senha(senha, request.form.get("senha_confirmacao"))
        if erro:
            flash(erro, "danger")
            return _tela(dados, novo=True)

        try:
            db.execute(
                """INSERT INTO usuarios
                       (nome, usuario, senha_hash, papel, vendedor_id, ativo, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    dados["nome"],
                    dados["usuario"],
                    hash_senha(senha),
                    dados["papel"],
                    dados["vendedor_id"],
                    dados["ativo"],
                    agora_iso(),
                ),
            )
        except sqlite3.IntegrityError:
            flash("Ja existe um usuario com o login '%s'." % dados["usuario"], "danger")
            return _tela(dados, novo=True)

        flash("Usuario '%s' criado." % dados["usuario"], "success")
        return redirect(url_for("usuarios.listar"))

    vazio = {"nome": "", "usuario": "", "papel": "VENDEDOR", "vendedor_id": None, "ativo": 1}
    return _tela(vazio, novo=True)


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@requer("usuarios.gerenciar")
def editar(usuario_id):
    alvo = db.query("SELECT * FROM usuarios WHERE id = ?", (usuario_id,), one=True)
    if alvo is None:
        flash("Usuario nao encontrado.", "danger")
        return redirect(url_for("usuarios.listar"))

    if request.method == "POST":
        dados = _le_formulario(request.form)
        senha = request.form.get("senha") or ""
        erro = _valida(dados)

        # Senha em branco na edicao significa "manter a atual".
        if not erro and senha:
            erro = _valida_senha(senha, request.form.get("senha_confirmacao"))

        # Trava de seguranca: a loja nao pode ficar sem super administrador.
        if not erro and alvo["papel"] == "SUPERADMIN":
            if dados["papel"] != "SUPERADMIN" or not dados["ativo"]:
                if _quantos_superadmins_ativos() <= 1:
                    erro = ("Este e o unico super administrador ativo. "
                            "Promova outro usuario antes de rebaixar ou desativar este.")

        if erro:
            flash(erro, "danger")
            return _tela(dados, novo=False, usuario_id=usuario_id)

        try:
            db.execute(
                """UPDATE usuarios
                      SET nome = ?, usuario = ?, papel = ?, vendedor_id = ?, ativo = ?
                    WHERE id = ?""",
                (
                    dados["nome"],
                    dados["usuario"],
                    dados["papel"],
                    dados["vendedor_id"],
                    dados["ativo"],
                    usuario_id,
                ),
            )
        except sqlite3.IntegrityError:
            flash("Ja existe outro usuario com o login '%s'." % dados["usuario"], "danger")
            return _tela(dados, novo=False, usuario_id=usuario_id)

        if senha:
            db.execute(
                "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                (hash_senha(senha), usuario_id),
            )
            flash("Senha redefinida.", "success")

        flash("Usuario atualizado.", "success")
        return redirect(url_for("usuarios.listar"))

    return _tela(alvo, novo=False, usuario_id=usuario_id)


@bp.route("/<int:usuario_id>/excluir", methods=["POST"])
@requer("usuarios.gerenciar")
def excluir(usuario_id):
    alvo = db.query("SELECT * FROM usuarios WHERE id = ?", (usuario_id,), one=True)
    eu = usuario_atual()

    if alvo is None:
        flash("Usuario nao encontrado.", "danger")
    elif alvo["id"] == eu["id"]:
        flash("Voce nao pode excluir o proprio usuario.", "danger")
    elif alvo["papel"] == "SUPERADMIN" and _quantos_superadmins_ativos() <= 1:
        flash("Nao e possivel excluir o unico super administrador do sistema.", "danger")
    else:
        db.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
        flash("Usuario '%s' excluido." % alvo["usuario"], "success")

    return redirect(url_for("usuarios.listar"))


@bp.route("/<int:usuario_id>/alternar", methods=["POST"])
@requer("usuarios.gerenciar")
def alternar(usuario_id):
    alvo = db.query("SELECT * FROM usuarios WHERE id = ?", (usuario_id,), one=True)
    eu = usuario_atual()

    if alvo is None:
        flash("Usuario nao encontrado.", "danger")
    elif alvo["id"] == eu["id"]:
        flash("Voce nao pode desativar o proprio usuario.", "danger")
    elif alvo["ativo"] and alvo["papel"] == "SUPERADMIN" and _quantos_superadmins_ativos() <= 1:
        flash("Nao e possivel desativar o unico super administrador.", "danger")
    else:
        novo_estado = 0 if alvo["ativo"] else 1
        db.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (novo_estado, usuario_id))
        flash("Usuario %s." % ("reativado" if novo_estado else "desativado"), "success")

    return redirect(url_for("usuarios.listar"))


# --- apoio ------------------------------------------------------------------

def _tela(dados, novo, usuario_id=None):
    return render_template(
        "usuarios/formulario.html",
        alvo=dados,
        novo=novo,
        usuario_id=usuario_id,
        papeis=PAPEIS,
        regras=REGRAS_POR_PAPEL,
        vendedores=db.query("SELECT id, nome FROM vendedores WHERE ativo = 1 ORDER BY nome"),
    )


def _le_formulario(form):
    papel = (form.get("papel") or "VENDEDOR").upper()
    vendedor_id = to_int(form.get("vendedor_id")) or None
    return {
        "nome": (form.get("nome") or "").strip(),
        "usuario": (form.get("usuario") or "").strip().lower(),
        "papel": papel if papel in PAPEIS else "VENDEDOR",
        # O vinculo com o cadastro de vendedor so faz sentido para o perfil VENDEDOR.
        "vendedor_id": vendedor_id if papel == "VENDEDOR" else None,
        "ativo": 1 if form.get("ativo") else 0,
    }


def _valida(dados):
    if not dados["nome"]:
        return "Informe o nome do usuario."
    if len(dados["usuario"]) < 3:
        return "O login precisa ter ao menos 3 caracteres."
    if not dados["usuario"].replace(".", "").replace("_", "").replace("-", "").isalnum():
        return "O login aceita apenas letras, numeros, ponto, hifen e underline."
    if dados["papel"] == "VENDEDOR" and not dados["vendedor_id"]:
        return ("Perfil Vendedor exige o vinculo com um cadastro de vendedor, "
                "para o sistema saber quais vendas e comissoes sao dele.")
    return None


def _valida_senha(senha, confirmacao):
    if len(senha or "") < 6:
        return "A senha precisa ter ao menos 6 caracteres."
    if senha != (confirmacao or ""):
        return "A confirmacao nao confere com a senha."
    return None


def _quantos_superadmins_ativos():
    return db.escalar(
        "SELECT COUNT(*) FROM usuarios WHERE papel = 'SUPERADMIN' AND ativo = 1"
    )
