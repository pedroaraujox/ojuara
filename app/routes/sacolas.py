"""Sacolas de consignacao externa: montagem, acompanhamento e acerto."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import meu_vendedor_id, pode, requer
from ..services import (
    ErroNegocio,
    montar_sacola,
    produtos_disponiveis_na_nf,
    registrar_acerto_sacola,
)
from ..utils import hoje_iso, to_int

bp = Blueprint("sacolas", __name__, url_prefix="/sacolas")


@bp.route("/")
@requer("sacolas.ver")
def listar():
    status = request.args.get("status") or ""

    # Vendedor so ve as proprias sacolas: filtro imposto no servidor.
    restrito = not pode("sacolas.gerenciar")
    vendedor_id = meu_vendedor_id() if restrito else request.args.get("vendedor_id")

    sql = """SELECT s.*, v.nome AS vendedor, nf.numero AS nf_numero,
                    (SELECT IFNULL(SUM(quantidade_saida), 0) FROM sacola_itens
                      WHERE sacola_id = s.id) AS pecas_saida,
                    (SELECT IFNULL(SUM(quantidade_vendida), 0) FROM sacola_itens
                      WHERE sacola_id = s.id) AS pecas_vendida,
                    (SELECT IFNULL(SUM(quantidade_devolvida), 0) FROM sacola_itens
                      WHERE sacola_id = s.id) AS pecas_devolvida
             FROM sacolas s
             JOIN vendedores v ON v.id = s.vendedor_id
             LEFT JOIN notas_fiscais nf ON nf.id = s.nota_fiscal_id
             WHERE 1 = 1"""
    params = []
    if status in ("ABERTA", "ACERTADA"):
        sql += " AND s.status = ?"
        params.append(status)
    if vendedor_id:
        sql += " AND s.vendedor_id = ?"
        params.append(vendedor_id)
    sql += " ORDER BY s.status ASC, s.data_saida DESC, s.id DESC"

    sacolas = db.query(sql, params)

    return render_template(
        "sacolas/listar.html",
        sacolas=sacolas,
        status=status,
        restrito=restrito,
        vendedor_id=str(vendedor_id or ""),
        vendedores=db.query("SELECT id, nome FROM vendedores ORDER BY nome"),
    )


@bp.route("/nova", methods=["GET", "POST"])
@requer("sacolas.gerenciar")
def nova():
    vendedores = db.query("SELECT id, nome FROM vendedores WHERE ativo = 1 ORDER BY nome")

    if request.method == "POST":
        nota_fiscal_id = to_int(request.form.get("nota_fiscal_id"))
        try:
            sacola_id = montar_sacola(request.form)
        except ErroNegocio as erro:
            flash(str(erro), "danger")
            nota, disponiveis = _carregar_nf_e_disponiveis(nota_fiscal_id)
            _restaurar_quantidades_digitadas(request.form, disponiveis)
            return render_template(
                "sacolas/nova.html",
                nota=nota,
                disponiveis=disponiveis,
                notas_disponiveis=None if nota else _notas_com_disponivel(),
                dados={
                    "vendedor_id": request.form.get("vendedor_id") or "",
                    "data_saida": request.form.get("data_saida") or hoje_iso(),
                    "observacao": request.form.get("observacao") or "",
                },
                vendedores=vendedores,
            )
        flash("Sacola #%d montada com sucesso." % sacola_id, "success")
        return redirect(url_for("sacolas.detalhe", sacola_id=sacola_id))

    nota_fiscal_id = to_int(request.args.get("nota_fiscal_id"))
    nota, disponiveis = _carregar_nf_e_disponiveis(nota_fiscal_id)
    if nota_fiscal_id and nota is None:
        flash("Nota fiscal de entrada nao encontrada ou sem produtos disponiveis.", "danger")

    return render_template(
        "sacolas/nova.html",
        nota=nota,
        disponiveis=disponiveis,
        notas_disponiveis=None if nota else _notas_com_disponivel(),
        dados={"vendedor_id": "", "data_saida": hoje_iso(), "observacao": ""},
        vendedores=vendedores,
    )


# --- apoio --------------------------------------------------------------

def _notas_com_disponivel():
    """NFs de entrada que ainda tem algum produto disponivel para sacola."""
    notas = db.query(
        "SELECT * FROM notas_fiscais WHERE tipo = 'ENTRADA' AND ativa = 1 ORDER BY id DESC"
    )
    return [nota for nota in notas if produtos_disponiveis_na_nf(nota["id"])]


def _carregar_nf_e_disponiveis(nota_fiscal_id):
    """Retorna (nota, disponiveis); (None, []) se a NF nao existir ou nao tiver saldo."""
    if not nota_fiscal_id:
        return None, []
    nota = db.query(
        "SELECT * FROM notas_fiscais WHERE id = ? AND tipo = 'ENTRADA' AND ativa = 1",
        (nota_fiscal_id,),
        one=True,
    )
    if nota is None:
        return None, []
    disponiveis = produtos_disponiveis_na_nf(nota_fiscal_id)
    if not disponiveis:
        return None, []
    return nota, disponiveis


def _restaurar_quantidades_digitadas(form, disponiveis):
    """Repoe no template os valores que o operador ja tinha digitado, para
    que um erro de validacao nao obrigue a preencher tudo de novo."""
    ids = form.getlist("produto_id[]")
    quantidades = form.getlist("quantidade[]")
    digitadas = {}
    for indice, produto_id in enumerate(ids):
        if indice < len(quantidades) and quantidades[indice]:
            digitadas[to_int(produto_id)] = quantidades[indice]
    for produto in disponiveis:
        produto["quantidade_digitada"] = digitadas.get(produto["id"], "")


@bp.route("/<int:sacola_id>")
@requer("sacolas.ver")
def detalhe(sacola_id):
    sacola = db.query(
        """SELECT s.*, v.nome AS vendedor, v.telefone, nf.numero AS nf_numero
           FROM sacolas s
           JOIN vendedores v ON v.id = s.vendedor_id
           LEFT JOIN notas_fiscais nf ON nf.id = s.nota_fiscal_id
           WHERE s.id = ?""",
        (sacola_id,),
        one=True,
    )
    if sacola is None:
        flash("Sacola nao encontrada.", "danger")
        return redirect(url_for("sacolas.listar"))

    if not pode("sacolas.gerenciar") and sacola["vendedor_id"] != meu_vendedor_id():
        abort(403)

    itens = db.query(
        "SELECT * FROM sacola_itens WHERE sacola_id = ? ORDER BY codigo_fabricante, tamanho",
        (sacola_id,),
    )
    itens = [
        dict(item, em_posse=item["quantidade_saida"] - item["quantidade_vendida"]
             - item["quantidade_devolvida"])
        for item in itens
    ]
    totais = {
        "saida": sum(i["quantidade_saida"] for i in itens),
        "vendida": sum(i["quantidade_vendida"] for i in itens),
        "devolvida": sum(i["quantidade_devolvida"] for i in itens),
        "em_posse": sum(i["em_posse"] for i in itens),
    }

    return render_template(
        "sacolas/detalhe.html",
        sacola=sacola,
        itens=itens,
        totais=totais,
    )


@bp.route("/<int:sacola_id>/acerto", methods=["POST"])
@requer("sacolas.gerenciar")
def acerto(sacola_id):
    try:
        registrar_acerto_sacola(sacola_id, request.form)
        flash("Acerto registrado com sucesso.", "success")
    except ErroNegocio as erro:
        flash(str(erro), "danger")
    return redirect(url_for("sacolas.detalhe", sacola_id=sacola_id))
