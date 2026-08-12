# Runbook de operação

## Verificação diária

```bash
docker ps --filter name=ojuara --format "table {{.Names}}\t{{.Status}}"
sudo ls -lah /opt/ojuara-dev/backups /opt/ojuara-producao/backups
df -h /
```

Esperado: aplicações `healthy`, serviços de backup `Up` e um backup recente
em cada ambiente.

## Atualização de desenvolvimento

1. Confirme que a branch `desenvolvimento` contém a mudança validada.
2. No Portainer, abra `ojuara-dev` e use **Pull and redeploy**.
3. Aguarde `ojuara-dev` ficar `healthy`.
4. Teste login e o fluxo alterado em `https://ojuara-dev.outboxtech.com.br`.

## Promoção para produção

1. Confirme um backup íntegro e recente de produção.
2. Incorpore o commit validado de `desenvolvimento` em `producao`.
3. No Portainer, faça **Pull and redeploy** em `ojuara-producao`.
4. Observe healthcheck e logs.
5. Teste login, painel e uma consulta ao banco.

Nunca atualize produção diretamente com código não validado em dev.

## Diagnóstico

```bash
docker logs ojuara-producao --tail 100
docker inspect ojuara-producao --format '{{json .State.Health}}'
docker exec nginx-proxy-app-1 node -e "require('http').get('http://IP_INTERNO:5000/saude',r=>{console.log(r.statusCode);r.pipe(process.stdout)})"
```

### `502 Bad Gateway`

1. Confirme aplicação `healthy`.
2. Confira o IP do ambiente em `nginx-proxy_default`.
3. Teste `/saude` de dentro do Nginx.
4. Confira o Proxy Host: esquema `http`, porta `5000` e IP sem espaços.
5. Leia `/data/logs/proxy-host-<id>_error.log` no container do Nginx.

### Aplicação não fica saudável

Leia os logs, confira segredos obrigatórios, permissões `10001:10001`, espaço
em disco e existência do banco. Não apague banco ou diretórios para tentar
resolver inicialização.

## Rollback

1. Preserve o banco e gere uma cópia antes de qualquer ação.
2. Reverta a branch para o último commit aprovado por meio de um novo commit.
3. Faça redeploy da Stack.
4. Restaure banco somente se uma migração ou escrita incompatível tiver ocorrido.

Não use `docker compose down -v` e não remova `/opt/ojuara-*`.
