"""Login, logout e troca da propria senha."""

from urllib.parse import urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import check_password_hash

from .. import db
from ..auth import autenticar, encerrar_sessao, hash_senha, iniciar_sessao, usuario_atual

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if usuario_atual() is not None:
        return redirect(url_for("dashboard.index"))

    proximo = request.args.get("proximo") or ""

    if request.method == "POST":
        login_informado = (request.form.get("usuario") or "").strip()
        usuario = autenticar(login_informado, request.form.get("senha"))
        if usuario is None:
            # Mensagem generica: nao revela se o usuario existe.
            flash("Usuario ou senha invalidos.", "danger")
            return render_template("auth/login.html", usuario_informado=login_informado,
                                   proximo=proximo)

        iniciar_sessao(usuario)
        flash("Bem-vindo(a), %s!" % usuario["nome"], "success")
        return redirect(_destino_seguro(request.form.get("proximo")))

    return render_template("auth/login.html", usuario_informado="", proximo=proximo)


@bp.route("/logout", methods=["POST"])
def logout():
    encerrar_sessao()
    flash("Sessao encerrada.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/minha-senha", methods=["GET", "POST"])
def minha_senha():
    usuario = usuario_atual()

    if request.method == "POST":
        atual = request.form.get("senha_atual") or ""
        nova = request.form.get("senha_nova") or ""
        confirmacao = request.form.get("senha_confirmacao") or ""

        if not check_password_hash(usuario["senha_hash"], atual):
            flash("A senha atual esta incorreta.", "danger")
        elif len(nova) < 6:
            flash("A nova senha precisa ter ao menos 6 caracteres.", "danger")
        elif nova != confirmacao:
            flash("A confirmacao nao confere com a nova senha.", "danger")
        else:
            db.execute(
                "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                (hash_senha(nova), usuario["id"]),
            )
            flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/minha_senha.html")


def _destino_seguro(destino):
    """So aceita redirecionamento interno, nunca para outro dominio."""
    if not destino:
        return url_for("dashboard.index")
    partes = urlparse(destino)
    if partes.scheme or partes.netloc or not destino.startswith("/"):
        return url_for("dashboard.index")
    return destino
