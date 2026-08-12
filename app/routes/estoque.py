"""Entrada por selecao do catalogo, devolucao ao fornecedor e historico.

Todas as movimentacoes (entrada, baixa, devolucao) sao sempre
lancadas atreladas a um numero de Nota Fiscal: e ela que agrupa os produtos
lancados numa mesma remessa (ver `_processa_lote` e `notas_fiscais.py`).
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import requer
from ..services import (
    ErroNegocio,
    aplicar_lote,
    coletar_lote,
    obter_ou_criar_nota_fiscal,
    produtos_disponiveis_na_nf,
    validar_lote,
)
from ..utils import TIPOS_MOVIMENTACAO, hoje_iso, parse_data

bp = Blueprint("estoque", __name__, url_prefix="/estoque")


@bp.route("/baixa", methods=["GET", "POST"])
@requer("estoque.movimentar")
def baixa():
    """Baixa por codigo do fabricante + tamanho, sem selecionar produto a produto."""
    if request.method == "POST":
        resultado = _processa_lote(
            request.form,
            tipo="BAIXA",
            rotulo="Baixa de estoque",
        )
        if resultado is not None:
            return resultado

    return render_template(
        "estoque/baixa.html",
        titulo="Baixa de estoque em lote",
        subtitulo="Informe a NF e os produtos do catalogo que saem do estoque.",
        acao=url_for("estoque.baixa"),
        tipo="BAIXA",
        cor="warning",
        rotulo_botao="Confirmar baixa",
        rotulo_fornecedor="Destino / observacao da NF",
        motivos=[
            "Peca danificada",
            "Perda / extravio",
            "Uso em vitrine",
            "Brinde / cortesia",
            "Ajuste de inventario",
        ],
        ultimas=_ultimas("BAIXA"),
    )


@bp.route("/devolucao", methods=["GET", "POST"])
@requer("estoque.movimentar")
def devolucao():
    """Devolucao de pecas encalhadas ao fornecedor."""
    nota_fiscal_id = request.form.get("nota_fiscal_id") if request.method == "POST" else request.args.get("nota_fiscal_id")
    nota = None
    disponiveis = []
    if str(nota_fiscal_id or "").isdigit():
        nota = db.query(
            "SELECT * FROM notas_fiscais WHERE id = ? AND tipo = 'ENTRADA' AND ativa = 1",
            (int(nota_fiscal_id),), one=True,
        )
        if nota:
            disponiveis = produtos_disponiveis_na_nf(nota["id"])
    if request.method == "POST":
        if not nota:
            flash("Selecione uma NF de entrada ativa.", "danger")
        else:
            permitidos = {item["id"]: item["disponivel"] for item in disponiveis}
            ids = request.form.getlist("produto_id[]")
            quantidades = request.form.getlist("quantidade[]")
            invalido = False
            for indice, produto_id in enumerate(ids):
                quantidade = int(quantidades[indice]) if indice < len(quantidades) and quantidades[indice].isdigit() else 0
                if quantidade > 0 and (not produto_id.isdigit() or quantidade > permitidos.get(int(produto_id), 0)):
                    invalido = True
                    break
            if invalido:
                flash("Ha item fora da NF selecionada ou quantidade acima do disponivel.", "danger")
            else:
                resultado = _processa_lote(
                    request.form, tipo="DEVOLUCAO_FORNECEDOR", rotulo="Devolucao ao fornecedor"
                )
                if resultado is not None:
                    return resultado

    return render_template(
        "estoque/devolucao.html",
        titulo="Devolucao ao fornecedor",
        nota=nota,
        disponiveis=disponiveis,
        notas_disponiveis=db.query(
            "SELECT * FROM notas_fiscais WHERE tipo = 'ENTRADA' AND ativa = 1 ORDER BY id DESC"
        ) if not nota else None,
        motivos=[
            "Peca encalhada",
            "Colecao anterior",
            "Defeito de fabrica",
            "Grade incompleta",
            "Troca por outro modelo",
        ],
    )


@bp.route("/entrada", methods=["GET", "POST"])
@requer("estoque.movimentar")
def entrada():
    """Entrada de NF selecionando variantes exatas no catalogo."""
    if request.method == "POST":
        resultado = _processa_lote(
            request.form,
            tipo="ENTRADA",
            rotulo="Entrada de NF",
            exigir_estoque=False,
            exigir_numero_nf_numerico=True,
        )
        if resultado is not None:
            return resultado

    return render_template(
        "estoque/entrada_nf.html",
        titulo="Entrada de NF",
        subtitulo="Informe a NF de compra e os produtos do catalogo que chegaram.",
        motivos=[
            "Compra de mercadoria",
            "Reposicao de grade",
            "Retorno de consignacao",
            "Ajuste de inventario",
        ],
    )


@bp.route("/movimentacoes")
@requer("estoque.ver")
def movimentacoes():
    tipo = request.args.get("tipo") or ""
    busca = (request.args.get("busca") or "").strip()
    inicio = request.args.get("inicio") or ""
    fim = request.args.get("fim") or ""

    sql = """SELECT m.*, p.nome AS produto_nome, p.tamanho, p.cor,
                    nf.numero AS nf_numero
             FROM movimentacoes m
             JOIN produtos p ON p.id = m.produto_id
             LEFT JOIN notas_fiscais nf ON nf.id = m.nota_fiscal_id
             WHERE 1 = 1"""
    params = []

    if tipo in TIPOS_MOVIMENTACAO:
        sql += " AND m.tipo = ?"
        params.append(tipo)
    if busca:
        sql += " AND (m.codigo_fabricante LIKE ? OR p.nome LIKE ? OR m.documento LIKE ?)"
        curinga = "%%%s%%" % busca
        params += [curinga, curinga, curinga]
    if inicio:
        sql += " AND m.data >= ?"
        params.append("%s 00:00:00" % inicio)
    if fim:
        sql += " AND m.data <= ?"
        params.append("%s 23:59:59" % fim)

    sql += " ORDER BY m.id DESC LIMIT 300"
    linhas = db.query(sql, params)

    resumo = {}
    for linha in linhas:
        resumo[linha["tipo"]] = resumo.get(linha["tipo"], 0) + linha["quantidade"]

    return render_template(
        "estoque/movimentacoes.html",
        movimentacoes=linhas,
        tipo=tipo,
        busca=busca,
        inicio=inicio,
        fim=fim,
        resumo=resumo,
    )


@bp.route("/notas-fiscais")
@requer("notas_fiscais.ver")
def notas_fiscais():
    tipo = request.args.get("tipo") or ""
    status = request.args.get("status") or ""
    busca = (request.args.get("busca") or "").strip()

    sql = """SELECT nf.*,
                    (SELECT COUNT(*) FROM movimentacoes m WHERE m.nota_fiscal_id = nf.id)
                        AS itens,
                    (SELECT IFNULL(SUM(m.quantidade), 0) FROM movimentacoes m
                      WHERE m.nota_fiscal_id = nf.id) AS pecas
             FROM notas_fiscais nf
             WHERE 1 = 1"""
    params = []
    if tipo in ("ENTRADA", "BAIXA", "DEVOLUCAO_FORNECEDOR"):
        sql += " AND nf.tipo = ?"
        params.append(tipo)
    if status in ("ATIVA", "INATIVA"):
        sql += " AND nf.ativa = ?"
        params.append(1 if status == "ATIVA" else 0)
    if busca:
        sql += " AND (nf.numero LIKE ? OR nf.fornecedor LIKE ?)"
        curinga = "%%%s%%" % busca
        params += [curinga, curinga]
    sql += " ORDER BY nf.id DESC LIMIT 300"

    return render_template(
        "estoque/notas_fiscais.html",
        notas=db.query(sql, params),
        tipo=tipo,
        status=status,
        busca=busca,
    )


@bp.route("/notas-fiscais/<int:nota_id>/status", methods=["POST"])
@requer("estoque.movimentar")
def alterar_status_nota_fiscal(nota_id):
    nota = db.query("SELECT * FROM notas_fiscais WHERE id = ?", (nota_id,), one=True)
    if nota is None:
        flash("Nota fiscal nao encontrada.", "danger")
        return redirect(url_for("estoque.notas_fiscais"))

    ativa = 1 if request.form.get("ativa") == "1" else 0
    db.execute("UPDATE notas_fiscais SET ativa = ? WHERE id = ?", (ativa, nota_id))
    flash(
        "NF %s marcada como %s." % (nota["numero"], "ativa" if ativa else "inativa"),
        "success",
    )
    return redirect(request.referrer or url_for("estoque.notas_fiscais"))


@bp.route("/notas-fiscais/<int:nota_id>")
@requer("notas_fiscais.ver")
def nota_fiscal_detalhe(nota_id):
    nota = db.query("SELECT * FROM notas_fiscais WHERE id = ?", (nota_id,), one=True)
    if nota is None:
        flash("Nota fiscal nao encontrada.", "danger")
        return redirect(url_for("estoque.notas_fiscais"))

    itens = db.query(
        """SELECT m.*, p.nome AS produto_nome, p.tamanho, p.cor
           FROM movimentacoes m
           JOIN produtos p ON p.id = m.produto_id
           WHERE m.nota_fiscal_id = ?
           ORDER BY m.id""",
        (nota_id,),
    )
    total_pecas = sum(item["quantidade"] for item in itens)

    return render_template(
        "estoque/nota_fiscal_detalhe.html",
        nota=nota,
        itens=itens,
        total_pecas=total_pecas,
    )


# --- apoio ------------------------------------------------------------------

def _processa_lote(
    form, tipo, rotulo, exigir_estoque=True, exigir_numero_nf_numerico=False
):
    """Valida e aplica o lote, atrelado a uma NF. Retorna um redirect quando
    tudo deu certo."""
    numero_nf = (form.get("numero_nf") or "").strip()
    fornecedor = (form.get("fornecedor") or "").strip()
    data_nf = parse_data(form.get("data_nf"), padrao=None)
    data_nf = data_nf.isoformat() if data_nf else hoje_iso()

    if not numero_nf:
        flash("Informe o numero da NF para lancar esta movimentacao.", "danger")
        return None
    if exigir_numero_nf_numerico and not numero_nf.isdigit():
        flash("O numero da NF deve conter somente numeros.", "danger")
        return None

    itens = coletar_lote(form)
    observacao = (form.get("observacao") or "").strip()
    if not observacao:
        observacao = (form.get("motivo") or "").strip()

    validos, erros = validar_lote(itens, exigir_estoque=exigir_estoque)

    for erro in erros:
        flash(erro, "danger")

    if not validos:
        return None

    if erros:
        # Nada e aplicado pela metade: o usuario corrige e reenvia.
        flash("Nenhuma movimentacao foi gravada. Corrija os itens acima.", "warning")
        return None

    try:
        nota_fiscal_id = obter_ou_criar_nota_fiscal(
            numero_nf, tipo, data_nf, fornecedor=fornecedor, observacao=observacao
        )
        aplicar_lote(
            validos,
            tipo,
            documento="NF %s" % numero_nf,
            observacao=observacao,
            nota_fiscal_id=nota_fiscal_id,
        )
    except ErroNegocio as erro:
        flash(str(erro), "danger")
        return None

    pecas = sum(item["quantidade"] for item in validos)
    flash(
        "%s concluida na NF %s: %d peca(s) em %d SKU(s)."
        % (rotulo, numero_nf, pecas, len(validos)),
        "success",
    )
    for item in validos:
        produto = item["produto"]
        flash(
            "%s%s - %s: %d peca(s). Saldo atual: %s."
            % (
                produto["codigo_fabricante"],
                " (%s)" % produto["tamanho"] if produto["tamanho"] else "",
                produto["nome"],
                item["quantidade"],
                db.escalar("SELECT estoque FROM produtos WHERE id = ?", (produto["id"],)),
            ),
            "info",
        )

    destino = {
        "BAIXA": "estoque.baixa",
        "DEVOLUCAO_FORNECEDOR": "estoque.devolucao",
        "ENTRADA": "estoque.entrada",
    }[tipo]
    return redirect(url_for(destino))


@bp.context_processor
def _dados_auxiliares_lote():
    """Alimenta o autocomplete e a tabela de referencia do catalogo nas telas de lote."""
    return {
        "produtos_disponiveis": db.query(
            """SELECT DISTINCT codigo_fabricante, nome FROM produtos
               WHERE ativo = 1 ORDER BY codigo_fabricante"""
        ),
        "catalogo_referencia": db.query(
            """SELECT id, codigo_fabricante, nome, tamanho, cor FROM produtos
               WHERE ativo = 1 ORDER BY nome ASC, codigo_fabricante ASC, tamanho ASC"""
        ),
    }


def _ultimas(tipo, limite=10):
    return db.query(
        """SELECT m.*, p.nome AS produto_nome, nf.numero AS nf_numero
           FROM movimentacoes m
           JOIN produtos p ON p.id = m.produto_id
           LEFT JOIN notas_fiscais nf ON nf.id = m.nota_fiscal_id
           WHERE m.tipo = ?
           ORDER BY m.id DESC
           LIMIT ?""",
        (tipo, limite),
    )
