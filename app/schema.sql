-- ---------------------------------------------------------------------------
-- Ojuara Lingerie - esquema do banco SQLite
-- Criado automaticamente na primeira execucao (ver app/db.py).
-- ---------------------------------------------------------------------------

PRAGMA foreign_keys = ON;

-- Usuarios do sistema --------------------------------------------------------
-- papel: SUPERADMIN | ADMIN | VENDEDOR  (regras em app/auth.py)
-- vendedor_id liga um usuario VENDEDOR ao seu cadastro em `vendedores`,
-- permitindo filtrar "minhas vendas" e "minha comissao".
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    usuario       TEXT    NOT NULL UNIQUE,
    senha_hash    TEXT    NOT NULL,
    papel         TEXT    NOT NULL DEFAULT 'VENDEDOR',
    vendedor_id   INTEGER REFERENCES vendedores (id),
    ativo         INTEGER NOT NULL DEFAULT 1,
    criado_em     TEXT    NOT NULL,
    ultimo_acesso TEXT
);

CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios (usuario);

-- Vendedores -----------------------------------------------------------------
-- Cadastro completo por seguranca juridica/compliance: documentos e endereco
-- ficam registrados junto do vendedor, nao apenas nome e telefone.
CREATE TABLE IF NOT EXISTS vendedores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                TEXT    NOT NULL,
    telefone            TEXT    NOT NULL DEFAULT '',
    data_nascimento     TEXT    NOT NULL DEFAULT '',
    cpf                 TEXT    NOT NULL DEFAULT '',
    rg                  TEXT    NOT NULL DEFAULT '',
    cep                 TEXT    NOT NULL DEFAULT '',
    rua                 TEXT    NOT NULL DEFAULT '',
    numero              TEXT    NOT NULL DEFAULT '',
    bairro              TEXT    NOT NULL DEFAULT '',
    cidade              TEXT    NOT NULL DEFAULT '',
    uf                  TEXT    NOT NULL DEFAULT '',
    percentual_comissao REAL    NOT NULL DEFAULT 0,
    ativo               INTEGER NOT NULL DEFAULT 1,
    criado_em           TEXT    NOT NULL
);

-- Clientes -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                 TEXT    NOT NULL,
    telefone             TEXT    NOT NULL DEFAULT '',
    data_nascimento      TEXT    NOT NULL DEFAULT '',
    cep                  TEXT    NOT NULL DEFAULT '',
    endereco             TEXT    NOT NULL DEFAULT '',
    -- Vendedor que captou/trouxe o cliente para a loja (nao e o vendedor da venda).
    vendedor_captador_id INTEGER REFERENCES vendedores (id),
    observacao           TEXT    NOT NULL DEFAULT '',
    ativo                INTEGER NOT NULL DEFAULT 1,
    criado_em            TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clientes_captador ON clientes (vendedor_captador_id);

-- Catalogo de produtos --------------------------------------------------
-- Um "modelo" e identificado pelo codigo_fabricante (exibido como "codigo do
-- produto" na interface), mas cada tamanho e uma linha propria com seu
-- proprio saldo de estoque: a combinacao (codigo, tamanho, cor) precisa ser unica,
-- nao o codigo isoladamente. O catalogo e puramente descritivo - fornecedor
-- e um dado da Nota Fiscal (ver notas_fiscais), nao do produto, e o saldo em
-- estoque so muda por movimentacao (entrada/baixa/venda/devolucao), nunca
-- pelo cadastro do produto.
CREATE TABLE IF NOT EXISTS produtos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_fabricante  TEXT    NOT NULL,
    nome               TEXT    NOT NULL,
    tamanho            TEXT    NOT NULL DEFAULT '',
    cor                TEXT    NOT NULL DEFAULT '',
    preco_custo        REAL    NOT NULL DEFAULT 0,
    preco_venda        REAL    NOT NULL DEFAULT 0,
    estoque            INTEGER NOT NULL DEFAULT 0,
    estoque_minimo     INTEGER NOT NULL DEFAULT 0,
    ativo              INTEGER NOT NULL DEFAULT 1,
    criado_em          TEXT    NOT NULL,
    UNIQUE (codigo_fabricante, tamanho, cor)
);

CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos (codigo_fabricante);

-- Vendas ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id      INTEGER NOT NULL REFERENCES clientes (id),
    vendedor_id     INTEGER NOT NULL REFERENCES vendedores (id),
    data            TEXT    NOT NULL,          -- YYYY-MM-DD
    criado_em       TEXT    NOT NULL,
    forma_pagamento TEXT    NOT NULL,          -- DINHEIRO | PIX | CARTAO | CREDIARIO
    subtotal        REAL    NOT NULL DEFAULT 0,
    desconto        REAL    NOT NULL DEFAULT 0,
    total           REAL    NOT NULL DEFAULT 0,
    parcelas        INTEGER NOT NULL DEFAULT 1,
    comissao_pct    REAL    NOT NULL DEFAULT 0,
    comissao_valor  REAL    NOT NULL DEFAULT 0,
    observacao      TEXT    NOT NULL DEFAULT '',
    cancelada       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_vendas_data     ON vendas (data);
CREATE INDEX IF NOT EXISTS idx_vendas_vendedor ON vendas (vendedor_id);
CREATE INDEX IF NOT EXISTS idx_vendas_cliente  ON vendas (cliente_id);

CREATE TABLE IF NOT EXISTS venda_itens (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id          INTEGER NOT NULL REFERENCES vendas (id) ON DELETE CASCADE,
    produto_id        INTEGER NOT NULL REFERENCES produtos (id),
    codigo_fabricante TEXT    NOT NULL,
    tamanho           TEXT    NOT NULL DEFAULT '',
    descricao         TEXT    NOT NULL,
    quantidade        INTEGER NOT NULL,
    preco_unitario    REAL    NOT NULL,
    subtotal          REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_itens_venda ON venda_itens (venda_id);

-- Crediario ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parcelas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id        INTEGER NOT NULL REFERENCES vendas (id) ON DELETE CASCADE,
    cliente_id      INTEGER NOT NULL REFERENCES clientes (id),
    numero          INTEGER NOT NULL,
    total_parcelas  INTEGER NOT NULL,
    valor           REAL    NOT NULL,
    vencimento      TEXT    NOT NULL,          -- YYYY-MM-DD
    pago            INTEGER NOT NULL DEFAULT 0,
    data_pagamento  TEXT
);

CREATE INDEX IF NOT EXISTS idx_parcelas_cliente    ON parcelas (cliente_id);
CREATE INDEX IF NOT EXISTS idx_parcelas_vencimento ON parcelas (vencimento);

-- Notas fiscais ----------------------------------------------------------
-- Cabecalho que agrupa as pecas lancadas numa mesma NF: entrada (compra),
-- baixa (saida principal) e devolucao ao fornecedor sao sempre lancadas
-- atreladas a um numero de NF (ver app/routes/estoque.py).
CREATE TABLE IF NOT EXISTS notas_fiscais (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    numero     TEXT    NOT NULL,
    tipo       TEXT    NOT NULL,   -- ENTRADA | BAIXA | DEVOLUCAO_FORNECEDOR
    fornecedor TEXT    NOT NULL DEFAULT '',
    data       TEXT    NOT NULL,   -- YYYY-MM-DD
    observacao TEXT    NOT NULL DEFAULT '',
    ativa      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nf_numero ON notas_fiscais (numero);
CREATE INDEX IF NOT EXISTS idx_nf_tipo   ON notas_fiscais (tipo);
CREATE INDEX IF NOT EXISTS idx_nf_ativa  ON notas_fiscais (ativa);

-- Movimentacoes de estoque ---------------------------------------------------
-- tipo: ENTRADA | VENDA | BAIXA | DEVOLUCAO_FORNECEDOR | ESTORNO | AJUSTE
--       SAIDA_SACOLA | DEVOLUCAO_SACOLA (consignacao externa, ver sacolas)
CREATE TABLE IF NOT EXISTS movimentacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id        INTEGER NOT NULL REFERENCES produtos (id),
    codigo_fabricante TEXT    NOT NULL,
    tipo              TEXT    NOT NULL,
    quantidade        INTEGER NOT NULL,        -- sempre positiva
    saldo_anterior    INTEGER NOT NULL,
    saldo_posterior   INTEGER NOT NULL,
    nota_fiscal_id    INTEGER REFERENCES notas_fiscais (id),
    documento         TEXT    NOT NULL DEFAULT '',
    observacao        TEXT    NOT NULL DEFAULT '',
    data              TEXT    NOT NULL         -- YYYY-MM-DD HH:MM:SS
);

CREATE INDEX IF NOT EXISTS idx_mov_produto ON movimentacoes (produto_id);
CREATE INDEX IF NOT EXISTS idx_mov_data    ON movimentacoes (data);
CREATE INDEX IF NOT EXISTS idx_mov_tipo    ON movimentacoes (tipo);
CREATE INDEX IF NOT EXISTS idx_mov_nf      ON movimentacoes (nota_fiscal_id);

-- Sacolas (consignacao externa) -----------------------------------------
-- A gerencia monta uma sacola com pecas de varios tamanhos e atrela a um
-- vendedor que sai para vender porta a porta. O acerto registra o que foi
-- vendido e o que voltou ao estoque; o restante fica em posse do vendedor.
-- nota_fiscal_id e obrigatorio a partir da tela (ver app/services.py
-- montar_sacola): toda sacola nova precisa vir de uma NF de entrada
-- especifica, de onde os produtos disponiveis sao filtrados. A coluna fica
-- nullable no banco so para nao quebrar sacolas de instalacoes anteriores a
-- essa regra.
CREATE TABLE IF NOT EXISTS sacolas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    vendedor_id    INTEGER NOT NULL REFERENCES vendedores (id),
    nota_fiscal_id INTEGER REFERENCES notas_fiscais (id),
    status         TEXT    NOT NULL DEFAULT 'ABERTA',  -- ABERTA | ACERTADA
    observacao     TEXT    NOT NULL DEFAULT '',
    data_saida     TEXT    NOT NULL,          -- YYYY-MM-DD
    data_acerto    TEXT,
    criado_em      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sacolas_vendedor ON sacolas (vendedor_id);
CREATE INDEX IF NOT EXISTS idx_sacolas_status   ON sacolas (status);
CREATE INDEX IF NOT EXISTS idx_sacolas_nf       ON sacolas (nota_fiscal_id);

CREATE TABLE IF NOT EXISTS sacola_itens (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    sacola_id             INTEGER NOT NULL REFERENCES sacolas (id) ON DELETE CASCADE,
    produto_id            INTEGER NOT NULL REFERENCES produtos (id),
    codigo_fabricante     TEXT    NOT NULL,
    tamanho               TEXT    NOT NULL DEFAULT '',
    descricao             TEXT    NOT NULL,
    quantidade_saida      INTEGER NOT NULL,
    quantidade_vendida    INTEGER NOT NULL DEFAULT 0,
    quantidade_devolvida  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sacola_itens_sacola ON sacola_itens (sacola_id);

-- Liga cada quantidade vendida ao item exato da sacola de onde saiu. Isso
-- permite validar a posse do vendedor e desfazer a alocacao no cancelamento.
CREATE TABLE IF NOT EXISTS venda_sacola_alocacoes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id       INTEGER NOT NULL REFERENCES vendas (id) ON DELETE CASCADE,
    venda_item_id  INTEGER NOT NULL REFERENCES venda_itens (id) ON DELETE CASCADE,
    sacola_item_id INTEGER NOT NULL REFERENCES sacola_itens (id),
    quantidade     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vsa_venda ON venda_sacola_alocacoes (venda_id);
CREATE INDEX IF NOT EXISTS idx_vsa_item  ON venda_sacola_alocacoes (sacola_item_id);
