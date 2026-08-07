"""Dados de demonstracao criados apenas quando o banco esta vazio.

Desative exportando OJUARA_SEED=0 antes de iniciar o servidor.
"""

from datetime import date

from werkzeug.datastructures import MultiDict
from werkzeug.security import generate_password_hash

from . import db
from .services import (
    aplicar_lote,
    montar_sacola,
    obter_ou_criar_nota_fiscal,
    registrar_acerto_sacola,
    registrar_venda,
    validar_lote,
)
from .utils import agora_iso, soma_meses

# nome, telefone, data_nascimento, cpf, rg, cep, rua, numero, bairro, cidade, uf, comissao
VENDEDORES = [
    ("Aline Ferreira", "(11) 98877-1020", "1992-04-14", "35216498060", "34.221.908-5",
     "04101-300", "Rua Vergueiro", "482", "Vila Mariana", "Sao Paulo", "SP", 5.0),
    ("Bruna Castilho", "(11) 99120-4477", "1988-09-02", "41028876521", "28.774.102-3",
     "03310-000", "Rua Sete de Setembro", "120", "Vila Nova", "Sao Paulo", "SP", 4.0),
    ("Camila Duarte", "(11) 98444-3311", "1996-01-21", "28765394038", "19.887.230-1",
     "05407-002", "Travessa das Flores", "45", "Centro", "Sao Paulo", "SP", 6.0),
]

# nome, telefone, data_nascimento, cep, endereco, indice do vendedor captador (ou None)
# Datas de nascimento espalhadas no mes atual (para o alerta de aniversariantes
# ter o que mostrar assim que o sistema sobe) e fora dele, para mostrar o filtro.
CLIENTES = [
    ("Maria Aparecida Souza", "(11) 99801-2233", "1985-07-26", "01310-100",
     "Rua das Acacias, 120 - Centro", 0),
    ("Joana Ribeiro Lima", "(11) 98120-9987", "1990-07-05", "04538-133",
     "Av. Brasil, 890 - Jardim Sul", 1),
    ("Patricia Nogueira", "(11) 97555-1188", "1978-11-30", "03310-000",
     "Rua Sete de Setembro, 45 - Vila Nova", 0),
    ("Rosangela Martins", "(11) 96322-7741", "1982-03-12", "05407-002",
     "Travessa das Flores, 8 - Centro", None),
    ("Simone Alcantara", "(11) 99444-0021", "1995-07-30", "02071-000",
     "Rua Ipiranga, 331 - Bela Vista", 2),
]

# codigo, nome, tamanho, cor, fornecedor, custo, venda, estoque, minimo
# Codigos repetidos (LIN-1001 e LIN-1005) formam a grade de tamanhos: mesmo
# modelo, mais de um tamanho, cada um com seu proprio saldo de estoque.
PRODUTOS = [
    ("LIN-1001", "Sutia Renda Delicata", "M", "Preto", "Delicata Lingerie", 28.90, 79.90, 24, 6),
    ("LIN-1001", "Sutia Renda Delicata", "P", "Preto", "Delicata Lingerie", 28.90, 79.90, 15, 6),
    ("LIN-1001", "Sutia Renda Delicata", "G", "Preto", "Delicata Lingerie", 28.90, 79.90, 10, 6),
    ("LIN-1002", "Sutia Renda Delicata", "G", "Nude", "Delicata Lingerie", 28.90, 79.90, 18, 6),
    ("LIN-1003", "Calcinha Tanga Renda", "M", "Preto", "Delicata Lingerie", 9.50, 29.90, 60, 15),
    ("LIN-1004", "Calcinha Tanga Renda", "P", "Vermelho", "Delicata Lingerie", 9.50, 29.90, 45, 15),
    ("LIN-1005", "Conjunto Microfibra Sensual", "M", "Vinho", "Bella Moda Intima", 42.00, 119.90, 12, 4),
    ("LIN-1005", "Conjunto Microfibra Sensual", "G", "Vinho", "Bella Moda Intima", 42.00, 119.90, 8, 4),
    ("LIN-1006", "Conjunto Microfibra Sensual", "G", "Preto", "Bella Moda Intima", 42.00, 119.90, 9, 4),
    ("LIN-2001", "Body Tule Bordado", "M", "Off White", "Bella Moda Intima", 55.00, 159.90, 7, 3),
    ("LIN-2002", "Camisola Cetim Longa", "U", "Champagne", "Noite Bela", 48.00, 139.90, 11, 3),
    ("LIN-2003", "Robe Cetim Curto", "U", "Rose", "Noite Bela", 39.00, 109.90, 8, 3),
    ("LIN-3001", "Sutia Amamentacao Confort", "G", "Branco", "MamaCare", 24.00, 69.90, 20, 6),
    ("LIN-3002", "Calcinha Alta Modeladora", "GG", "Nude", "MamaCare", 14.00, 44.90, 26, 8),
    ("LIN-3003", "Cinta Modeladora Pos-Parto", "M", "Preto", "MamaCare", 62.00, 179.90, 5, 2),
    ("LIN-4001", "Kit 3 Calcinhas Algodao", "M", "Sortido", "Basica Textil", 21.00, 59.90, 33, 10),
    ("LIN-4002", "Top Fitness Sustentacao", "P", "Cinza", "Basica Textil", 26.00, 74.90, 14, 5),
    ("LIN-4003", "Pijama Malha Curto", "M", "Azul", "Noite Bela", 37.00, 99.90, 16, 5),
    ("LIN-5001", "Meia Calca Fio 40", "U", "Preto", "Basica Textil", 8.00, 24.90, 50, 12),
]

# Tamanho "de referencia" de cada codigo, usado ao montar as vendas de
# demonstracao (evita ambiguidade nos codigos que viraram grade acima).
TAMANHO_REFERENCIA = {}
for _codigo, _nome, _tam, _cor, _forn, _custo, _venda, _estoque, _minimo in PRODUTOS:
    TAMANHO_REFERENCIA.setdefault(_codigo, _tam)

# (indice_cliente, indice_vendedor, [(codigo, qtd)], forma, dias_atras, parcelas)
VENDAS = [
    (0, 0, [("LIN-1001", 1), ("LIN-1003", 2)], "PIX", 42, 0),
    (1, 1, [("LIN-1005", 1)], "CREDIARIO", 38, 3),
    (2, 0, [("LIN-2002", 1), ("LIN-2003", 1)], "CARTAO", 30, 0),
    (3, 2, [("LIN-4001", 2), ("LIN-5001", 3)], "DINHEIRO", 24, 0),
    (4, 1, [("LIN-3001", 1), ("LIN-3002", 2)], "CREDIARIO", 20, 4),
    (0, 2, [("LIN-2001", 1)], "CARTAO", 14, 0),
    (1, 0, [("LIN-1002", 1), ("LIN-1004", 2)], "PIX", 9, 0),
    (2, 1, [("LIN-3003", 1)], "CREDIARIO", 5, 6),
    (3, 2, [("LIN-4003", 1), ("LIN-4002", 1)], "CARTAO", 3, 0),
    (4, 0, [("LIN-1006", 1), ("LIN-1003", 1)], "DINHEIRO", 1, 0),
]


def _banco_vazio():
    return db.escalar("SELECT COUNT(*) FROM produtos") == 0


def garantir_superadmin(app):
    """Cria o super administrador caso o sistema ainda nao tenha nenhum.

    Roda em toda inicializacao, inclusive com OJUARA_SEED=0: sem um super
    administrador ativo nao haveria como entrar no sistema.
    """
    if db.escalar("SELECT COUNT(*) FROM usuarios WHERE papel = 'SUPERADMIN' AND ativo = 1"):
        return

    login = app.config["SUPERADMIN_LOGIN"].strip().lower()
    senha = app.config["SUPERADMIN_SENHA"]

    existente = db.query("SELECT id FROM usuarios WHERE usuario = ?", (login,), one=True)
    if existente:
        db.execute(
            "UPDATE usuarios SET papel = 'SUPERADMIN', ativo = 1 WHERE id = ?",
            (existente["id"],),
        )
    else:
        db.execute(
            """INSERT INTO usuarios
                   (nome, usuario, senha_hash, papel, vendedor_id, ativo, criado_em)
               VALUES (?, ?, ?, 'SUPERADMIN', NULL, 1, ?)""",
            ("Super Administrador", login, generate_password_hash(senha), agora_iso()),
        )
    app.logger.info("Super administrador '%s' disponivel para login.", login)


def _cria_usuarios_demo():
    """Um usuario por perfil, para demonstrar as regras de acesso."""
    agora = agora_iso()
    vendedora = db.query("SELECT id, nome FROM vendedores ORDER BY id LIMIT 1", one=True)

    demos = [
        ("Gerente da Loja", "admin", "Admin@2026", "ADMIN", None),
        (
            vendedora["nome"] if vendedora else "Vendedora",
            "vendedora",
            "Vendedora@2026",
            "VENDEDOR",
            vendedora["id"] if vendedora else None,
        ),
    ]

    for nome, login, senha, papel, vendedor_id in demos:
        if papel == "VENDEDOR" and vendedor_id is None:
            continue
        if db.query("SELECT id FROM usuarios WHERE usuario = ?", (login,), one=True):
            continue
        db.execute(
            """INSERT INTO usuarios
                   (nome, usuario, senha_hash, papel, vendedor_id, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (nome, login, generate_password_hash(senha), papel, vendedor_id, agora),
        )


def popular_demo():
    if not _banco_vazio():
        return

    conexao = db.get_db()
    agora = agora_iso()

    for nome, telefone, nascimento, cpf, rg, cep, rua, numero, bairro, cidade, uf, comissao in VENDEDORES:
        conexao.execute(
            """INSERT INTO vendedores
                   (nome, telefone, data_nascimento, cpf, rg, cep, rua, numero, bairro,
                    cidade, uf, percentual_comissao, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (nome, telefone, nascimento, cpf, rg, cep, rua, numero, bairro, cidade, uf,
             comissao, agora),
        )

    vendedores_ids = [
        linha["id"] for linha in db.query("SELECT id FROM vendedores ORDER BY id")
    ]

    # O primeiro cliente da lista sempre nasce "hoje" (mes/dia atuais, ano fixo
    # de exemplo), para o alerta de aniversariante do dia aparecer de imediato
    # em qualquer instalacao recem-semeada, nao so na data em que isto foi escrito.
    hoje = date.today()
    for indice, (nome, telefone, nascimento, cep, endereco, idx_captador) in enumerate(CLIENTES):
        if indice == 0:
            try:
                nascimento = date(1985, hoje.month, hoje.day).isoformat()
            except ValueError:
                nascimento = date(1985, hoje.month, 28).isoformat()  # 29/02 em ano nao bissexto
        captador_id = vendedores_ids[idx_captador] if idx_captador is not None else None
        conexao.execute(
            """INSERT INTO clientes
                   (nome, telefone, data_nascimento, cep, endereco, vendedor_captador_id,
                    observacao, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, '', 1, ?)""",
            (nome, telefone, nascimento, cep, endereco, captador_id, agora),
        )

    # O catalogo em si nao guarda fornecedor (isso e um dado da NF). A carga
    # inicial de estoque simula o fluxo real: uma NF de entrada por
    # fornecedor visitado, com os produtos daquela remessa atrelados a ela.
    nfs_por_fornecedor = {}
    sequencial_nf = 1
    for codigo, nome, tam, cor, fornecedor, custo, venda, estoque, minimo in PRODUTOS:
        if fornecedor not in nfs_por_fornecedor:
            numero_nf = "NF-%04d" % sequencial_nf
            nf_id = obter_ou_criar_nota_fiscal(
                numero_nf, "ENTRADA", agora[:10],
                fornecedor=fornecedor,
                observacao="Carga inicial de estoque - %s" % fornecedor,
            )
            nfs_por_fornecedor[fornecedor] = (nf_id, numero_nf)
            sequencial_nf += 1
        nf_id, numero_nf = nfs_por_fornecedor[fornecedor]

        cursor = conexao.execute(
            """INSERT INTO produtos
                   (codigo_fabricante, nome, tamanho, cor, preco_custo,
                    preco_venda, estoque, estoque_minimo, ativo, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (codigo, nome, tam, cor, custo, venda, estoque, minimo, agora),
        )
        conexao.execute(
            """INSERT INTO movimentacoes
                   (produto_id, codigo_fabricante, tipo, quantidade, saldo_anterior,
                    saldo_posterior, nota_fiscal_id, documento, observacao, data)
               VALUES (?, ?, 'ENTRADA', ?, 0, ?, ?, ?, 'Cadastro do catalogo', ?)""",
            (
                cursor.lastrowid, codigo, estoque, estoque, nf_id,
                "NF %s" % numero_nf, agora,
            ),
        )

    conexao.commit()

    _cria_usuarios_demo()

    vendedores = vendedores_ids
    clientes = [linha["id"] for linha in db.query("SELECT id FROM clientes ORDER BY id")]
    hoje = date.today()

    # Toda venda nova precisa sair de uma sacola do proprio vendedor e de uma
    # NF ativa. Prepara sacolas demonstrativas com exatamente os itens usados
    # nas vendas abaixo, agrupando por vendedor e NF de origem.
    necessidades = {}
    for _idx_cliente, idx_vendedor, itens, _forma, _dias, _parcelas in VENDAS:
        for codigo, quantidade in itens:
            produto = db.query(
                """SELECT p.id, m.nota_fiscal_id
                   FROM produtos p
                   JOIN movimentacoes m ON m.produto_id = p.id AND m.tipo = 'ENTRADA'
                   WHERE p.codigo_fabricante = ? AND p.tamanho = ?
                   ORDER BY m.id LIMIT 1""",
                (codigo, TAMANHO_REFERENCIA.get(codigo, "")),
                one=True,
            )
            chave = (idx_vendedor, produto["nota_fiscal_id"])
            necessidades.setdefault(chave, {})
            necessidades[chave][produto["id"]] = (
                necessidades[chave].get(produto["id"], 0) + quantidade
            )
    for (idx_vendedor, nota_fiscal_id), produtos_necessarios in necessidades.items():
        form_sacola = MultiDict()
        form_sacola["vendedor_id"] = str(vendedores[idx_vendedor])
        form_sacola["nota_fiscal_id"] = str(nota_fiscal_id)
        form_sacola["data_saida"] = hoje.isoformat()
        form_sacola["observacao"] = "Sacola para vendas de demonstracao"
        for produto_id, quantidade in produtos_necessarios.items():
            form_sacola.add("produto_id[]", str(produto_id))
            form_sacola.add("quantidade[]", str(quantidade))
        montar_sacola(form_sacola)

    for idx_cliente, idx_vendedor, itens, forma, dias, parcelas in VENDAS:
        data_venda = date.fromordinal(hoje.toordinal() - dias)
        form = MultiDict()
        form["cliente_id"] = str(clientes[idx_cliente])
        form["vendedor_id"] = str(vendedores[idx_vendedor])
        form["forma_pagamento"] = forma
        form["data"] = data_venda.isoformat()
        form["desconto"] = "0"
        form["observacao"] = "Venda de demonstracao"
        if forma == "CREDIARIO":
            form["qtd_parcelas"] = str(parcelas)
            form["primeiro_vencimento"] = soma_meses(data_venda, 1).isoformat()
        for codigo, quantidade in itens:
            form.add("codigo[]", codigo)
            form.add("tamanho[]", TAMANHO_REFERENCIA.get(codigo, ""))
            form.add("quantidade[]", str(quantidade))
            form.add("preco[]", "")
        registrar_venda(form)

    # Uma devolucao ao fornecedor e uma baixa avulsa, cada uma na sua NF, para
    # o historico e a lista de notas fiscais nao nascerem vazios.
    validos, erros = validar_lote([{"codigo": "LIN-5001", "tamanho": "", "quantidade": 4}])
    if validos and not erros:
        nf_dev_id = obter_ou_criar_nota_fiscal(
            "NF-DEV-0001", "DEVOLUCAO_FORNECEDOR", hoje.isoformat(),
            fornecedor="Basica Textil",
            observacao="Pecas encalhadas - colecao anterior",
        )
        aplicar_lote(
            validos,
            "DEVOLUCAO_FORNECEDOR",
            documento="NF NF-DEV-0001",
            observacao="Pecas encalhadas - colecao anterior",
            nota_fiscal_id=nf_dev_id,
        )

    validos, erros = validar_lote([{"codigo": "LIN-1004", "tamanho": "", "quantidade": 2}])
    if validos and not erros:
        nf_baixa_id = obter_ou_criar_nota_fiscal(
            "NF-BAIXA-0001", "BAIXA", hoje.isoformat(),
            observacao="Pecas danificadas em manuseio",
        )
        aplicar_lote(
            validos,
            "BAIXA",
            documento="NF NF-BAIXA-0001",
            observacao="Peca danificada",
            nota_fiscal_id=nf_baixa_id,
        )

    # Uma sacola em consignacao com um vendedor, ja parcialmente acertada:
    # mostra os tres estados (vendido / devolvido / ainda em posse). Os dois
    # itens precisam vir da MESMA nota fiscal (regra da montagem por NF), por
    # isso os dois codigos escolhidos aqui sao da NF-0005 (Basica Textil).
    nf_sacola_id, _ = nfs_por_fornecedor["Basica Textil"]
    produto_lin4001 = db.escalar(
        "SELECT id FROM produtos WHERE codigo_fabricante = 'LIN-4001'"
    )
    produto_lin5001 = db.escalar(
        "SELECT id FROM produtos WHERE codigo_fabricante = 'LIN-5001'"
    )
    sacola_form = MultiDict()
    sacola_form["vendedor_id"] = str(vendedores[2])
    sacola_form["nota_fiscal_id"] = str(nf_sacola_id)
    sacola_form["data_saida"] = date.fromordinal(hoje.toordinal() - 7).isoformat()
    sacola_form["observacao"] = "Rodada porta a porta - bairro Vila Nova"
    sacola_form.add("produto_id[]", str(produto_lin4001))
    sacola_form.add("quantidade[]", "4")
    sacola_form.add("produto_id[]", str(produto_lin5001))
    sacola_form.add("quantidade[]", "2")
    try:
        sacola_id = montar_sacola(sacola_form)
        itens_sacola = db.query(
            "SELECT * FROM sacola_itens WHERE sacola_id = ? ORDER BY id", (sacola_id,)
        )
        if len(itens_sacola) >= 2:
            acerto_form = MultiDict()
            acerto_form["vendeu_%d" % itens_sacola[0]["id"]] = "2"
            acerto_form["devolveu_%d" % itens_sacola[0]["id"]] = "0"
            acerto_form["vendeu_%d" % itens_sacola[1]["id"]] = "0"
            acerto_form["devolveu_%d" % itens_sacola[1]["id"]] = "1"
            registrar_acerto_sacola(sacola_id, acerto_form)
    except Exception:
        # A sacola de demonstracao e um extra; falha aqui nao pode travar o
        # restante da carga inicial do sistema.
        conexao.rollback()

    # Quita a primeira parcela de cada crediario para exibir os dois estados.
    conexao = db.get_db()
    for linha in db.query(
        """SELECT id FROM parcelas
           WHERE numero = 1 AND vencimento <= ?
           ORDER BY id""",
        (hoje.isoformat(),),
    ):
        conexao.execute(
            "UPDATE parcelas SET pago = 1, data_pagamento = ? WHERE id = ?",
            (hoje.isoformat(), linha["id"]),
        )
    conexao.commit()
