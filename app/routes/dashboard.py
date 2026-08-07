"""Painel inicial com os indicadores da loja."""

from flask import Blueprint, render_template

from .. import db
from ..auth import meu_vendedor_id, pode
from ..utils import competencia_atual, hoje_iso, intervalo_mes, rotulo_competencia

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    competencia = competencia_atual()
    inicio, fim = intervalo_mes(competencia)
    hoje = hoje_iso()

    # Vendedor recebe um painel proprio, sem faturamento da loja nem custos.
    if not pode("painel.gerencial"):
        return _painel_vendedor(competencia, inicio, fim, hoje)

    indicadores = {
        "produtos": db.escalar("SELECT COUNT(*) FROM produtos WHERE ativo = 1"),
        "pecas": db.escalar("SELECT SUM(estoque) FROM produtos WHERE ativo = 1"),
        "valor_custo": db.escalar(
            "SELECT SUM(estoque * preco_custo) FROM produtos WHERE ativo = 1", padrao=0.0
        ),
        "valor_venda": db.escalar(
            "SELECT SUM(estoque * preco_venda) FROM produtos WHERE ativo = 1", padrao=0.0
        ),
        "clientes": db.escalar("SELECT COUNT(*) FROM clientes WHERE ativo = 1"),
        "vendas_mes": db.escalar(
            "SELECT COUNT(*) FROM vendas WHERE cancelada = 0 AND data BETWEEN ? AND ?",
            (inicio, fim),
        ),
        "faturamento_mes": db.escalar(
            "SELECT SUM(total) FROM vendas WHERE cancelada = 0 AND data BETWEEN ? AND ?",
            (inicio, fim),
            padrao=0.0,
        ),
        "comissao_mes": db.escalar(
            """SELECT SUM(comissao_valor) FROM vendas
               WHERE cancelada = 0 AND data BETWEEN ? AND ?""",
            (inicio, fim),
            padrao=0.0,
        ),
        "a_receber": db.escalar(
            "SELECT SUM(valor) FROM parcelas WHERE pago = 0", padrao=0.0
        ),
        "vencidas_qtd": db.escalar(
            "SELECT COUNT(*) FROM parcelas WHERE pago = 0 AND vencimento < ?", (hoje,)
        ),
        "vencidas_valor": db.escalar(
            "SELECT SUM(valor) FROM parcelas WHERE pago = 0 AND vencimento < ?",
            (hoje,),
            padrao=0.0,
        ),
    }

    ultimas_vendas = db.query(
        """SELECT v.*, c.nome AS cliente, e.nome AS vendedor
           FROM vendas v
           JOIN clientes c   ON c.id = v.cliente_id
           JOIN vendedores e ON e.id = v.vendedor_id
           ORDER BY v.data DESC, v.id DESC
           LIMIT 8"""
    )

    ranking = db.query(
        """SELECT e.nome, COUNT(v.id) AS qtd, SUM(v.total) AS total,
                  SUM(v.comissao_valor) AS comissao
           FROM vendas v
           JOIN vendedores e ON e.id = v.vendedor_id
           WHERE v.cancelada = 0 AND v.data BETWEEN ? AND ?
           GROUP BY e.id
           ORDER BY total DESC""",
        (inicio, fim),
    )

    estoque_baixo = db.query(
        """SELECT * FROM produtos
           WHERE ativo = 1 AND estoque <= estoque_minimo
           ORDER BY estoque ASC, nome ASC
           LIMIT 10"""
    )

    mais_vendidos = db.query(
        """SELECT i.codigo_fabricante, i.descricao, SUM(i.quantidade) AS pecas,
                  SUM(i.subtotal) AS total
           FROM venda_itens i
           JOIN vendas v ON v.id = i.venda_id
           WHERE v.cancelada = 0 AND v.data BETWEEN ? AND ?
           GROUP BY i.codigo_fabricante
           ORDER BY pecas DESC
           LIMIT 6""",
        (inicio, fim),
    )

    proximas_parcelas = db.query(
        """SELECT p.*, c.nome AS cliente
           FROM parcelas p
           JOIN clientes c ON c.id = p.cliente_id
           WHERE p.pago = 0
           ORDER BY p.vencimento ASC
           LIMIT 8"""
    )

    aniversariantes_mes, aniversariantes_hoje = _aniversariantes()

    return render_template(
        "dashboard.html",
        indicadores=indicadores,
        ultimas_vendas=ultimas_vendas,
        ranking=ranking,
        estoque_baixo=estoque_baixo,
        mais_vendidos=mais_vendidos,
        proximas_parcelas=proximas_parcelas,
        aniversariantes_mes=aniversariantes_mes,
        aniversariantes_hoje=aniversariantes_hoje,
        hoje=hoje,
        rotulo_mes=rotulo_competencia(competencia),
    )


def _aniversariantes():
    """Clientes ativos que fazem aniversario no mes atual.

    Comparado por substring (posicoes 5-7 do 'YYYY-MM-DD') em vez de funcoes
    de data do SQLite para nao depender do fuso horario do 'now' do banco.
    """
    hoje = hoje_iso()
    mes_atual, dia_hoje = hoje[5:7], hoje[8:10]

    linhas = db.query(
        """SELECT id, nome, telefone, data_nascimento
           FROM clientes
           WHERE ativo = 1 AND data_nascimento != ''
             AND substr(data_nascimento, 6, 2) = ?
           ORDER BY substr(data_nascimento, 9, 2) ASC, nome ASC""",
        (mes_atual,),
    )

    aniversariantes_mes = []
    aniversariantes_hoje = []
    for linha in linhas:
        item = dict(linha)
        item["dia"] = linha["data_nascimento"][8:10]
        item["e_hoje"] = item["dia"] == dia_hoje
        aniversariantes_mes.append(item)
        if item["e_hoje"]:
            aniversariantes_hoje.append(item)

    return aniversariantes_mes, aniversariantes_hoje


def _painel_vendedor(competencia, inicio, fim, hoje):
    """Painel do perfil VENDEDOR: apenas os proprios numeros."""
    vendedor_id = meu_vendedor_id() or 0

    indicadores = {
        "vendas_mes": db.escalar(
            """SELECT COUNT(*) FROM vendas
               WHERE cancelada = 0 AND vendedor_id = ? AND data BETWEEN ? AND ?""",
            (vendedor_id, inicio, fim),
        ),
        "total_mes": db.escalar(
            """SELECT SUM(total) FROM vendas
               WHERE cancelada = 0 AND vendedor_id = ? AND data BETWEEN ? AND ?""",
            (vendedor_id, inicio, fim),
            padrao=0.0,
        ),
        "comissao_mes": db.escalar(
            """SELECT SUM(comissao_valor) FROM vendas
               WHERE cancelada = 0 AND vendedor_id = ? AND data BETWEEN ? AND ?""",
            (vendedor_id, inicio, fim),
            padrao=0.0,
        ),
        "pecas_mes": db.escalar(
            """SELECT SUM(i.quantidade) FROM venda_itens i
               JOIN vendas v ON v.id = i.venda_id
               WHERE v.cancelada = 0 AND v.vendedor_id = ? AND v.data BETWEEN ? AND ?""",
            (vendedor_id, inicio, fim),
        ),
    }
    indicadores["ticket_medio"] = (
        indicadores["total_mes"] / indicadores["vendas_mes"]
        if indicadores["vendas_mes"]
        else 0.0
    )

    minhas_vendas = db.query(
        """SELECT v.*, c.nome AS cliente
           FROM vendas v
           JOIN clientes c ON c.id = v.cliente_id
           WHERE v.vendedor_id = ?
           ORDER BY v.data DESC, v.id DESC
           LIMIT 10""",
        (vendedor_id,),
    )

    proximas_parcelas = db.query(
        """SELECT p.*, c.nome AS cliente
           FROM parcelas p
           JOIN clientes c ON c.id = p.cliente_id
           WHERE p.pago = 0
           ORDER BY p.vencimento ASC
           LIMIT 8"""
    )

    estoque_baixo = db.query(
        """SELECT * FROM produtos
           WHERE ativo = 1 AND estoque <= estoque_minimo
           ORDER BY estoque ASC, nome ASC
           LIMIT 10"""
    )

    aniversariantes_mes, aniversariantes_hoje = _aniversariantes()

    return render_template(
        "dashboard_vendedor.html",
        indicadores=indicadores,
        minhas_vendas=minhas_vendas,
        proximas_parcelas=proximas_parcelas,
        estoque_baixo=estoque_baixo,
        aniversariantes_mes=aniversariantes_mes,
        aniversariantes_hoje=aniversariantes_hoje,
        hoje=hoje,
        rotulo_mes=rotulo_competencia(competencia),
    )
