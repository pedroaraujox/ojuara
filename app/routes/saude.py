"""Verificacao minima usada pelo Docker e pelo proxy reverso."""

from flask import Blueprint, jsonify

from .. import db

bp = Blueprint("saude", __name__)


@bp.get("/saude")
def verificar():
    db.escalar("SELECT 1")
    return jsonify(status="ok")
