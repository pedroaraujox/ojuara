# Ojuara Lingerie — Sistema de Gestão

Sistema web de gestão para loja de varejo de lingeries e roupas íntimas: catálogo
de produtos por código + tamanho + cor, estoque sempre atrelado a Nota Fiscal, vendas
com crediário, clientes, vendedores e comissões.

Projeto de portfólio da **Outbox Tech**. Roda 100% local — sem Docker, sem
container, sem servidor de banco externo.

---

## Stack

| Camada        | Tecnologia                                        |
|---------------|---------------------------------------------------|
| Backend       | Python 3.10+ · Flask 3                            |
| Banco         | SQLite (arquivo local, criado automaticamente)    |
| Frontend      | HTML5 · CSS3 · JavaScript puro · Bootstrap 5.3    |
| Dependências  | Apenas `Flask` — nenhum ORM, nenhum build step    |

---

## Como rodar localmente

Pré-requisito: **Python 3.10 ou superior** instalado (`python --version`).

### Windows (PowerShell)

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
pip install -r requirements.txt
```

```powershell
python run.py
```

> Se o PowerShell bloquear a ativação do venv, rode uma vez:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### Linux / macOS

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python run.py
```

### Acessar

Abra **http://127.0.0.1:5000** no navegador. O sistema exige login.

| Perfil              | Usuário      | Senha            |
|---------------------|--------------|------------------|
| Super administrador | `superadmin` | `Ojuara@2026`    |
| Administrador       | `admin`      | `Admin@2026`     |
| Vendedor            | `vendedora`  | `Vendedora@2026` |

> **Troque a senha do `superadmin` no primeiro acesso** (menu do usuário →
> Minha senha). As contas `admin` e `vendedora` são apenas demonstração dos
> perfis e podem ser excluídas em Usuários.

O banco `data/ojuara.db` e todas as tabelas são criados automaticamente na
primeira execução, junto com uma massa de dados de demonstração (19 produtos
— incluindo duas grades de tamanho —, 5 clientes com CEP, 3 vendedores,
10 vendas, notas fiscais de entrada/baixa/devolução e uma sacola de
consignação parcialmente acertada).

Para definir outras credenciais iniciais do super administrador, exporte as
variáveis antes da primeira execução:

```powershell
$env:OJUARA_SUPERADMIN = "pedro"; $env:OJUARA_SUPERADMIN_SENHA = "MinhaSenhaForte"; python run.py
```

### Começar com o banco vazio

Para subir sem os dados de demonstração:

```powershell
$env:OJUARA_SEED = "0"; python run.py
```

Para zerar tudo e recomeçar, basta apagar o arquivo `data/ojuara.db` e rodar de novo.

---

## Funcionalidades

### Login e perfis de acesso

Toda rota exige sessão autenticada — um `before_request` global bloqueia o
sistema inteiro, e só a tela de login e os arquivos estáticos ficam de fora.
As senhas são gravadas com hash `scrypt` (`werkzeug.security`); a senha em
texto puro nunca é armazenada. Erro de login devolve sempre a mesma mensagem,
sem revelar se o usuário existe.

Existem três perfis, definidos em [`app/auth.py`](app/auth.py):

| Área          | Super administrador | Administrador | Vendedor |
|---------------|:-------------------:|:-------------:|:--------:|
| Usuários (criar/editar/excluir) | ✅ | ❌ | ❌ |
| Produtos — consultar            | ✅ | ✅ | ✅ |
| Produtos — cadastrar/editar     | ✅ | ✅ | ❌ |
| Preço de custo e margem         | ✅ | ✅ | ❌ |
| Notas Fiscais — entrada/devolução | ✅ | ✅ | ❌ |
| Notas Fiscais — movimentações e listagem | ✅ | ✅ | ✅ |
| Sacolas — montar e acertar      | ✅ | ✅ | ❌ |
| Sacolas — ver (só as próprias)  | ✅ | ✅ | ✅ |
| Clientes — cadastrar/editar     | ✅ | ✅ | ✅ |
| Vendedores                      | ✅ | ✅ | ❌ |
| Vendas — registrar              | ✅ | ✅ | ✅ |
| Vendas — ver as da loja inteira | ✅ | ✅ | ❌ (só as suas) |
| Vendas — cancelar               | ✅ | ✅ | ❌ |
| Crediário — receber parcela     | ✅ | ✅ | ✅ |
| Crediário — estornar pagamento  | ✅ | ✅ | ❌ |
| Relatório de comissões          | ✅ | ✅ | ❌ (só a sua) |
| Posição de estoque / painel gerencial | ✅ | ✅ | ❌ |

Detalhes que valem destacar:

- **Regra vale no servidor, não só na tela.** Cada rota é protegida por
  `@requer("permissao")`; esconder o botão é conveniência, não segurança. Um
  vendedor que force a URL `/estoque/baixa` recebe 403.
- **O vendedor só enxerga as próprias vendas.** O filtro é imposto no servidor:
  abrir a venda de outro vendedor pela URL devolve 403, e um POST de venda com
  `vendedor_id` de terceiro é reescrito para o próprio usuário.
- **Preço de custo não trafega** para quem não pode vê-lo — a API
  `/api/produtos/<codigo>` remove o campo da resposta, além de a coluna sumir
  da tela.
- **O vendedor tem um painel próprio**, com as próprias vendas, comissão e
  ticket médio, sem faturamento da loja nem capital investido em estoque.
- **Travas de integridade**: ninguém exclui ou desativa o próprio usuário, e o
  sistema recusa remover, rebaixar ou desativar o **último super administrador
  ativo** — a loja nunca fica sem quem gerencie acessos.
- Perfil **Vendedor exige vínculo** com um cadastro de vendedor, que é o que
  permite ao sistema saber quais vendas e comissões são dele.

### Catálogo de produtos por código + grade de tamanhos e cores

`/produtos` é o **Catálogo de Produtos** — um cadastro puramente descritivo:
código do produto, nome, tamanho, cor, preço de custo e preço de venda. Ele
**não guarda fornecedor nem estoque**: todo produto novo nasce com saldo
zerado, e o saldo só passa a existir quando entra mercadoria de verdade pela
tela de Notas Fiscais, pela opção **Entrada de NF** (veja a seção seguinte). Isso
permite cadastrar o catálogo inteiro de uma vez, na loja ou em casa, sem
depender de já ter a mercadoria em mãos ou o número de uma NF. O estoque
mínimo (usado no alerta de "estoque baixo") também saiu do formulário: fica
fixo em zero para produtos novos, preservando o valor de quem já tinha um
mínimo configurado antes desta versão.

O **código do produto** lido na etiqueta identifica o modelo. O mesmo modelo
pode ter vários tamanhos e cores, cada combinação com saldo próprio. A chave
única é **(código, tamanho, cor)**: `12015 / M / Preta` e
`12015 / M / Branca` são variantes diferentes do mesmo modelo.

- Na ficha do produto (`/produtos/<id>`) uma seção **Grade do modelo** lista
  os demais tamanhos do mesmo código, com estoque e preço de cada um, e um
  atalho **Adicionar tamanho** pré-preenche nome/cor/preço do tamanho novo,
  deixando só o tamanho para digitar.
- Nas telas de lote (baixa, entrada, devolução, montagem de sacola) e na
  venda, a grade pede para **escolher tamanho e cor** quando houver mais de
  uma opção antes de liberar a quantidade.
- A API `GET /api/produtos/<codigo>` retorna todas as variantes de tamanho e
  cor do código, com os tamanhos ordenados de forma natural (PP/P/M/G/GG antes
  de numeração).

### Leitura de etiquetas por câmera

O próprio **código do produto** pode ser preenchido lendo a etiqueta pela
câmera. Não existe um segundo campo de código de barras: a leitura `12015`
preenche o código `12015`, enquanto tamanho e cor continuam manuais.
O padrão atual é obrigatório: **exatamente 5 algarismos**. Leituras parciais
continuam com a câmera aberta até o código completo ser confirmado.
No cadastro de produto novo, a mesma imagem também passa por reconhecimento
de texto para sugerir o nome impresso acima das barras. A sugestão permanece
editável para correção antes de salvar.

Nas grades de entrada, baixa, devolução e venda, o botão **Ler código** abre
a câmera traseira do celular. Também é possível digitar o número ou usar um
leitor físico que funcione como teclado. A câmera requer acesso pelo navegador
e uma conexão HTTPS (ou `localhost`).

### Notas Fiscais em dois passos: primeiro a NF, depois os produtos

**Entrada de NF** usa uma interface própria baseada no catálogo:

1. O operador informa os dados da nota fiscal. O número da NF aceita somente
   algarismos e abre o teclado numérico em celulares, preservando zeros à esquerda.
2. A tela mostra cada combinação já cadastrada de código, produto, tamanho e
   cor como uma opção independente.
3. A busca com lupa filtra imediatamente pelo código ou pelo nome do produto.
4. Ao tocar no item exato, o sistema solicita somente a quantidade recebida.
5. Os itens escolhidos ficam resumidos ao lado (ou abaixo, no celular) antes
   da confirmação da NF.

A antiga grade genérica de entrada em lote, com digitação manual de código,
tamanho e cor, não é usada na Entrada de NF. A **Devolução ao Fornecedor**
continua com sua própria grade de movimentação.
- O **número da NF é obrigatório**. Lançamentos sucessivos com o mesmo
  número (e mesmo tipo — entrada, baixa ou devolução) reaproveitam o mesmo
  cabeçalho em vez de duplicá-lo, então uma NF pode ser preenchida aos
  poucos.
- O mesmo SKU (código + tamanho + cor) digitado duas vezes é **somado** antes da
  validação, então o saldo nunca é estourado por duplicidade.
- Regra **tudo ou nada**: se qualquer item for inválido, ambíguo ou sem
  saldo, nenhuma movimentação é gravada e o lote volta inteiro para correção.
- O **fornecedor é um dado da NF**, não do produto (o catálogo não tem mais
  esse campo): cada nota carrega o fornecedor daquela remessa.
- **Listagem de Notas Fiscais** (`/estoque/notas-fiscais`) reúne todas as NFs lançadas (filtro por tipo e
  busca por número/fornecedor); `/estoque/notas-fiscais/<id>` mostra os
  produtos agrupados dentro dela. O histórico de movimentações e a ficha do
  produto linkam direto para a NF de origem.
- Cada NF possui status **Ativa** ou **Inativa**, alterável pela gerência na
  listagem. Apenas NFs de entrada ativas podem alimentar novas sacolas e vendas.

A entrada pela ficha do produto (`/produtos/<id>/entrada`) também
exige um número de NF, pelo mesmo motivo: todo acréscimo de estoque nasce de
uma nota fiscal.

No menu principal, **Notas Fiscais** contém exatamente estas opções:

- **Entrada de NF**;
- **Devolução ao Fornecedor**;
- **Movimentações**;
- **Listagem de Notas Fiscais**.

### Vendas e crediário

Em `/vendas/nova`, a escolha do vendedor controla o catálogo disponível. A tela
lista somente variantes que ainda estão em posse dele dentro de uma sacola
aberta e cuja NF de origem esteja ativa. A busca filtra por código ou nome; o
preço de tabela é carregado automaticamente e continua editável linha a linha.
Os demais campos são cliente, data, desconto e forma de pagamento — **Dinheiro,
Pix, Cartão ou Crediário/Parcelado**.

Essa condição também é validada no servidor: alterar manualmente o formulário
não permite vender produto de outro vendedor, fora da sacola, acima da
quantidade em posse ou originado de NF inativa.

Ao escolher Crediário, o sistema pergunta a **quantidade de parcelas** (1 a 24 na
tela, até 36 aceitos pela API) e a data do **primeiro vencimento**, e então:

- gera as parcelas com **vencimentos mensais** a partir dessa data;
- ajusta o dia quando o mês não tem a data (31/01 → 28/02);
- joga o resto dos centavos na última parcela, de forma que a soma bata exatamente
  com o total (ex.: R$ 100,00 em 3x → 33,33 + 33,33 + **33,34**);
- vincula as parcelas à conta do cliente.

Alocar os itens da sacola, calcular a comissão e gerar o carnê acontecem numa
**única transação**: se algo falhar, nada é gravado. A saída do estoque já
ocorreu na montagem da sacola, portanto a venda não baixa a mesma peça novamente.

Cada venda pode ser **cancelada** — nas vendas novas, as quantidades voltam à
sacola de origem; as parcelas em aberto são removidas (as já pagas ficam no
histórico). Vendas antigas, anteriores a essa vinculação, preservam o estorno
direto ao estoque por compatibilidade.

### Parcelas de vendas

A página independente de Crediário foi retirada da navegação. As parcelas
existentes continuam preservadas e podem ser consultadas, recebidas ou
estornadas na ficha do cliente e no detalhe da venda correspondente. O painel
continua destacando próximos vencimentos e valores em atraso.

### Clientes e vendedores

Cadastro completo de clientes (nome, telefone, **CEP obrigatório**, endereço,
observações e o **vendedor que captou/trouxe o cliente** para a loja) com
ficha individual: total comprado, saldo devedor, valor em atraso, carnê do
crediário e histórico de compras. O vendedor captador é só um dado de
atribuição de origem — não é o vendedor da venda, que é escolhido em cada
transação.

Vendedores têm percentual de comissão próprio, aplicado sobre o total de cada
venda no momento do registro.

### Sacolas (consignação externa)

Módulo de **montagem de sacolas** (`/sacolas`) para controlar peças que saem
da loja com um vendedor para vender porta a porta:

- `/sacolas/nova` (gerência): seleciona uma **NF de entrada ativa** e seus
  produtos por código + tamanho + cor, informa quantidade, vendedor e data de
  saída. As peças saem do estoque no ato (movimentação `SAIDA_SACOLA`).
- A ficha da sacola (`/sacolas/<id>`) mostra, por item, quanto **saiu**, quanto
  já foi **vendido**, quanto já foi **devolvido** e quanto ainda está **em
  posse** do vendedor.
- O **acerto** é lançado aos poucos: a gerência informa, por item, quanto foi
  vendido e quanto voltou desde o último acerto. As peças devolvidas retornam
  ao estoque automaticamente (`DEVOLUCAO_SACOLA`); o sistema nunca aceita
  acertar mais do que está em posse do vendedor. Quando todo item estiver
  100% contabilizado (vendido + devolvido = saiu), a sacola fecha sozinha
  como **Acertada**.
- O vendedor enxerga só as próprias sacolas (o que saiu, vendeu e devolveu),
  sem montar ou acertar — isso é exclusivo de administrador/super administrador.

### Comissões

`/relatorios/comissoes` filtra por mês e mostra, por vendedor: número de vendas,
total vendido, participação relativa, percentual e comissão a pagar — com
totalizador e quebra por forma de pagamento. A tela é pronta para impressão.

### Outras telas

- **Painel** (`/`): faturamento do mês, peças e valor em estoque, crediário a
  receber, parcelas vencidas, ranking de vendedores, produtos abaixo do estoque
  mínimo, mais vendidos e próximos vencimentos.
- **Movimentações** (`/estoque/movimentacoes`): histórico completo com filtro por
  tipo, período e busca. Toda movimentação registra saldo anterior e posterior.
- **Posição de estoque** (`/relatorios/estoque`): capital investido, venda
  potencial, margem, quebra por fornecedor e códigos mais devolvidos.

### Interface: tema escuro e responsividade

- **Tema claro/escuro**: botão no canto superior direito (e na tela de login)
  alterna entre os dois a qualquer momento. A escolha fica salva no navegador
  (`localStorage`) e é aplicada antes da página desenhar, sem "flash" do tema
  errado. Sem escolha salva, o sistema segue a preferência do sistema
  operacional/navegador.
- **Responsivo**: layout pensado para celular, tablet e desktop — tabelas
  longas rolam horizontalmente dentro do próprio cartão, os formulários em
  lote (estoque, sacolas, vendas) empilham em telas estreitas, e o menu
  principal vira um menu hambúrguer abaixo do breakpoint `lg`.
- Identidade visual própria (tipografia Plus Jakarta Sans, paleta de marca,
  cartões de indicador sem o clichê da "tarja lateral colorida" de template
  pronto) em vez do visual padrão do Bootstrap.

---

## Estrutura do projeto

```
OJUARA/
├── run.py                     # ponto de entrada: python run.py
├── requirements.txt
├── README.md
├── data/
│   └── ojuara.db              # SQLite criado automaticamente (ignorado no git)
└── app/
    ├── __init__.py            # create_app(): factory + blueprints + error handlers
    ├── config.py              # caminhos, secret key, flags de seed e superadmin
    ├── db.py                  # conexão SQLite por requisição + criação do schema
    ├── schema.sql             # DDL de todas as tabelas
    ├── auth.py                # perfis, matriz de permissões, sessão e decoradores
    ├── services.py            # regras de negócio (estoque, vendas, crediário)
    ├── seed.py                # massa de demonstração + superadmin inicial
    ├── utils.py               # datas, moeda BR, parsing de formulário, filtros Jinja
    ├── routes/
    │   ├── auth.py            # /login, /logout, /minha-senha
    │   ├── usuarios.py        # /usuarios (exclusivo do super administrador)
    │   ├── dashboard.py       # /
    │   ├── produtos.py        # /produtos (cadastro, ficha, grade de tamanhos)
    │   ├── estoque.py         # /estoque (baixa, entrada, devolução, NFs, movimentações)
    │   ├── clientes.py        # /clientes
    │   ├── vendedores.py      # /vendedores
    │   ├── vendas.py          # /vendas
    │   ├── crediario.py       # /crediario
    │   ├── relatorios.py      # /relatorios
    │   ├── sacolas.py         # /sacolas (consignação externa)
    │   └── api.py             # /api (busca de produto por código, usada pelo JS)
    ├── templates/             # Jinja2, um diretório por módulo
    │   ├── base.html          # layout, navegação por permissão e menu do usuário
    │   ├── dashboard.html     # painel gerencial
    │   ├── dashboard_vendedor.html  # painel reduzido do vendedor
    │   ├── erro.html          # 403 / 404 / 500
    │   ├── auth/ usuarios/
    │   ├── produtos/ estoque/ clientes/ vendedores/ vendas/ crediario/ relatorios/
    │   └── sacolas/
    └── static/
        ├── css/estilo.css     # identidade visual da loja
        └── js/app.js          # grade de digitação em lote por código + tamanho
```

---

## Modelo de dados

| Tabela          | Papel                                                             |
|-----------------|-------------------------------------------------------------------|
| `usuarios`      | Login, hash da senha, perfil (SUPERADMIN/ADMIN/VENDEDOR) e vínculo com o cadastro de vendedor |
| `produtos`      | Catálogo: código do produto + tamanho + cor (chave única composta), nome, custo, venda, estoque, mínimo. Sem fornecedor — isso é um dado da NF |
| `clientes`      | Nome, telefone, data de nascimento, CEP, endereço, vendedor captador, observações |
| `vendedores`    | Nome, telefone, data de nascimento, CPF, RG, endereço completo (CEP/rua/número/bairro/cidade/UF), percentual de comissão |
| `vendas`        | Cliente, vendedor, data, forma de pagamento, subtotal, desconto, total, comissão |
| `venda_itens`   | Itens da venda com código, tamanho, quantidade e preço praticado  |
| `parcelas`      | Carnê do crediário: número, valor, vencimento, situação           |
| `notas_fiscais` | Cabeçalho que agrupa os itens de uma entrada, baixa ou devolução: número, tipo, fornecedor, data e status ativa/inativa |
| `movimentacoes` | Histórico de estoque: tipo, quantidade, saldo anterior/posterior, NF de origem |
| `sacolas`       | Consignação externa: vendedor, situação (aberta/acertada), data de saída/acerto |
| `sacola_itens`  | Itens de cada sacola: quantidade que saiu, foi vendida e foi devolvida |
| `venda_sacola_alocacoes` | Liga cada quantidade vendida ao item exato da sacola de origem |

Tipos de movimentação: `ENTRADA`, `VENDA`, `BAIXA`, `DEVOLUCAO_FORNECEDOR`,
`ESTORNO`, `AJUSTE`, `SAIDA_SACOLA`, `DEVOLUCAO_SACOLA`.

---

## API interna

Consumida pelo JavaScript das telas de lote — útil também para integrações.

Ambas exigem sessão autenticada e a permissão `produtos.ver`.

| Rota                     | Retorno                                                  |
|--------------------------|----------------------------------------------------------|
| `GET /api/produtos/<codigo>` | Todas as variantes de tamanho e cor cadastradas para o código, ordenadas naturalmente (404 se nenhuma existir). O campo `preco_custo` é omitido de cada variante para o perfil Vendedor |
| `GET /api/produtos/<codigo>?vendedor_id=<id>` | Somente variantes disponíveis em sacola do vendedor e ligadas a NF ativa |
| `GET /api/vendedores/<id>/produtos-disponiveis` | Lista completa dos produtos elegíveis para a venda daquele vendedor |
| `GET /api/produtos?q=<termo>`| Até 15 produtos ativos por código ou nome            |

---

## Observações

- O Bootstrap e os ícones são carregados por CDN, então a **primeira abertura
  precisa de internet**. O CSS próprio (`static/css/estilo.css`) é local e mantém
  o layout legível caso o CDN não responda.
- O modo debug do Flask está ligado em `run.py` (recarrega ao salvar arquivo).
  É intencional para desenvolvimento local — desligue antes de qualquer uso real.
- A `SECRET_KEY` tem um valor padrão de desenvolvimento. Para uso real, defina
  `OJUARA_SECRET_KEY` no ambiente: sem isso, os cookies de sessão são
  assináveis por qualquer um que conheça o código.
- A sessão é por cookie e expira ao fechar o navegador. Não há expiração por
  inatividade nem bloqueio após tentativas repetidas de login.
- Para mudar a porta, edite `run.py` (`app.run(..., port=5000)`).
