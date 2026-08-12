# Implantação na Contabo

## Topologia oficial

Dois ambientes independentes são executados na mesma VM. O Nginx Proxy
Manager é o único serviço público e encaminha HTTPS para a porta `5000` dos
containers pela rede Docker privada `nginx-proxy_default`.

| Ambiente | Branch | Stack | Container | Domínio |
|---|---|---|---|---|
| Dev | `desenvolvimento` | `ojuara-dev` | `ojuara-dev` | `ojuara-dev.outboxtech.com.br` |
| Produção | `producao` | `ojuara-producao` | `ojuara-producao` | `ojuara.outboxtech.com.br` |

## Pré-requisitos

- Registros A dos dois domínios apontando para o IP público da VM.
- Docker, Portainer e Nginx Proxy Manager ativos.
- Portas públicas 80/443 encaminhadas apenas ao Nginx Proxy Manager.
- Rede externa Docker `nginx-proxy_default` existente.

## Criar a Stack de dev

No Portainer, crie uma Stack pelo Git:

```text
Nome: ojuara-dev
Repositório: https://github.com/pedroaraujox/ojuara.git
Referência: refs/heads/desenvolvimento
Compose path: compose.portainer.yaml
```

Variáveis:

```text
OJUARA_IMAGE_NAME=ojuara-dev
OJUARA_CONTAINER_NAME=ojuara-dev
OJUARA_DATA_DIR=/opt/ojuara-dev/data
OJUARA_BACKUP_DIR=/opt/ojuara-dev/backups
OJUARA_SUPERADMIN=superadmin
OJUARA_BACKUP_RETENCAO_DIAS=30
OJUARA_BACKUP_INTERVALO_SEGUNDOS=86400
NPM_NETWORK=nginx-proxy_default
OJUARA_SECRET_KEY=<segredo exclusivo com 32+ caracteres>
OJUARA_SUPERADMIN_SENHA=<senha inicial exclusiva>
```

## Criar a Stack de produção

Use o mesmo procedimento com:

```text
Nome: ojuara-producao
Referência: refs/heads/producao
OJUARA_IMAGE_NAME=ojuara-producao
OJUARA_CONTAINER_NAME=ojuara-producao
OJUARA_DATA_DIR=/opt/ojuara-producao/data
OJUARA_BACKUP_DIR=/opt/ojuara-producao/backups
```

Os demais valores são equivalentes, mas segredo e senha devem ser diferentes
de dev. Mantenha uma única réplica por causa do SQLite.

## Nginx Proxy Manager

Crie um Proxy Host por domínio com esquema `http`, porta `5000`, **Block Common
Exploits** e certificado Let's Encrypt com **Force SSL**.

Use o IP atribuído ao container na rede `nginx-proxy_default` conforme a
política desta VM. Digite o IP sem espaços; um espaço inicial faz o Nginx tentar
resolver o valor como hostname e causa `502`.

Descubra os endereços com:

```bash
docker inspect ojuara-dev --format '{{range $n, $r := .NetworkSettings.Networks}}{{$n}} {{$r.IPAddress}}{{println}}{{end}}'
docker inspect ojuara-producao --format '{{range $n, $r := .NetworkSettings.Networks}}{{$n}} {{$r.IPAddress}}{{println}}{{end}}'
```

IPs Docker podem mudar após redeploy. Atualize o Proxy Host quando isso ocorrer.

## Validação

```bash
docker ps --filter name=ojuara --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
sudo ls -la /opt/ojuara-dev/data /opt/ojuara-dev/backups
sudo ls -la /opt/ojuara-producao/data /opt/ojuara-producao/backups
```

Confirme `healthy`, backup em execução, certificado válido, login e
persistência após recriar o container. Troque a senha inicial no primeiro acesso.

Para atualizações e incidentes, consulte [operacao.md](operacao.md). Para
recuperação de dados, consulte [backup-restauracao.md](backup-restauracao.md).
