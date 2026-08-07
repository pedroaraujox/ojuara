"""Relatorios: comissao por vendedor no mes e posicao de estoque."""

from datetime import date

from flask import Blueprint, render_template, request

from .. import db
from ..auth import meu_vendedor_id, pode, requer
from ..utils import (
    FORMAS_PAGAMENTO,
    competencia_atual,
    intervalo_mes,
    rotulo_competencia,
    soma_meses,
)

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")


@bp.route("/comissoes")
@requer("relatorios.comissoes")
def comissoes():
    competencia = request.args.get("mes") or competencia_atual()
    inicio, fim = intervalo_mes(competencia)

    # Vendedor ve apenas a propria linha; admin ve a loja inteira.
    somente_meu = not pode("relatorios.ver")
    filtro_vendedor = ""
    parametros = [inicio, fim]
    if somente_meu:
        filtro_vendedor = " WHERE e.id = ?"
        parametros.append(meu_vendedor_id() or 0)

    linhas = db.query(
        """SELECT e.id, e.nome, e.percentual_comissao,
                  COUNT(v.id) AS qtd_vendas,
                  IFNULL(SUM(v.total), 0)          AS total_vendido,
                  IFNULL(SUM(v.comissao_valor), 0) AS comissao,
                  IFNULL(SUM(CASE WHEN v.forma_pagamento = 'CREDIARIO'
                                  THEN v.total ELSE 0 END), 0) AS total_crediario
           FROM vendedores e
           LEFT JOIN vendas v
                  ON v.vendedor_id = e.id
                 AND v.cancelada = 0
                 AND v.data BETWEEN ? AND ?"""
        + filtro_vendedor
        + """
           GROUP BY e.id
           ORDER BY total_vendido DESC, e.nome ASC""",
        parametros,
    )

    totais = {
        "vendas": sum(l["qtd_vendas"] for l in linhas),
        "vendido": sum(l["total_vendido"] for l in linhas),
        "comissao": sum(l["comissao"] for l in linhas),
    }
    maior = max([l["total_vendido"] for l in linhas], default=0) or 1

    sql_forma = """SELECT forma_pagamento, COUNT(*) AS qtd, SUM(total) AS total
                   FROM vendas
                   WHERE cancelada = 0 AND data BETWEEN ? AND ?"""
    parametros_forma = [inicio, fim]
    if somente_meu:
        sql_forma += " AND vendedor_id = ?"
        parametros_forma.append(meu_vendedor_id() or 0)
    sql_forma += " GROUP BY forma_pagamento ORDER BY total DESC"
    por_forma = db.query(sql_forma, parametros_forma)

    return render_template(
        "relatorios/comissoes.html",
        somente_meu=somente_meu,
        linhas=linhas,
        totais=totais,
        maior=maior,
        por_forma=por_forma,
        competencia=competencia,
        rotulo=rotulo_competencia(competencia),
        competencias=_competencias(),
        formas=FORMAS_PAGAMENTO,
        inicio=inicio,
        fim=fim,
    )


@bp.route("/estoque")
@requer("relatorios.ver")
def estoque():
    ordem = request.args.get("ordem") or "valor"
    coluna = {
        "valor": "(estoque * preco_custo) DESC",
        "estoque": "estoque DESC",
        "nome": "nome ASC",
        "codigo": "codigo_fabricante ASC",
    }.get(ordem, "(estoque * preco_custo) DESC")

    produtos = db.query(
        "SELECT * FROM produtos WHERE ativo = 1 ORDER BY %s" % coluna
    )
    totais = {
        "itens": len(produtos),
        "pecas": sum(p["estoque"] for p in produtos),
        "custo": sum(p["estoque"] * p["preco_custo"] for p in produtos),
        "venda": sum(p["estoque"] * p["preco_venda"] for p in produtos),
    }
    totais["margem"] = totais["venda"] - totais["custo"]

    # Fornecedor e um dado da NF, nao do produto: soma-se o que ja foi
    # comprado (entradas lancadas) por NF.fornecedor, usando o custo atual
    # de cada produto para estimar o valor.
    por_fornecedor = db.query(
        """SELECT CASE WHEN nf.fornecedor = '' THEN '(sem fornecedor)' ELSE nf.fornecedor END
                    AS fornecedor,
                  COUNT(*) AS lancamentos, SUM(m.quantidade) AS pecas,
                  SUM(m.quantidade * p.preco_custo) AS custo
           FROM movimentacoes m
           JOIN notas_fiscais nf ON nf.id = m.nota_fiscal_id
           JOIN produtos p ON p.id = m.produto_id
           WHERE m.tipo = 'ENTRADA'
           GROUP BY fornecedor
           ORDER BY custo DESC"""
    )

    devolucoes = db.query(
        """SELECT codigo_fabricante, SUM(quantidade) AS pecas, COUNT(*) AS ocorrencias
           FROM movimentacoes
           WHERE tipo = 'DEVOLUCAO_FORNECEDOR'
           GROUP BY codigo_fabricante
           ORDER BY pecas DESC
           LIMIT 10"""
    )

    return render_template(
        "relatorios/estoque.html",
        produtos=produtos,
        totais=totais,
        por_fornecedor=por_fornecedor,
        devolucoes=devolucoes,
        ordem=ordem,
    )


def _competencias():
    """Ultimos 12 meses somados aos meses que ja tem venda registrada."""
    base = date.today().replace(day=1)
    meses = {soma_meses(base, -i).strftime("%Y-%m") for i in range(12)}
    for linha in db.query("SELECT DISTINCT substr(data, 1, 7) AS c FROM vendas"):
        meses.add(linha["c"])
    return [(m, rotulo_competencia(m)) for m in sorted(meses, reverse=True)]
