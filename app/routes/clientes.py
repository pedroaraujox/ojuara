"""Cadastro de clientes e ficha com compras e crediario."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import requer
from ..utils import agora_iso, hoje_iso, parse_data_ou_none, to_int

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@bp.route("/")
@requer("clientes.ver")
def listar():
    busca = (request.args.get("busca") or "").strip()
    sql = """SELECT c.*, v.nome AS captador_nome,
                    (SELECT COUNT(*) FROM vendas ve
                      WHERE ve.cliente_id = c.id AND ve.cancelada = 0) AS compras,
                    (SELECT IFNULL(SUM(p.valor), 0) FROM parcelas p
                      WHERE p.cliente_id = c.id AND p.pago = 0) AS devendo
             FROM clientes c
             LEFT JOIN vendedores v ON v.id = c.vendedor_captador_id
             WHERE 1 = 1"""
    params = []
    if busca:
        sql += " AND (c.nome LIKE ? OR c.telefone LIKE ? OR c.endereco LIKE ? OR c.cep LIKE ?)"
        curinga = "%%%s%%" % busca
        params += [curinga, curinga, curinga, curinga]
    sql += " ORDER BY c.nome ASC"

    return render_template(
        "clientes/listar.html", clientes=db.query(sql, params), busca=busca
    )


@bp.route("/novo", methods=["GET", "POST"])
@requer("clientes.editar")
def novo():
    if request.method == "POST":
        dados = _le_formulario(request.form)
        erro = _valida(dados)
        if erro:
            flash(erro, "danger")
            return render_template(
                "clientes/formulario.html", cliente=dados, novo=True,
                vendedores=_vendedores(),
            )

        cliente_id = db.execute(
            """INSERT INTO clientes
                   (nome, telefone, data_nascimento, cep, endereco, vendedor_captador_id,
                    observacao, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dados["nome"],
                dados["telefone"],
                dados["data_nascimento"],
                dados["cep"],
                dados["endereco"],
                dados["vendedor_captador_id"],
                dados["observacao"],
                dados["ativo"],
                agora_iso(),
            ),
        )
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

    vazio = {
        "nome": "", "telefone": "", "data_nascimento": "", "cep": "", "endereco": "",
        "vendedor_captador_id": None, "observacao": "", "ativo": 1,
    }
    return render_template(
        "clientes/formulario.html", cliente=vazio, novo=True, vendedores=_vendedores()
    )


@bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@requer("clientes.editar")
def editar(cliente_id):
    cliente = db.query("SELECT * FROM clientes WHERE id = ?", (cliente_id,), one=True)
    if cliente is None:
        flash("Cliente nao encontrado.", "danger")
        return redirect(url_for("clientes.listar"))

    if request.method == "POST":
        dados = _le_formulario(request.form)
        erro = _valida(dados)
        if erro:
            flash(erro, "danger")
            return render_template(
                "clientes/formulario.html", cliente=dados, novo=False, cliente_id=cliente_id,
                vendedores=_vendedores(),
            )
        db.execute(
            """UPDATE clientes
                  SET nome = ?, telefone = ?, data_nascimento = ?, cep = ?, endereco = ?,
                      vendedor_captador_id = ?, observacao = ?, ativo = ?
                WHERE id = ?""",
            (
                dados["nome"],
                dados["telefone"],
                dados["data_nascimento"],
                dados["cep"],
                dados["endereco"],
                dados["vendedor_captador_id"],
                dados["observacao"],
                dados["ativo"],
                cliente_id,
            ),
        )
        flash("Cliente atualizado.", "success")
        return redirect(url_for("clientes.detalhe", cliente_id=cliente_id))

    return render_template(
        "clientes/formulario.html", cliente=cliente, novo=False, cliente_id=cliente_id,
        vendedores=_vendedores(),
    )


@bp.route("/<int:cliente_id>")
@requer("clientes.ver")
def detalhe(cliente_id):
    cliente = db.query(
        """SELECT c.*, v.nome AS captador_nome
           FROM clientes c
           LEFT JOIN vendedores v ON v.id = c.vendedor_captador_id
           WHERE c.id = ?""",
        (cliente_id,),
        one=True,
    )
    if cliente is None:
        flash("Cliente nao encontrado.", "danger")
        return redirect(url_for("clientes.listar"))

    vendas = db.query(
        """SELECT v.*, e.nome AS vendedor
           FROM vendas v
           JOIN vendedores e ON e.id = v.vendedor_id
           WHERE v.cliente_id = ?
           ORDER BY v.data DESC, v.id DESC""",
        (cliente_id,),
    )
    parcelas = db.query(
        """SELECT p.*, v.data AS data_venda
           FROM parcelas p
           JOIN vendas v ON v.id = p.venda_id
           WHERE p.cliente_id = ?
           ORDER BY p.pago ASC, p.vencimento ASC""",
        (cliente_id,),
    )

    hoje = hoje_iso()
    resumo = {
        "compras": sum(1 for v in vendas if not v["cancelada"]),
        "total_comprado": sum(v["total"] for v in vendas if not v["cancelada"]),
        "em_aberto": sum(p["valor"] for p in parcelas if not p["pago"]),
        "vencido": sum(
            p["valor"] for p in parcelas if not p["pago"] and p["vencimento"] < hoje
        ),
    }

    return render_template(
        "clientes/detalhe.html",
        cliente=cliente,
        vendas=vendas,
        parcelas=parcelas,
        resumo=resumo,
        hoje=hoje,
    )


def _le_formulario(form):
    return {
        "nome": (form.get("nome") or "").strip(),
        "telefone": (form.get("telefone") or "").strip(),
        "data_nascimento": (form.get("data_nascimento") or "").strip(),
        "cep": (form.get("cep") or "").strip(),
        "endereco": (form.get("endereco") or "").strip(),
        "vendedor_captador_id": to_int(form.get("vendedor_captador_id")) or None,
        "observacao": (form.get("observacao") or "").strip(),
        "ativo": 1 if form.get("ativo") else 0,
    }


def _valida(dados):
    if not dados["nome"]:
        return "Informe o nome do cliente."
    if not dados["cep"]:
        return "Informe o CEP do cliente."
    if not dados["data_nascimento"]:
        return "Informe a data de nascimento do cliente."
    nascimento = parse_data_ou_none(dados["data_nascimento"])
    if nascimento is None:
        return "Data de nascimento invalida."
    if nascimento > date.today():
        return "A data de nascimento nao pode estar no futuro."
    dados["data_nascimento"] = nascimento.isoformat()
    return None


def _vendedores():
    return db.query("SELECT id, nome FROM vendedores WHERE ativo = 1 ORDER BY nome")
