"""Fabrica da aplicacao Flask do sistema Ojuara."""

import os

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .utils import FORMAS_PAGAMENTO, TIPOS_MOVIMENTACAO, registra_filtros


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    if app.config.get("PRODUCAO"):
        segredo = os.environ.get("OJUARA_SECRET_KEY", "")
        if len(segredo) < 32 or segredo == "ojuara-dev-secret-key":
            raise RuntimeError(
                "OJUARA_SECRET_KEY precisa ter ao menos 32 caracteres em producao."
            )
        # Em producao ha exatamente um proxy reverso confiavel na frente da
        # aplicacao (Nginx Proxy Manager ou cloudflared local).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    registra_filtros(app)

    from . import db

    db.init_app(app)

    from . import auth

    auth.init_app(app)

    from .routes import (
        api,
        auth as auth_rotas,
        clientes,
        crediario,
        dashboard,
        estoque,
        produtos,
        relatorios,
        sacolas,
        saude,
        usuarios,
        vendas,
        vendedores,
    )

    app.register_blueprint(auth_rotas.bp)
    app.register_blueprint(usuarios.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(produtos.bp)
    app.register_blueprint(estoque.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(vendedores.bp)
    app.register_blueprint(vendas.bp)
    app.register_blueprint(crediario.bp)
    app.register_blueprint(relatorios.bp)
    app.register_blueprint(sacolas.bp)
    app.register_blueprint(saude.bp)
    app.register_blueprint(api.bp)

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return (
            render_template(
                "erro.html",
                codigo=404,
                mensagem="Pagina nao encontrada",
                detalhe="O endereco acessado nao existe neste sistema.",
            ),
            404,
        )

    @app.errorhandler(403)
    def sem_permissao(_erro):
        return (
            render_template(
                "erro.html",
                codigo=403,
                mensagem="Acesso negado",
                detalhe="Seu perfil de usuario nao tem permissao para acessar esta tela.",
            ),
            403,
        )

    @app.errorhandler(500)
    def erro_interno(_erro):
        return (
            render_template(
                "erro.html",
                codigo=500,
                mensagem="Erro interno",
                detalhe="Algo deu errado ao processar a solicitacao. Tente novamente.",
            ),
            500,
        )

    @app.after_request
    def cabecalhos_seguranca(resposta):
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        resposta.headers.setdefault(
            "Permissions-Policy", "camera=(self), microphone=(), geolocation=()"
        )
        if app.config.get("PRODUCAO"):
            resposta.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return resposta

    @app.context_processor
    def injeta_globais():
        return {
            "NOME_LOJA": app.config["NOME_LOJA"],
            "EMPRESA": app.config["EMPRESA"],
            "FORMAS_PAGAMENTO": FORMAS_PAGAMENTO,
            "TIPOS_MOVIMENTACAO": TIPOS_MOVIMENTACAO,
        }

    return app
