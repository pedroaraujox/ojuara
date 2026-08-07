"""Carne do crediario: parcelas a receber e baixa de pagamento."""

from flask import Blueprint, flash, redirect, request, url_for

from .. import db
from ..auth import requer
from ..utils import parse_data

bp = Blueprint("crediario", __name__, url_prefix="/crediario")


@bp.route("/")
@requer("crediario.ver")
def listar():
    """A pagina independente foi retirada; parcelas ficam nas fichas relacionadas."""
    return redirect(url_for("vendas.listar"))


@bp.route("/<int:parcela_id>/pagar", methods=["POST"])
@requer("crediario.receber")
def pagar(parcela_id):
    parcela = db.query("SELECT * FROM parcelas WHERE id = ?", (parcela_id,), one=True)
    if parcela is None:
        flash("Parcela nao encontrada.", "danger")
        return redirect(url_for("crediario.listar"))
    if parcela["pago"]:
        flash("Parcela ja estava quitada.", "warning")
    else:
        data_pagamento = parse_data(request.form.get("data_pagamento")).isoformat()
        db.execute(
            "UPDATE parcelas SET pago = 1, data_pagamento = ? WHERE id = ?",
            (data_pagamento, parcela_id),
        )
        flash(
            "Parcela %d/%d quitada." % (parcela["numero"], parcela["total_parcelas"]),
            "success",
        )
    return redirect(request.referrer or url_for("crediario.listar"))


@bp.route("/<int:parcela_id>/estornar", methods=["POST"])
@requer("crediario.estornar")
def estornar(parcela_id):
    parcela = db.query("SELECT * FROM parcelas WHERE id = ?", (parcela_id,), one=True)
    if parcela is None:
        flash("Parcela nao encontrada.", "danger")
    elif not parcela["pago"]:
        flash("Parcela ja esta em aberto.", "warning")
    else:
        db.execute(
            "UPDATE parcelas SET pago = 0, data_pagamento = NULL WHERE id = ?",
            (parcela_id,),
        )
        flash("Pagamento estornado.", "success")
    return redirect(request.referrer or url_for("crediario.listar"))
