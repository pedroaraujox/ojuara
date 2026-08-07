"""Cadastro de vendedores e ficha individual."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import db
from ..auth import requer
from ..utils import (
    agora_iso,
    competencia_atual,
    cpf_valido,
    intervalo_mes,
    normaliza_cpf,
    parse_data_ou_none,
    rotulo_competencia,
    to_decimal,
)

bp = Blueprint("vendedores", __name__, url_prefix="/vendedores")


@bp.route("/")
@requer("vendedores.ver")
def listar():
    inicio, fim = intervalo_mes(competencia_atual())
    vendedores = db.query(
        """SELECT e.*,
                  (SELECT COUNT(*) FROM vendas v
                    WHERE v.vendedor_id = e.id AND v.cancelada = 0
                      AND v.data BETWEEN ? AND ?) AS vendas_mes,
                  (SELECT IFNULL(SUM(v.total), 0) FROM vendas v
                    WHERE v.vendedor_id = e.id AND v.cancelada = 0
                      AND v.data BETWEEN ? AND ?) AS total_mes,
                  (SELECT IFNULL(SUM(v.comissao_valor), 0) FROM vendas v
                    WHERE v.vendedor_id = e.id AND v.cancelada = 0
                      AND v.data BETWEEN ? AND ?) AS comissao_mes
           FROM vendedores e
           ORDER BY e.ativo DESC, e.nome ASC""",
        (inicio, fim, inicio, fim, inicio, fim),
    )
    return render_template(
        "vendedores/listar.html",
        vendedores=vendedores,
        rotulo_mes=rotulo_competencia(competencia_atual()),
    )


@bp.route("/novo", methods=["GET", "POST"])
@requer("vendedores.editar")
def novo():
    if request.method == "POST":
        dados = _le_formulario(request.form)
        erro = _valida(dados)
        if erro:
            flash(erro, "danger")
            return render_template("vendedores/formulario.html", vendedor=dados, novo=True)
        db.execute(
            """INSERT INTO vendedores
                   (nome, telefone, data_nascimento, cpf, rg, cep, rua, numero, bairro,
                    cidade, uf, percentual_comissao, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dados["nome"],
                dados["telefone"],
                dados["data_nascimento"],
                dados["cpf"],
                dados["rg"],
                dados["cep"],
                dados["rua"],
                dados["numero"],
                dados["bairro"],
                dados["cidade"],
                dados["uf"],
                dados["percentual_comissao"],
                dados["ativo"],
                agora_iso(),
            ),
        )
        flash("Vendedor cadastrado.", "success")
        return redirect(url_for("vendedores.listar"))

    vazio = {
        "nome": "", "telefone": "", "data_nascimento": "", "cpf": "", "rg": "",
        "cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "",
        "percentual_comissao": 5.0, "ativo": 1,
    }
    return render_template("vendedores/formulario.html", vendedor=vazio, novo=True)


@bp.route("/<int:vendedor_id>/editar", methods=["GET", "POST"])
@requer("vendedores.editar")
def editar(vendedor_id):
    vendedor = db.query("SELECT * FROM vendedores WHERE id = ?", (vendedor_id,), one=True)
    if vendedor is None:
        flash("Vendedor nao encontrado.", "danger")
        return redirect(url_for("vendedores.listar"))

    if request.method == "POST":
        dados = _le_formulario(request.form)
        erro = _valida(dados, vendedor_id=vendedor_id)
        if erro:
            flash(erro, "danger")
            return render_template(
                "vendedores/formulario.html",
                vendedor=dados,
                novo=False,
                vendedor_id=vendedor_id,
            )
        db.execute(
            """UPDATE vendedores
                  SET nome = ?, telefone = ?, data_nascimento = ?, cpf = ?, rg = ?,
                      cep = ?, rua = ?, numero = ?, bairro = ?, cidade = ?, uf = ?,
                      percentual_comissao = ?, ativo = ?
                WHERE id = ?""",
            (
                dados["nome"],
                dados["telefone"],
                dados["data_nascimento"],
                dados["cpf"],
                dados["rg"],
                dados["cep"],
                dados["rua"],
                dados["numero"],
                dados["bairro"],
                dados["cidade"],
                dados["uf"],
                dados["percentual_comissao"],
                dados["ativo"],
                vendedor_id,
            ),
        )
        flash("Vendedor atualizado.", "success")
        return redirect(url_for("vendedores.detalhe", vendedor_id=vendedor_id))

    return render_template(
        "vendedores/formulario.html", vendedor=vendedor, novo=False, vendedor_id=vendedor_id
    )


@bp.route("/<int:vendedor_id>")
@requer("vendedores.ver")
def detalhe(vendedor_id):
    vendedor = db.query("SELECT * FROM vendedores WHERE id = ?", (vendedor_id,), one=True)
    if vendedor is None:
        flash("Vendedor nao encontrado.", "danger")
        return redirect(url_for("vendedores.listar"))

    vendas = db.query(
        """SELECT v.*, c.nome AS cliente
           FROM vendas v
           JOIN clientes c ON c.id = v.cliente_id
           WHERE v.vendedor_id = ?
           ORDER BY v.data DESC, v.id DESC
           LIMIT 100""",
        (vendedor_id,),
    )
    por_mes = db.query(
        """SELECT substr(data, 1, 7) AS competencia, COUNT(*) AS qtd,
                  SUM(total) AS total, SUM(comissao_valor) AS comissao
           FROM vendas
           WHERE vendedor_id = ? AND cancelada = 0
           GROUP BY competencia
           ORDER BY competencia DESC""",
        (vendedor_id,),
    )
    return render_template(
        "vendedores/detalhe.html",
        vendedor=vendedor,
        vendas=vendas,
        por_mes=por_mes,
        rotulo_competencia=rotulo_competencia,
    )


def _le_formulario(form):
    return {
        "nome": (form.get("nome") or "").strip(),
        "telefone": (form.get("telefone") or "").strip(),
        "data_nascimento": (form.get("data_nascimento") or "").strip(),
        "cpf": (form.get("cpf") or "").strip(),
        "rg": (form.get("rg") or "").strip(),
        "cep": (form.get("cep") or "").strip(),
        "rua": (form.get("rua") or "").strip(),
        "numero": (form.get("numero") or "").strip(),
        "bairro": (form.get("bairro") or "").strip(),
        "cidade": (form.get("cidade") or "").strip(),
        "uf": (form.get("uf") or "").strip().upper()[:2],
        "percentual_comissao": to_decimal(form.get("percentual_comissao")),
        "ativo": 1 if form.get("ativo") else 0,
    }


def _valida(dados, vendedor_id=None):
    if not dados["nome"]:
        return "Informe o nome completo do vendedor."
    if not dados["data_nascimento"]:
        return "Informe a data de nascimento."
    nascimento = parse_data_ou_none(dados["data_nascimento"])
    if nascimento is None:
        return "Data de nascimento invalida."
    if nascimento > date.today():
        return "A data de nascimento nao pode estar no futuro."
    dados["data_nascimento"] = nascimento.isoformat()

    if not dados["cpf"]:
        return "Informe o CPF."
    if not cpf_valido(dados["cpf"]):
        return "CPF invalido. Confira os numeros digitados."
    dados["cpf"] = normaliza_cpf(dados["cpf"])
    if _cpf_em_uso(dados["cpf"], ignorar_id=vendedor_id):
        return "Ja existe um vendedor cadastrado com este CPF."

    if not dados["rg"]:
        return "Informe o RG."
    if not dados["cep"]:
        return "Informe o CEP."
    if not dados["rua"]:
        return "Informe a rua/logradouro."
    if not dados["numero"]:
        return "Informe o numero do endereco."
    if not dados["bairro"]:
        return "Informe o bairro."
    if not dados["cidade"]:
        return "Informe a cidade."
    if len(dados["uf"]) != 2:
        return "Informe a UF (2 letras)."

    if dados["percentual_comissao"] < 0 or dados["percentual_comissao"] > 100:
        return "A comissao deve ficar entre 0 e 100%."
    return None


def _cpf_em_uso(cpf, ignorar_id=None):
    sql = "SELECT id FROM vendedores WHERE cpf = ?"
    params = [cpf]
    if ignorar_id:
        sql += " AND id != ?"
        params.append(ignorar_id)
    return db.query(sql, params, one=True) is not None
