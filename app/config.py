"""Configuracao da aplicacao."""

import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class Config:
    AMBIENTE = os.environ.get("OJUARA_AMBIENTE", "desenvolvimento").strip().lower()
    PRODUCAO = AMBIENTE == "producao"
    HTTPS_ATIVO = os.environ.get(
        "OJUARA_HTTPS", "1" if PRODUCAO else "0"
    ).strip() == "1"
    PROXY_CONFIAVEL = os.environ.get(
        "OJUARA_PROXY_CONFIAVEL", "1" if PRODUCAO else "0"
    ).strip() == "1"
    SECRET_KEY = os.environ.get("OJUARA_SECRET_KEY", "ojuara-dev-secret-key")

    DATABASE = os.environ.get("OJUARA_DATABASE", os.path.join(BASE_DIR, "data", "ojuara.db"))
    DATA_DIR = os.path.dirname(DATABASE)

    # Popula o banco com dados de demonstracao na primeira execucao.
    SEED_DEMO = not PRODUCAO and os.environ.get("OJUARA_SEED", "1") != "0"

    # Credenciais do super administrador criado na primeira execucao.
    # Troque a senha pelo sistema (menu do usuario > Minha senha) apos entrar.
    SUPERADMIN_LOGIN = os.environ.get("OJUARA_SUPERADMIN", "superadmin")
    SUPERADMIN_SENHA = os.environ.get("OJUARA_SUPERADMIN_SENHA", "Ojuara@2026")

    NOME_LOJA = "Ojuara Lingerie"
    EMPRESA = "Outbox Tech"

    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = not PRODUCAO

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = HTTPS_ATIVO
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    PREFERRED_URL_SCHEME = "https" if HTTPS_ATIVO else "http"

    LOGIN_MAX_TENTATIVAS = 5
    LOGIN_BLOQUEIO_MINUTOS = 15
