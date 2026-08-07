"""Configuracao da aplicacao."""

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class Config:
    SECRET_KEY = os.environ.get("OJUARA_SECRET_KEY", "ojuara-dev-secret-key")

    DATA_DIR = os.path.join(BASE_DIR, "data")
    DATABASE = os.path.join(DATA_DIR, "ojuara.db")

    # Popula o banco com dados de demonstracao na primeira execucao.
    SEED_DEMO = os.environ.get("OJUARA_SEED", "1") != "0"

    # Credenciais do super administrador criado na primeira execucao.
    # Troque a senha pelo sistema (menu do usuario > Minha senha) apos entrar.
    SUPERADMIN_LOGIN = os.environ.get("OJUARA_SUPERADMIN", "superadmin")
    SUPERADMIN_SENHA = os.environ.get("OJUARA_SUPERADMIN_SENHA", "Ojuara@2026")

    NOME_LOJA = "Ojuara Lingerie"
    EMPRESA = "Outbox Tech"

    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = True
