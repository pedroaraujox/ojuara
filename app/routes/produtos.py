"""Catalogo de produtos (cadastro puramente descritivo) e ficha por peca.

O catalogo nao guarda estoque nem fornecedor: qualquer produto pode ser
cadastrado com saldo zero a qualquer momento, e o saldo so muda depois,
atraves de uma Nota Fiscal lancada em Estoque (ver app/routes/estoque.py).
"""

import sqlite3

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import db
from ..auth import requer
from ..services import ErroNegocio, movimentar, obter_ou_criar_nota_fiscal
from ..utils import (
    CORES_PRODUTO,
    agora_iso,
    hoje_iso,
    normaliza_codigo,
    normaliza_tamanho,
    ordenar_por_tamanho,
    to_decimal,
    to_int,
)

bp = Blueprint("produtos", __name__, url_prefix="/produtos")


@bp.route("/importar-pdf", methods=["GET", "POST"])
@requer("produtos.editar")
def importar_pdf():
    """Revisa no navegador e grava produtos reconhecidos em catalogos PDF.

    A leitura do arquivo ocorre no proprio navegador. O servidor recebe apenas
    os dados ja revisados, evitando guardar o PDF (que pode conter informacoes
    comerciais) e mantendo o Flask sem dependencias pesadas de OCR.
    """
    if request.method == "GET":
        return render_template("produtos/importar_pdf.html")

    corpo = request.get_json(silent=True) or {}
    itens = corpo.get("produtos")
    if not isinstance(itens, list) or not itens:
        return jsonify(erro="Nenhum produto foi enviado para cadastro."), 400
    if len(itens) > 500:
        return jsonify(erro="O limite por importacao e de 500 produtos."), 400

    preparados = []
    erros = []
    chaves = set()
    repetidos_no_arquivo = 0
    for indice, item in enumerate(itens, start=1):
        if not isinstance(item, dict):
            erros.append("Linha %d: dados invalidos." % indice)
            continue
        dados = {
            "codigo_fabricante": normaliza_codigo(item.get("codigo_fabricante")),
            "nome": str(item.get("nome") or "").strip(),
            "tamanho": normaliza_tamanho(item.get("tamanho")),
            "cor": str(item.get("cor") or "").strip(),
            "preco_custo": to_decimal(item.get("preco_custo")),
            "preco_venda": to_decimal(item.get("preco_venda")),
            "ativo": 1,
        }
        erro = _valida(dados)
        if erro:
            erros.append("Linha %d (%s): %s" % (indice, dados["codigo_fabricante"] or "sem codigo", erro))
            continue
        chave = (dados["codigo_fabricante"], dados["tamanho"], dados["cor"].casefold())
        if chave in chaves:
            repetidos_no_arquivo += 1
            continue
        chaves.add(chave)
        preparados.append(dados)

    if erros:
        return jsonify(erro="Revise os itens destacados antes de importar.", erros=erros), 400

    conexao = db.get_db()
    novos = []
    existentes = 0
    for dados in preparados:
        if conexao.execute(
            """SELECT 1 FROM produtos
               WHERE codigo_fabricante = ? AND tamanho = ? AND lower(cor) = lower(?)""",
            (dados["codigo_fabricante"], dados["tamanho"], dados["cor"]),
        ).fetchone():
            existentes += 1
        else:
            novos.append(dados)

    try:
        for dados in novos:
            conexao.execute(
                """INSERT INTO produtos
                       (codigo_fabricante, nome, tamanho, cor, preco_custo,
                        preco_venda, estoque, estoque_minimo, ativo, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 0, 1, ?)""",
                (
                    dados["codigo_fabricante"], dados["nome"], dados["tamanho"],
                    dados["cor"], dados["preco_custo"], dados["preco_venda"], agora_iso(),
                ),
            )
        conexao.commit()
    except sqlite3.IntegrityError:
        conexao.rollback()
        return jsonify(erro="A importacao encontrou um conflito inesperado. Nada foi cadastrado."), 409

    ignorados = existentes + repetidos_no_arquivo
    mensagem = "%d produto(s) cadastrado(s) no catalogo com estoque zerado." % len(novos)
    if ignorados:
        mensagem += " %d produto(s) ja existente(s) ou repetido(s) foram pulados." % ignorados
    return jsonify(
        mensagem=mensagem,
        quantidade=len(novos),
        ignorados=ignorados,
        destino=url_for("produtos.listar"),
    )


@bp.route("/")
@requer("produtos.ver")
def listar():
    busca = (request.args.get("busca") or "").strip()
    situacao = request.args.get("situacao") or "todos"

    sql = "SELECT * FROM produtos WHERE 1 = 1"
    params = []

    if busca:
        sql += " AND (codigo_fabricante LIKE ? OR nome LIKE ? OR cor LIKE ?)"
        curinga = "%%%s%%" % busca
        params += [curinga, curinga, curinga]

    if situacao == "inativos":
        sql += " AND ativo = 0"
    else:
        situacao = "todos"
        sql += " AND ativo = 1"

    sql += " ORDER BY nome ASC, tamanho ASC"
    produtos = db.query(sql, params)

    totais = {
        "itens": len(produtos),
    }

    return render_template(
        "produtos/listar.html",
        produtos=produtos,
        busca=busca,
        situacao=situacao,
        totais=totais,
    )


@bp.route("/novo", methods=["GET", "POST"])
@requer("produtos.editar")
def novo():
    if request.method == "POST":
        dados = _le_formulario(request.form)

        erro = _valida(dados)
        if erro:
            flash(erro, "danger")
            return render_template("produtos/formulario.html", produto=dados, novo=True)

        try:
            produto_id = db.execute(
                """INSERT INTO produtos
                       (codigo_fabricante, nome, tamanho, cor,
                        preco_custo, preco_venda, estoque, estoque_minimo,
                        ativo, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
                (
                    dados["codigo_fabricante"],
                    dados["nome"],
                    dados["tamanho"],
                    dados["cor"],
                    dados["preco_custo"],
                    dados["preco_venda"],
                    dados["ativo"],
                    agora_iso(),
                ),
            )
        except sqlite3.IntegrityError:
            flash(
                "Ja existe um produto com o codigo %s, tamanho %s e cor %s."
                % (
                    dados["codigo_fabricante"],
                    dados["tamanho"] or "(sem tamanho)",
                    dados["cor"] or "(sem cor)",
                ),
                "danger",
            )
            return render_template("produtos/formulario.html", produto=dados, novo=True)

        flash(
            "Produto %s cadastrado no catalogo. Para dar entrada em estoque, use "
            "Notas Fiscais > Entrada de NF informando a NF de compra." % dados["codigo_fabricante"],
            "success",
        )
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    vazio = {
        "codigo_fabricante": "",
        "nome": "",
        "tamanho": "",
        "cor": "",
        "preco_custo": 0.0,
        "preco_venda": 0.0,
        "ativo": 1,
    }

    copiar_de = request.args.get("copiar_de")
    if copiar_de and copiar_de.isdigit():
        origem = db.query("SELECT * FROM produtos WHERE id = ?", (int(copiar_de),), one=True)
        if origem is not None:
            vazio.update(
                {
                    "codigo_fabricante": origem["codigo_fabricante"],
                    "nome": origem["nome"],
                    "cor": origem["cor"],
                    "preco_custo": origem["preco_custo"],
                    "preco_venda": origem["preco_venda"],
                }
            )

    return render_template("produtos/formulario.html", produto=vazio, novo=True)


@bp.route("/<int:produto_id>/editar", methods=["GET", "POST"])
@requer("produtos.editar")
def editar(produto_id):
    produto = db.query("SELECT * FROM produtos WHERE id = ?", (produto_id,), one=True)
    if produto is None:
        flash("Produto nao encontrado.", "danger")
        return redirect(url_for("produtos.listar"))

    if request.method == "POST":
        dados = _le_formulario(request.form)
        erro = _valida(dados)
        if erro:
            flash(erro, "danger")
            return render_template(
                "produtos/formulario.html", produto=dados, novo=False, produto_id=produto_id
            )

        try:
            db.execute(
                """UPDATE produtos
                      SET codigo_fabricante = ?, nome = ?, tamanho = ?, cor = ?,
                          preco_custo = ?, preco_venda = ?, ativo = ?
                    WHERE id = ?""",
                (
                    dados["codigo_fabricante"],
                    dados["nome"],
                    dados["tamanho"],
                    dados["cor"],
                    dados["preco_custo"],
                    dados["preco_venda"],
                    dados["ativo"],
                    produto_id,
                ),
            )
        except sqlite3.IntegrityError:
            flash(
                "Ja existe outro produto com o codigo %s, tamanho %s e cor %s."
                % (
                    dados["codigo_fabricante"],
                    dados["tamanho"] or "(sem tamanho)",
                    dados["cor"] or "(sem cor)",
                ),
                "danger",
            )
            return render_template(
                "produtos/formulario.html", produto=dados, novo=False, produto_id=produto_id
            )

        flash("Produto atualizado.", "success")
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    return render_template(
        "produtos/formulario.html", produto=produto, novo=False, produto_id=produto_id
    )


@bp.route("/<int:produto_id>")
@requer("produtos.ver")
def detalhe(produto_id):
    produto = db.query("SELECT * FROM produtos WHERE id = ?", (produto_id,), one=True)
    if produto is None:
        flash("Produto nao encontrado.", "danger")
        return redirect(url_for("produtos.listar"))

    movimentacoes = db.query(
        """SELECT m.*, nf.numero AS nf_numero
           FROM movimentacoes m
           LEFT JOIN notas_fiscais nf ON nf.id = m.nota_fiscal_id
           WHERE m.produto_id = ?
           ORDER BY m.id DESC LIMIT 100""",
        (produto_id,),
    )
    vendido = db.escalar(
        """SELECT SUM(i.quantidade) FROM venda_itens i
           JOIN vendas v ON v.id = i.venda_id
           WHERE i.produto_id = ? AND v.cancelada = 0""",
        (produto_id,),
    )

    grade = db.query(
        "SELECT * FROM produtos WHERE codigo_fabricante = ? AND id != ?",
        (produto["codigo_fabricante"], produto_id),
    )
    grade = ordenar_por_tamanho(grade)

    return render_template(
        "produtos/detalhe.html",
        produto=produto,
        movimentacoes=movimentacoes,
        vendido=vendido,
        grade=grade,
    )


@bp.route("/<int:produto_id>/entrada", methods=["POST"])
@requer("estoque.movimentar")
def entrada(produto_id):
    quantidade = to_int(request.form.get("quantidade"))
    numero_nf = (request.form.get("numero_nf") or "").strip()
    observacao = (request.form.get("observacao") or "").strip()

    if not numero_nf:
        flash("Informe o numero da NF para registrar a entrada.", "danger")
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    conexao = db.get_db()
    try:
        nota_fiscal_id = obter_ou_criar_nota_fiscal(numero_nf, "ENTRADA", hoje_iso())
        movimentar(
            produto_id,
            "ENTRADA",
            quantidade,
            documento="NF %s" % numero_nf,
            observacao=observacao or "Entrada avulsa",
            nota_fiscal_id=nota_fiscal_id,
        )
        conexao.commit()
        flash("Entrada de %d peca(s) registrada na NF %s." % (quantidade, numero_nf), "success")
    except ErroNegocio as erro:
        conexao.rollback()
        flash(str(erro), "danger")
    return redirect(url_for("produtos.detalhe", produto_id=produto_id))


@bp.route("/<int:produto_id>/alternar", methods=["POST"])
@requer("produtos.editar")
def alternar(produto_id):
    produto = db.query("SELECT ativo FROM produtos WHERE id = ?", (produto_id,), one=True)
    if produto is None:
        flash("Produto nao encontrado.", "danger")
        return redirect(url_for("produtos.listar"))
    novo_estado = 0 if produto["ativo"] else 1
    db.execute("UPDATE produtos SET ativo = ? WHERE id = ?", (novo_estado, produto_id))
    flash("Produto %s." % ("reativado" if novo_estado else "desativado"), "success")
    return redirect(request.referrer or url_for("produtos.listar"))


# --- apoio ------------------------------------------------------------------

def _le_formulario(form):
    cor = (form.get("cor") or "").strip()
    if cor == "__OUTRA__":
        cor = (form.get("cor_personalizada") or "").strip()
    return {
        "codigo_fabricante": normaliza_codigo(form.get("codigo_fabricante")),
        "nome": (form.get("nome") or "").strip(),
        "tamanho": normaliza_tamanho(form.get("tamanho")),
        "cor": cor,
        "preco_custo": to_decimal(form.get("preco_custo")),
        "preco_venda": to_decimal(form.get("preco_venda")),
        "ativo": 1 if form.get("ativo") else 0,
    }


def _valida(dados):
    if not dados["codigo_fabricante"]:
        return "Informe o codigo do produto."
    if len(dados["codigo_fabricante"]) != 5 or not dados["codigo_fabricante"].isdigit():
        return "O codigo do produto deve ter exatamente 5 numeros."
    if not dados["nome"]:
        return "Informe o nome do produto."
    if not dados["tamanho"]:
        return "Informe o tamanho do produto."
    if not dados["cor"]:
        return "Informe a cor do produto."
    if dados["preco_venda"] <= 0:
        return "O preco de venda deve ser maior que zero."
    if dados["preco_custo"] < 0:
        return "Valores negativos nao sao permitidos."
    return None


# Data usada nos templates de historico.
@bp.app_context_processor
def _hoje():
    return {"HOJE": hoje_iso(), "CORES_PRODUTO": CORES_PRODUTO}
