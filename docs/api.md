# API interna

A API atende o JavaScript do próprio sistema. Não é uma API pública nem
versionada. Todas as rotas exigem sessão autenticada e permissão adequada.

## Autenticação e formato

- Autenticação: cookie de sessão obtido por `POST /login`.
- Respostas: JSON.
- Erros usuais: `401/302` sem sessão, `403` sem permissão, `404` sem resultado.
- Não há paginação ou rate limit próprio para estas consultas.

## Endpoints

### `GET /saude`

Verifica aplicação e uma consulta simples ao banco.

```json
{"status": "ok"}
```

### `GET /api/produtos/<codigo>`

Retorna variantes do código por tamanho e cor. Aceita `vendedor_id` para
restringir às variantes disponíveis em sacolas elegíveis. O perfil Vendedor
não recebe custo.

### `GET /api/produtos?q=<termo>`

Busca até 15 produtos ativos por código ou nome.

### `GET /api/vendedores/<id>/produtos-disponiveis`

Lista produtos que o vendedor pode vender a partir de suas sacolas abertas e
NFs ativas.

### `GET /api/vendedores/<id>/sacolas-disponiveis`

Lista sacolas elegíveis do vendedor para seleção na venda.

## Compatibilidade

Mudanças de campos devem ser coordenadas com `app/static/js/app.js` e com os
templates consumidores. Nunca exponha custos ao perfil Vendedor.
