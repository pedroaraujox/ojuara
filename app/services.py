"""Regras de negocio: estoque, notas fiscais, vendas, crediario e sacolas."""

from . import db
from .utils import (
    agora_iso,
    normaliza_codigo,
    normaliza_tamanho,
    parse_data,
    soma_meses,
    to_decimal,
    to_int,
)


class ErroNegocio(Exception):
    """Falha de validacao que deve ser mostrada ao usuario."""


# --- leitura de lotes -------------------------------------------------------

def coletar_lote(form):
    """Le itens em lote de um formulario.

    Aceita duas entradas simultaneas:
      * linhas dinamicas da tabela  -> campos `codigo[]`, `tamanho[]`,
        `cor[]` e `quantidade[]`
      * area de colagem `lote_texto` -> uma linha por item, nos formatos
        "COD;TAM;COR;QTD", "COD;TAM;QTD", "COD;QTD" (quando o codigo
        cadastrado) ou "COD" (quantidade 1).

    Retorna lista de dicts {codigo, tamanho, cor, quantidade} preservando a
    ordem digitada. Tamanho e cor podem vir vazios quando o codigo so tem uma
    variante cadastrada.
    """
    itens = []

    codigos = form.getlist("codigo[]") or form.getlist("codigo")
    tamanhos = form.getlist("tamanho[]") or form.getlist("tamanho")
    cores = form.getlist("cor[]") or form.getlist("cor")
    quantidades = form.getlist("quantidade[]") or form.getlist("quantidade")
    for indice, bruto in enumerate(codigos):
        codigo = normaliza_codigo(bruto)
        if not codigo:
            continue
        tamanho = normaliza_tamanho(tamanhos[indice] if indice < len(tamanhos) else "")
        cor = (cores[indice] if indice < len(cores) else "").strip()
        qtd = to_int(quantidades[indice] if indice < len(quantidades) else 0)
        itens.append({"codigo": codigo, "tamanho": tamanho, "cor": cor, "quantidade": qtd})

    for linha in (form.get("lote_texto") or "").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p for p in linha.replace(";", ",").split(",") if p.strip()] or \
            [p for p in linha.split() if p]
        partes = [p.strip() for p in partes]
        codigo = normaliza_codigo(partes[0])
        if not codigo:
            continue
        if len(partes) >= 4:
            tamanho = normaliza_tamanho(partes[1])
            cor = partes[2].strip()
            qtd = to_int(partes[3], 1)
        elif len(partes) == 3:
            tamanho = normaliza_tamanho(partes[1])
            cor = ""
            qtd = to_int(partes[2], 1)
        elif len(partes) == 2:
            tamanho = ""
            cor = ""
            qtd = to_int(partes[1], 1)
        else:
            tamanho = ""
            cor = ""
            qtd = 1
        itens.append({"codigo": codigo, "tamanho": tamanho, "cor": cor, "quantidade": qtd})

    return itens


def _resolver_produto(codigo, tamanho, cor=""):
    """Encontra a linha exata de produto (codigo + tamanho + cor).

    Se o tamanho vier vazio e o codigo tiver uma unica variante cadastrada,
    resolve sozinho. Se houver mais de uma variante, exige que o tamanho
    seja informado. Retorna (produto, erro) - exatamente um dos dois.
    """
    candidatos = db.query(
        "SELECT * FROM produtos WHERE codigo_fabricante = ? ORDER BY tamanho, cor", (codigo,)
    )
    if not candidatos:
        return None, "%s: codigo de produto nao cadastrado no catalogo." % codigo

    filtrados = candidatos
    if tamanho:
        filtrados = [p for p in filtrados if p["tamanho"] == tamanho]
    if cor:
        filtrados = [p for p in filtrados if (p["cor"] or "").casefold() == cor.casefold()]
    if len(filtrados) == 1:
        return filtrados[0], None
    if not filtrados:
        variantes = ", ".join(
            "%s / %s" % (p["tamanho"] or "sem tamanho", p["cor"] or "sem cor")
            for p in candidatos
        )
        return None, "%s: variante nao encontrada. Cadastradas: %s." % (codigo, variantes)

    if not tamanho:
        tamanhos = ", ".join(sorted({p["tamanho"] or "(sem tamanho)" for p in filtrados}))
        return None, "%s: informe o tamanho. Opcoes: %s." % (codigo, tamanhos)
    cores = ", ".join(sorted({p["cor"] or "(sem cor)" for p in filtrados}))
    return None, (
        "%s (%s): informe a cor. Opcoes: %s." % (codigo, tamanho, cores)
    )


def validar_lote(itens, exigir_estoque=True):
    """Valida um lote contra o cadastro de produtos (por codigo + tamanho).

    Retorna (validos, erros). Cada valido traz o produto ja carregado e a
    quantidade total acumulada por SKU, para que o mesmo codigo/tamanho
    digitado duas vezes nao estoure o estoque.
    """
    acumulado = {}
    ordem = []
    erros = []

    for item in itens:
        codigo = item["codigo"]
        tamanho = item.get("tamanho", "")
        cor = item.get("cor", "")
        quantidade = item["quantidade"]
        rotulo = "%s%s" % (codigo, " (%s)" % tamanho if tamanho else "")

        if quantidade <= 0:
            erros.append("%s: informe uma quantidade maior que zero." % rotulo)
            continue

        produto, erro = _resolver_produto(codigo, tamanho, cor)
        if erro:
            erros.append(erro)
            continue

        chave = produto["id"]
        if chave not in acumulado:
            acumulado[chave] = {"produto": produto, "quantidade": 0}
            ordem.append(chave)
        acumulado[chave]["quantidade"] += quantidade

    validos = []
    for chave in ordem:
        produto = acumulado[chave]["produto"]
        quantidade = acumulado[chave]["quantidade"]
        if exigir_estoque and quantidade > produto["estoque"]:
            erros.append(
                "%s (%s%s): estoque insuficiente. Disponivel %d, solicitado %d."
                % (
                    produto["codigo_fabricante"],
                    produto["nome"],
                    " %s" % produto["tamanho"] if produto["tamanho"] else "",
                    produto["estoque"],
                    quantidade,
                )
            )
            continue
        validos.append({"produto": produto, "quantidade": quantidade})

    if not validos and not erros:
        erros.append("Nenhum item informado.")

    return validos, erros


# --- notas fiscais -----------------------------------------------------------

def obter_ou_criar_nota_fiscal(numero, tipo, data, fornecedor="", observacao=""):
    """Retorna o id do cabecalho de NF, criando-o se ainda nao existir.

    Uma mesma NF (numero + tipo) pode receber varios lancamentos ao longo do
    tempo - por exemplo, itens conferidos aos poucos. Lancamentos seguintes
    apenas reaproveitam o cabecalho ja criado, sem sobrescrever seus dados.
    """
    numero = (numero or "").strip()
    if not numero:
        raise ErroNegocio("Informe o numero da nota fiscal.")

    existente = db.query(
        "SELECT id FROM notas_fiscais WHERE numero = ? AND tipo = ?",
        (numero, tipo),
        one=True,
    )
    if existente:
        return existente["id"]

    return db.execute(
        """INSERT INTO notas_fiscais (numero, tipo, fornecedor, data, observacao, criado_em)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (numero, tipo, (fornecedor or "").strip(), data, (observacao or "").strip(), agora_iso()),
    )


# --- movimentacao de estoque ------------------------------------------------

def movimentar(produto_id, tipo, quantidade, documento="", observacao="", nota_fiscal_id=None):
    """Aplica a movimentacao e grava o historico. Retorna o novo saldo.

    Tipos de saida abatem o estoque; os demais somam.
    """
    conexao = db.get_db()
    produto = conexao.execute(
        "SELECT * FROM produtos WHERE id = ?", (produto_id,)
    ).fetchone()
    if produto is None:
        raise ErroNegocio("Produto %s nao encontrado." % produto_id)

    quantidade = abs(to_int(quantidade))
    if quantidade <= 0:
        raise ErroNegocio("Quantidade deve ser maior que zero.")

    saida = tipo in ("VENDA", "BAIXA", "DEVOLUCAO_FORNECEDOR", "SAIDA_SACOLA")
    saldo_anterior = produto["estoque"]
    saldo_posterior = saldo_anterior - quantidade if saida else saldo_anterior + quantidade

    if saldo_posterior < 0:
        raise ErroNegocio(
            "Estoque insuficiente para %s (disponivel %d)."
            % (produto["codigo_fabricante"], saldo_anterior)
        )

    conexao.execute(
        "UPDATE produtos SET estoque = ? WHERE id = ?", (saldo_posterior, produto_id)
    )
    conexao.execute(
        """INSERT INTO movimentacoes
               (produto_id, codigo_fabricante, tipo, quantidade,
                saldo_anterior, saldo_posterior, nota_fiscal_id,
                documento, observacao, data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            produto_id,
            produto["codigo_fabricante"],
            tipo,
            quantidade,
            saldo_anterior,
            saldo_posterior,
            nota_fiscal_id,
            documento,
            observacao,
            agora_iso(),
        ),
    )
    return saldo_posterior


def aplicar_lote(validos, tipo, documento="", observacao="", nota_fiscal_id=None):
    """Movimenta todos os itens validados dentro de uma unica transacao."""
    conexao = db.get_db()
    try:
        for item in validos:
            movimentar(
                item["produto"]["id"],
                tipo,
                item["quantidade"],
                documento=documento,
                observacao=observacao,
                nota_fiscal_id=nota_fiscal_id,
            )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return validos


# --- vendas -----------------------------------------------------------------

def produtos_disponiveis_vendedor(vendedor_id, codigo=None):
    """Variantes ainda em posse do vendedor, vindas de NFs de entrada ativas."""
    vendedor_id = to_int(vendedor_id)
    if not vendedor_id:
        return []
    sql = """SELECT p.id, p.codigo_fabricante, p.nome, p.tamanho, p.cor,
                    p.preco_venda, p.preco_custo, p.ativo,
                    SUM(si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida)
                        AS estoque
             FROM sacola_itens si
             JOIN sacolas s ON s.id = si.sacola_id
             JOIN notas_fiscais nf ON nf.id = s.nota_fiscal_id
             JOIN produtos p ON p.id = si.produto_id
             WHERE s.vendedor_id = ? AND s.status = 'ABERTA'
               AND nf.tipo = 'ENTRADA' AND nf.ativa = 1 AND p.ativo = 1"""
    params = [vendedor_id]
    if codigo:
        sql += " AND p.codigo_fabricante = ?"
        params.append(normaliza_codigo(codigo))
    sql += """ GROUP BY p.id
               HAVING SUM(si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) > 0
               ORDER BY p.codigo_fabricante, p.tamanho, p.cor"""
    return db.query(sql, params)


def sacolas_disponiveis_vendedor(vendedor_id):
    """Sacolas abertas do vendedor, com os itens ainda disponiveis para venda."""
    vendedor_id = to_int(vendedor_id)
    if not vendedor_id:
        return []
    sacolas = db.query(
        """SELECT s.id, s.data_saida, nf.numero AS nf_numero, nf.fornecedor
           FROM sacolas s
           JOIN notas_fiscais nf ON nf.id = s.nota_fiscal_id
           WHERE s.vendedor_id = ? AND s.status = 'ABERTA'
             AND nf.tipo = 'ENTRADA' AND nf.ativa = 1
             AND EXISTS (
                 SELECT 1 FROM sacola_itens si WHERE si.sacola_id = s.id
                   AND (si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) > 0
             )
           ORDER BY s.data_saida, s.id""",
        (vendedor_id,),
    )
    totais = {item["id"]: item["estoque"] for item in produtos_disponiveis_vendedor(vendedor_id)}
    resultado = []
    for sacola in sacolas:
        grupo = dict(sacola)
        grupo["produtos"] = [dict(item) for item in db.query(
            """SELECT p.id, p.codigo_fabricante, p.nome, p.tamanho, p.cor,
                      p.preco_venda,
                      (si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) AS disponivel
               FROM sacola_itens si
               JOIN produtos p ON p.id = si.produto_id
               WHERE si.sacola_id = ? AND p.ativo = 1
                 AND (si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) > 0
               ORDER BY p.nome, p.tamanho, p.cor""",
            (sacola["id"],),
        )]
        for produto in grupo["produtos"]:
            produto["disponivel_total"] = totais.get(produto["id"], produto["disponivel"])
        resultado.append(grupo)
    return resultado


def _alocar_item_em_sacolas(conexao, venda_id, venda_item_id, vendedor_id, produto_id, quantidade):
    """Consome a quantidade das sacolas elegiveis do vendedor, em ordem FIFO."""
    linhas = conexao.execute(
        """SELECT si.id, si.sacola_id,
                  (si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) AS disponivel
           FROM sacola_itens si
           JOIN sacolas s ON s.id = si.sacola_id
           JOIN notas_fiscais nf ON nf.id = s.nota_fiscal_id
           WHERE s.vendedor_id = ? AND si.produto_id = ? AND s.status = 'ABERTA'
             AND nf.tipo = 'ENTRADA' AND nf.ativa = 1
             AND (si.quantidade_saida - si.quantidade_vendida - si.quantidade_devolvida) > 0
           ORDER BY s.data_saida, s.id, si.id""",
        (vendedor_id, produto_id),
    ).fetchall()
    restante = quantidade
    sacolas_afetadas = set()
    for linha in linhas:
        usada = min(restante, linha["disponivel"])
        if usada <= 0:
            continue
        conexao.execute(
            "UPDATE sacola_itens SET quantidade_vendida = quantidade_vendida + ? WHERE id = ?",
            (usada, linha["id"]),
        )
        conexao.execute(
            """INSERT INTO venda_sacola_alocacoes
                   (venda_id, venda_item_id, sacola_item_id, quantidade)
               VALUES (?, ?, ?, ?)""",
            (venda_id, venda_item_id, linha["id"], usada),
        )
        sacolas_afetadas.add(linha["sacola_id"])
        restante -= usada
        if restante == 0:
            break
    if restante:
        raise ErroNegocio("A quantidade disponivel na sacola mudou. Atualize a venda e tente novamente.")

    for sacola_id in sacolas_afetadas:
        pendentes = conexao.execute(
            """SELECT COUNT(*) FROM sacola_itens
               WHERE sacola_id = ?
                 AND (quantidade_saida - quantidade_vendida - quantidade_devolvida) > 0""",
            (sacola_id,),
        ).fetchone()[0]
        if pendentes == 0:
            conexao.execute(
                "UPDATE sacolas SET status = 'ACERTADA', data_acerto = ? WHERE id = ?",
                (agora_iso()[:10], sacola_id),
            )

def registrar_venda(form):
    """Cria a venda a partir de sacola do vendedor ligada a NF ativa.

    Retorna o id da venda. Levanta ErroNegocio com mensagem pronta para o
    usuario quando algo nao bate.
    """
    cliente_id = to_int(form.get("cliente_id"))
    vendedor_id = to_int(form.get("vendedor_id"))
    forma = (form.get("forma_pagamento") or "").upper()
    data_venda = parse_data(form.get("data")).isoformat()
    desconto = to_decimal(form.get("desconto"))
    observacao = (form.get("observacao") or "").strip()

    if not cliente_id:
        raise ErroNegocio("Selecione o cliente.")
    if not vendedor_id:
        raise ErroNegocio("Selecione o vendedor.")
    if forma not in ("DINHEIRO", "PIX", "CARTAO", "CREDIARIO"):
        raise ErroNegocio("Selecione a forma de pagamento.")

    cliente = db.query("SELECT * FROM clientes WHERE id = ?", (cliente_id,), one=True)
    if cliente is None:
        raise ErroNegocio("Cliente nao encontrado.")
    vendedor = db.query(
        "SELECT * FROM vendedores WHERE id = ?", (vendedor_id,), one=True
    )
    if vendedor is None:
        raise ErroNegocio("Vendedor nao encontrado.")

    # Itens: cada linha pode ter um preco unitario editado na tela.
    codigos = form.getlist("codigo[]")
    tamanhos = form.getlist("tamanho[]")
    cores = form.getlist("cor[]")
    quantidades = form.getlist("quantidade[]")
    precos = form.getlist("preco[]")

    brutos = []
    for indice, bruto in enumerate(codigos):
        codigo = normaliza_codigo(bruto)
        if not codigo:
            continue
        brutos.append(
            {
                "codigo": codigo,
                "tamanho": normaliza_tamanho(tamanhos[indice] if indice < len(tamanhos) else ""),
                "cor": (cores[indice] if indice < len(cores) else "").strip(),
                "quantidade": to_int(quantidades[indice] if indice < len(quantidades) else 0),
                "preco": (precos[indice] if indice < len(precos) else ""),
            }
        )

    if not brutos:
        raise ErroNegocio("Adicione pelo menos um produto a venda.")

    disponibilidade = {
        p["id"]: p for p in produtos_disponiveis_vendedor(vendedor_id)
    }
    acumulado = {}
    ordem = []
    erros = []
    for bruto in brutos:
        produto, erro = _resolver_produto(bruto["codigo"], bruto["tamanho"], bruto["cor"])
        if erro:
            erros.append(erro)
            continue
        if bruto["quantidade"] <= 0:
            erros.append("%s: informe uma quantidade maior que zero." % bruto["codigo"])
            continue
        if produto["id"] not in disponibilidade:
            erros.append(
                "%s (%s / %s): produto indisponivel. Ele deve estar em uma sacola deste vendedor e pertencer a uma NF ativa."
                % (produto["codigo_fabricante"], produto["tamanho"] or "-", produto["cor"] or "-")
            )
            continue
        if produto["id"] not in acumulado:
            acumulado[produto["id"]] = {"produto": produto, "quantidade": 0}
            ordem.append(produto["id"])
        acumulado[produto["id"]]["quantidade"] += bruto["quantidade"]
    for produto_id in ordem:
        solicitado = acumulado[produto_id]["quantidade"]
        disponivel = disponibilidade[produto_id]["estoque"]
        if solicitado > disponivel:
            produto = acumulado[produto_id]["produto"]
            erros.append(
                "%s (%s / %s): ha %d peca(s) disponivel(is) na sacola, mas foram solicitadas %d."
                % (produto["codigo_fabricante"], produto["tamanho"] or "-", produto["cor"] or "-", disponivel, solicitado)
            )
    if erros:
        raise ErroNegocio(" ".join(erros))
    validos = [acumulado[produto_id] for produto_id in ordem]

    # Preco informado prevalece sobre o preco de tabela (chave: id do produto).
    # Reaproveita a mesma resolucao de SKU usada na validacao, para nao correr
    # o risco de outra consulta ambigua bater num produto diferente.
    precos_informados = {}
    for bruto in brutos:
        preco = to_decimal(bruto["preco"], padrao=0.0)
        if preco <= 0:
            continue
        produto, _erro = _resolver_produto(bruto["codigo"], bruto["tamanho"], bruto["cor"])
        if produto:
            precos_informados[produto["id"]] = preco

    itens = []
    subtotal = 0.0
    for valido in validos:
        produto = valido["produto"]
        preco = precos_informados.get(produto["id"], produto["preco_venda"])
        total_item = round(preco * valido["quantidade"], 2)
        subtotal += total_item
        itens.append(
            {
                "produto": produto,
                "quantidade": valido["quantidade"],
                "preco": preco,
                "subtotal": total_item,
            }
        )

    subtotal = round(subtotal, 2)
    if desconto < 0:
        desconto = 0.0
    if desconto > subtotal:
        raise ErroNegocio("O desconto nao pode ser maior que o valor dos produtos.")
    total = round(subtotal - desconto, 2)

    qtd_parcelas = 1
    primeiro_vencimento = None
    if forma == "CREDIARIO":
        qtd_parcelas = to_int(form.get("qtd_parcelas"), 1)
        if qtd_parcelas < 1 or qtd_parcelas > 36:
            raise ErroNegocio("Informe de 1 a 36 parcelas para o crediario.")
        if total <= 0:
            raise ErroNegocio("Venda no crediario precisa ter valor maior que zero.")
        primeiro_vencimento = parse_data(
            form.get("primeiro_vencimento"),
            padrao=soma_meses(parse_data(data_venda), 1),
        )

    comissao_pct = vendedor["percentual_comissao"]
    comissao_valor = round(total * comissao_pct / 100.0, 2)

    conexao = db.get_db()
    try:
        cursor = conexao.execute(
            """INSERT INTO vendas
                   (cliente_id, vendedor_id, data, criado_em, forma_pagamento,
                    subtotal, desconto, total, parcelas, comissao_pct,
                    comissao_valor, observacao, cancelada)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                cliente_id,
                vendedor_id,
                data_venda,
                agora_iso(),
                forma,
                subtotal,
                desconto,
                total,
                qtd_parcelas,
                comissao_pct,
                comissao_valor,
                observacao,
            ),
        )
        venda_id = cursor.lastrowid

        for item in itens:
            produto = item["produto"]
            cursor_item = conexao.execute(
                """INSERT INTO venda_itens
                       (venda_id, produto_id, codigo_fabricante, tamanho, descricao,
                        quantidade, preco_unitario, subtotal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    venda_id,
                    produto["id"],
                    produto["codigo_fabricante"],
                    produto["tamanho"],
                    produto["nome"],
                    item["quantidade"],
                    item["preco"],
                    item["subtotal"],
                ),
            )
            _alocar_item_em_sacolas(
                conexao,
                venda_id,
                cursor_item.lastrowid,
                vendedor_id,
                produto["id"],
                item["quantidade"],
            )

        if forma == "CREDIARIO":
            gerar_parcelas(
                conexao, venda_id, cliente_id, total, qtd_parcelas, primeiro_vencimento
            )

        conexao.commit()
    except ErroNegocio:
        conexao.rollback()
        raise
    except Exception:
        conexao.rollback()
        raise

    return venda_id


def gerar_parcelas(conexao, venda_id, cliente_id, total, qtd_parcelas, primeiro_vencimento):
    """Divide o total em parcelas mensais; a ultima absorve a diferenca de centavos."""
    base = round(total / qtd_parcelas, 2)
    valores = [base] * qtd_parcelas
    valores[-1] = round(total - base * (qtd_parcelas - 1), 2)

    for indice in range(qtd_parcelas):
        vencimento = soma_meses(primeiro_vencimento, indice)
        conexao.execute(
            """INSERT INTO parcelas
                   (venda_id, cliente_id, numero, total_parcelas, valor,
                    vencimento, pago, data_pagamento)
               VALUES (?, ?, ?, ?, ?, ?, 0, NULL)""",
            (
                venda_id,
                cliente_id,
                indice + 1,
                qtd_parcelas,
                valores[indice],
                vencimento.isoformat(),
            ),
        )


def cancelar_venda(venda_id):
    """Cancela a venda e remove parcelas abertas.

    Vendas ligadas a sacolas devolvem as quantidades a posse do vendedor;
    vendas legadas sem alocacao preservam o estorno direto ao estoque.
    Parcelas ja pagas sao mantidas para historico.
    """
    venda = db.query("SELECT * FROM vendas WHERE id = ?", (venda_id,), one=True)
    if venda is None:
        raise ErroNegocio("Venda nao encontrada.")
    if venda["cancelada"]:
        raise ErroNegocio("Esta venda ja esta cancelada.")

    itens = db.query("SELECT * FROM venda_itens WHERE venda_id = ?", (venda_id,))
    alocacoes = db.query(
        "SELECT * FROM venda_sacola_alocacoes WHERE venda_id = ?", (venda_id,)
    )
    conexao = db.get_db()
    try:
        if alocacoes:
            sacolas_afetadas = set()
            for alocacao in alocacoes:
                linha = conexao.execute(
                    "SELECT sacola_id FROM sacola_itens WHERE id = ?",
                    (alocacao["sacola_item_id"],),
                ).fetchone()
                conexao.execute(
                    """UPDATE sacola_itens
                       SET quantidade_vendida = quantidade_vendida - ?
                       WHERE id = ?""",
                    (alocacao["quantidade"], alocacao["sacola_item_id"]),
                )
                if linha:
                    sacolas_afetadas.add(linha["sacola_id"])
            for sacola_id in sacolas_afetadas:
                conexao.execute(
                    "UPDATE sacolas SET status = 'ABERTA', data_acerto = NULL WHERE id = ?",
                    (sacola_id,),
                )
        else:
            # Compatibilidade com vendas antigas, registradas diretamente no estoque.
            for item in itens:
                movimentar(
                    item["produto_id"],
                    "ESTORNO",
                    item["quantidade"],
                    documento="Cancelamento venda #%d" % venda_id,
                    observacao="Retorno ao estoque",
                )
        conexao.execute(
            "DELETE FROM parcelas WHERE venda_id = ? AND pago = 0", (venda_id,)
        )
        conexao.execute("UPDATE vendas SET cancelada = 1 WHERE id = ?", (venda_id,))
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise


# --- sacolas (consignacao externa) ------------------------------------------

def produtos_disponiveis_na_nf(nota_fiscal_id):
    """Produtos recebidos numa NF de entrada, com o saldo ainda disponivel.

    O disponivel e o menor valor entre o que foi recebido naquela NF
    especifica e o estoque atual do produto: uma sacola nunca pode tirar
    mais do que essa NF trouxe, mesmo que o produto tenha saldo maior por
    causa de outras entradas. Produtos sem saldo disponivel nao aparecem.
    """
    linhas = db.query(
        """SELECT p.id, p.codigo_fabricante, p.nome, p.tamanho, p.cor, p.estoque,
                  SUM(m.quantidade) AS recebido_na_nf
           FROM movimentacoes m
           JOIN produtos p ON p.id = m.produto_id
           WHERE m.nota_fiscal_id = ? AND m.tipo = 'ENTRADA'
           GROUP BY p.id
           ORDER BY p.nome ASC, p.codigo_fabricante ASC, p.tamanho ASC""",
        (nota_fiscal_id,),
    )
    disponiveis = []
    for linha in linhas:
        item = dict(linha)
        item["disponivel"] = min(item["recebido_na_nf"], item["estoque"])
        if item["disponivel"] > 0:
            disponiveis.append(item)
    return disponiveis


def montar_sacola(form):
    """Monta uma sacola a partir dos produtos de uma NF de entrada especifica.

    O primeiro passo obrigatorio e a NF de origem: so podem ser selecionados
    produtos recebidos nela, e ate o limite ainda disponivel (ver
    `produtos_disponiveis_na_nf`). As pecas saem do estoque no ato (tipo
    SAIDA_SACOLA, atrelado a mesma NF) e ficam "em posse" do vendedor ate o
    acerto. Retorna o id da sacola criada.
    """
    vendedor_id = to_int(form.get("vendedor_id"))
    if not vendedor_id:
        raise ErroNegocio("Selecione o vendedor que vai levar a sacola.")

    vendedor = db.query("SELECT * FROM vendedores WHERE id = ?", (vendedor_id,), one=True)
    if vendedor is None:
        raise ErroNegocio("Vendedor nao encontrado.")

    nota_fiscal_id = to_int(form.get("nota_fiscal_id"))
    if not nota_fiscal_id:
        raise ErroNegocio("Selecione a Nota Fiscal de origem dos produtos.")

    nota = db.query(
        "SELECT * FROM notas_fiscais WHERE id = ? AND tipo = 'ENTRADA' AND ativa = 1",
        (nota_fiscal_id,),
        one=True,
    )
    if nota is None:
        raise ErroNegocio("Nota fiscal de entrada nao encontrada ou inativa.")

    data_saida = parse_data(form.get("data_saida")).isoformat()
    observacao = (form.get("observacao") or "").strip()

    disponiveis = {p["id"]: p for p in produtos_disponiveis_na_nf(nota_fiscal_id)}
    if not disponiveis:
        raise ErroNegocio("Esta nota fiscal nao tem mais produtos disponiveis para sacola.")

    ids = form.getlist("produto_id[]")
    quantidades = form.getlist("quantidade[]")
    selecionados = []
    for indice, produto_id_bruto in enumerate(ids):
        produto_id = to_int(produto_id_bruto)
        quantidade = to_int(quantidades[indice] if indice < len(quantidades) else 0)
        if not produto_id or quantidade <= 0:
            continue

        produto = disponiveis.get(produto_id)
        if produto is None:
            raise ErroNegocio(
                "Produto invalido: nao pertence a NF %s ou ja nao esta disponivel." % nota["numero"]
            )
        if quantidade > produto["disponivel"]:
            raise ErroNegocio(
                "%s%s: disponivel %d na NF %s, solicitado %d."
                % (
                    produto["codigo_fabricante"],
                    " (%s)" % produto["tamanho"] if produto["tamanho"] else "",
                    produto["disponivel"],
                    nota["numero"],
                    quantidade,
                )
            )
        selecionados.append({"produto": produto, "quantidade": quantidade})

    if not selecionados:
        raise ErroNegocio("Selecione ao menos um produto e informe a quantidade.")

    conexao = db.get_db()
    try:
        cursor = conexao.execute(
            """INSERT INTO sacolas
                   (vendedor_id, nota_fiscal_id, status, observacao, data_saida, criado_em)
               VALUES (?, ?, 'ABERTA', ?, ?, ?)""",
            (vendedor_id, nota_fiscal_id, observacao, data_saida, agora_iso()),
        )
        sacola_id = cursor.lastrowid

        for item in selecionados:
            produto = item["produto"]
            conexao.execute(
                """INSERT INTO sacola_itens
                       (sacola_id, produto_id, codigo_fabricante, tamanho, descricao,
                        quantidade_saida, quantidade_vendida, quantidade_devolvida)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 0)""",
                (
                    sacola_id,
                    produto["id"],
                    produto["codigo_fabricante"],
                    produto["tamanho"],
                    produto["nome"],
                    item["quantidade"],
                ),
            )
            movimentar(
                produto["id"],
                "SAIDA_SACOLA",
                item["quantidade"],
                documento="Sacola #%d" % sacola_id,
                observacao="Vendedor: %s" % vendedor["nome"],
                nota_fiscal_id=nota_fiscal_id,
            )

        conexao.commit()
    except Exception:
        conexao.rollback()
        raise

    return sacola_id


def registrar_acerto_sacola(sacola_id, form):
    """Registra, para cada item da sacola, quantas pecas foram vendidas e
    quantas voltaram ao estoque nesta rodada de acerto (valores incrementais,
    somados ao que ja havia sido acertado antes).

    Pecas devolvidas retornam ao estoque (DEVOLUCAO_SACOLA). Quando todo item
    estiver totalmente contabilizado (vendido + devolvido = saida), a sacola
    e marcada como ACERTADA.
    """
    sacola = db.query("SELECT * FROM sacolas WHERE id = ?", (sacola_id,), one=True)
    if sacola is None:
        raise ErroNegocio("Sacola nao encontrada.")
    if sacola["status"] == "ACERTADA":
        raise ErroNegocio("Esta sacola ja foi totalmente acertada.")

    itens = db.query("SELECT * FROM sacola_itens WHERE sacola_id = ? ORDER BY id", (sacola_id,))

    lancamentos = []
    for item in itens:
        vendeu_agora = to_int(form.get("vendeu_%d" % item["id"]))
        devolveu_agora = to_int(form.get("devolveu_%d" % item["id"]))
        if vendeu_agora < 0 or devolveu_agora < 0:
            raise ErroNegocio("Quantidades do acerto nao podem ser negativas.")
        if vendeu_agora == 0 and devolveu_agora == 0:
            continue

        em_posse = item["quantidade_saida"] - item["quantidade_vendida"] - item["quantidade_devolvida"]
        if vendeu_agora + devolveu_agora > em_posse:
            raise ErroNegocio(
                "%s%s: em posse do vendedor ha %d peca(s), mas o acerto informa %d."
                % (
                    item["codigo_fabricante"],
                    " (%s)" % item["tamanho"] if item["tamanho"] else "",
                    em_posse,
                    vendeu_agora + devolveu_agora,
                )
            )
        lancamentos.append((item, vendeu_agora, devolveu_agora))

    if not lancamentos:
        raise ErroNegocio("Informe ao menos uma quantidade vendida ou devolvida.")

    conexao = db.get_db()
    try:
        for item, vendeu_agora, devolveu_agora in lancamentos:
            if vendeu_agora:
                conexao.execute(
                    "UPDATE sacola_itens SET quantidade_vendida = quantidade_vendida + ? WHERE id = ?",
                    (vendeu_agora, item["id"]),
                )
            if devolveu_agora:
                conexao.execute(
                    "UPDATE sacola_itens SET quantidade_devolvida = quantidade_devolvida + ? WHERE id = ?",
                    (devolveu_agora, item["id"]),
                )
                movimentar(
                    item["produto_id"],
                    "DEVOLUCAO_SACOLA",
                    devolveu_agora,
                    documento="Sacola #%d" % sacola_id,
                    observacao="Retorno ao estoque no acerto",
                )

        pendentes = conexao.execute(
            """SELECT COUNT(*) AS qtd FROM sacola_itens
               WHERE sacola_id = ?
                 AND (quantidade_saida - quantidade_vendida - quantidade_devolvida) > 0""",
            (sacola_id,),
        ).fetchone()["qtd"]

        if pendentes == 0:
            conexao.execute(
                "UPDATE sacolas SET status = 'ACERTADA', data_acerto = ? WHERE id = ?",
                (agora_iso()[:10], sacola_id),
            )

        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
