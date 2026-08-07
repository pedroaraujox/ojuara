"""Registro e consulta de vendas."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import meu_vendedor_id, pode, requer
from ..services import (
    ErroNegocio,
    cancelar_venda,
    produtos_disponiveis_vendedor,
    registrar_venda,
)
from ..utils import FORMAS_PAGAMENTO, hoje_iso, parse_data, soma_meses

bp = Blueprint("vendas", __name__, url_prefix="/vendas")


@bp.route("/")
@requer("vendas.criar")
def listar():
    inicio = request.args.get("inicio") or ""
    fim = request.args.get("fim") or ""
    forma = request.args.get("forma") or ""
    vendedor_id = request.args.get("vendedor_id") or ""
    cliente_id = request.args.get("cliente_id") or ""

    # Vendedor so enxerga as proprias vendas: o filtro e imposto no servidor,
    # nao apenas escondido na tela.
    restrito = not pode("vendas.ver_todas")
    if restrito:
        vendedor_id = str(meu_vendedor_id() or 0)

    sql = """SELECT v.*, c.nome AS cliente, e.nome AS vendedor
             FROM vendas v
             JOIN clientes c   ON c.id = v.cliente_id
             JOIN vendedores e ON e.id = v.vendedor_id
             WHERE 1 = 1"""
    params = []
    if inicio:
        sql += " AND v.data >= ?"
        params.append(inicio)
    if fim:
        sql += " AND v.data <= ?"
        params.append(fim)
    if forma in FORMAS_PAGAMENTO:
        sql += " AND v.forma_pagamento = ?"
        params.append(forma)
    if vendedor_id.isdigit():
        sql += " AND v.vendedor_id = ?"
        params.append(int(vendedor_id))
    if cliente_id.isdigit():
        sql += " AND v.cliente_id = ?"
        params.append(int(cliente_id))
    sql += " ORDER BY v.data DESC, v.id DESC LIMIT 300"

    vendas = db.query(sql, params)
    totais = {
        "qtd": sum(1 for v in vendas if not v["cancelada"]),
        "total": sum(v["total"] for v in vendas if not v["cancelada"]),
        "comissao": sum(v["comissao_valor"] for v in vendas if not v["cancelada"]),
    }

    return render_template(
        "vendas/listar.html",
        vendas=vendas,
        totais=totais,
        inicio=inicio,
        fim=fim,
        forma=forma,
        vendedor_id=vendedor_id,
        cliente_id=cliente_id,
        restrito=restrito,
        vendedores=db.query("SELECT id, nome FROM vendedores ORDER BY nome"),
        clientes=db.query("SELECT id, nome FROM clientes ORDER BY nome"),
    )


@bp.route("/nova", methods=["GET", "POST"])
@requer("vendas.criar")
def nova():
    if request.method == "POST":
        formulario = request.form
        if not pode("vendas.ver_todas"):
            # Vendedor sempre registra em seu proprio nome, venha o que vier no POST.
            formulario = request.form.copy()
            formulario["vendedor_id"] = str(meu_vendedor_id() or 0)
        try:
            venda_id = registrar_venda(formulario)
        except ErroNegocio as erro:
            flash(str(erro), "danger")
            return _tela_nova(formulario)
        flash("Venda #%d registrada com sucesso." % venda_id, "success")
        return redirect(url_for("vendas.detalhe", venda_id=venda_id))

    return _tela_nova(None)


@bp.route("/<int:venda_id>")
@requer("vendas.criar")
def detalhe(venda_id):
    venda = db.query(
        """SELECT v.*, c.nome AS cliente, c.telefone, c.endereco,
                  e.nome AS vendedor
           FROM vendas v
           JOIN clientes c   ON c.id = v.cliente_id
           JOIN vendedores e ON e.id = v.vendedor_id
           WHERE v.id = ?""",
        (venda_id,),
        one=True,
    )
    if venda is None:
        flash("Venda nao encontrada.", "danger")
        return redirect(url_for("vendas.listar"))

    if not pode("vendas.ver_todas") and venda["vendedor_id"] != meu_vendedor_id():
        abort(403)

    itens = db.query("SELECT * FROM venda_itens WHERE venda_id = ? ORDER BY id", (venda_id,))
    parcelas = db.query(
        "SELECT * FROM parcelas WHERE venda_id = ? ORDER BY numero", (venda_id,)
    )
    return render_template(
        "vendas/detalhe.html",
        venda=venda,
        itens=itens,
        parcelas=parcelas,
        hoje=hoje_iso(),
    )


@bp.route("/<int:venda_id>/cancelar", methods=["POST"])
@requer("vendas.cancelar")
def cancelar(venda_id):
    try:
        cancelar_venda(venda_id)
        flash("Venda #%d cancelada. Quantidades devolvidas a origem." % venda_id, "success")
    except ErroNegocio as erro:
        flash(str(erro), "danger")
    return redirect(url_for("vendas.detalhe", venda_id=venda_id))


def _tela_nova(form):
    """Monta a tela de nova venda, reaproveitando o que ja foi digitado."""
    hoje = hoje_iso()
    itens_digitados = []
    if form:
        codigos = form.getlist("codigo[]")
        tamanhos = form.getlist("tamanho[]")
        cores = form.getlist("cor[]")
        quantidades = form.getlist("quantidade[]")
        precos = form.getlist("preco[]")
        for indice, codigo in enumerate(codigos):
            if not (codigo or "").strip():
                continue
            itens_digitados.append(
                {
                    "codigo": codigo.strip().upper(),
                    "tamanho": (tamanhos[indice] if indice < len(tamanhos) else "").strip().upper(),
                    "cor": (cores[indice] if indice < len(cores) else "").strip(),
                    "quantidade": quantidades[indice] if indice < len(quantidades) else "1",
                    "preco": precos[indice] if indice < len(precos) else "",
                }
            )

    # Vendedor nao escolhe o vendedor da venda: e sempre ele proprio.
    vendedor_travado = not pode("vendas.ver_todas")
    if vendedor_travado:
        vendedores = db.query(
            "SELECT id, nome FROM vendedores WHERE id = ?", (meu_vendedor_id(),)
        )
    else:
        vendedores = db.query(
            "SELECT id, nome FROM vendedores WHERE ativo = 1 ORDER BY nome"
        )

    dados = {
        # No GET, aceita ?cliente_id= vindo da ficha do cliente.
        "cliente_id": (form.get("cliente_id") if form else request.args.get("cliente_id")) or "",
        "vendedor_id": str(meu_vendedor_id() or "") if vendedor_travado
                       else ((form.get("vendedor_id") if form else "") or ""),
        "forma_pagamento": (form.get("forma_pagamento") if form else "") or "DINHEIRO",
        "data": (form.get("data") if form else "") or hoje,
        "desconto": (form.get("desconto") if form else "") or "0",
        "qtd_parcelas": (form.get("qtd_parcelas") if form else "") or "2",
        "observacao": (form.get("observacao") if form else "") or "",
    }
    vencimento_padrao = (form.get("primeiro_vencimento") if form else "") or soma_meses(
        parse_data(dados["data"]), 1
    ).isoformat()
    dados["primeiro_vencimento"] = vencimento_padrao
    produtos = produtos_disponiveis_vendedor(dados["vendedor_id"])

    return render_template(
        "vendas/nova.html",
        dados=dados,
        itens_digitados=itens_digitados,
        clientes=db.query("SELECT id, nome FROM clientes WHERE ativo = 1 ORDER BY nome"),
        vendedores=vendedores,
        vendedor_travado=vendedor_travado,
        produtos=[dict(produto) for produto in produtos],
    )
