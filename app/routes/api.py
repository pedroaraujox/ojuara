"""Endpoints JSON usados pelas telas (busca de produto por codigo)."""

from flask import Blueprint, jsonify, request

from .. import db
from ..auth import meu_vendedor_id, pode, requer
from ..services import produtos_disponiveis_vendedor
from ..utils import normaliza_codigo, ordenar_por_tamanho

bp = Blueprint("api", __name__, url_prefix="/api")


def _resposta_variantes(linhas, codigo):
    if not linhas:
        return jsonify({"encontrado": False, "codigo": codigo}), 404

    pode_ver_custo = pode("custos.ver")
    variantes = []
    for linha in ordenar_por_tamanho(linhas):
        variante = dict(linha)
        if not pode_ver_custo:
            variante.pop("preco_custo", None)
        variantes.append(variante)

    return jsonify(
        {
            "encontrado": True,
            "codigo": codigo or variantes[0]["codigo_fabricante"],
            "variantes": variantes,
        }
    )


@bp.route("/produtos/<codigo>")
@requer("produtos.ver")
def produto_por_codigo(codigo):
    """Retorna todas as variantes (tamanhos) cadastradas para o codigo.

    A tela de lote usa isso para, ao digitar o codigo, oferecer o tamanho
    certo - direto quando so existe uma variante, por selecao quando existem
    varias.
    """
    codigo = normaliza_codigo(codigo)
    vendedor_id = request.args.get("vendedor_id")
    if vendedor_id is not None:
        vendedor_id = int(vendedor_id) if vendedor_id.isdigit() else 0
        if not pode("vendas.ver_todas"):
            vendedor_id = meu_vendedor_id() or 0
        linhas = produtos_disponiveis_vendedor(vendedor_id, codigo)
    else:
        linhas = db.query(
            """SELECT id, codigo_fabricante, nome, tamanho, cor, preco_venda,
                      preco_custo, estoque, ativo
               FROM produtos WHERE codigo_fabricante = ? AND ativo = 1""",
            (codigo,),
        )
    return _resposta_variantes(linhas, codigo)


@bp.route("/vendedores/<int:vendedor_id>/produtos-disponiveis")
@requer("vendas.criar")
def produtos_disponiveis_para_venda(vendedor_id):
    if not pode("vendas.ver_todas"):
        vendedor_id = meu_vendedor_id() or 0
    linhas = produtos_disponiveis_vendedor(vendedor_id)
    pode_ver_custo = pode("custos.ver")
    resultado = []
    for linha in linhas:
        item = dict(linha)
        if not pode_ver_custo:
            item.pop("preco_custo", None)
        resultado.append(item)
    return jsonify(resultado)


@bp.route("/produtos")
@requer("produtos.ver")
def buscar_produtos():
    termo = (request.args.get("q") or "").strip()
    if not termo:
        return jsonify([])
    curinga = "%%%s%%" % termo
    linhas = db.query(
        """SELECT codigo_fabricante, nome, tamanho, cor, preco_venda, estoque
           FROM produtos
           WHERE ativo = 1 AND (codigo_fabricante LIKE ? OR nome LIKE ?)
           ORDER BY codigo_fabricante
           LIMIT 15""",
        (curinga, curinga),
    )
    return jsonify([dict(linha) for linha in linhas])
