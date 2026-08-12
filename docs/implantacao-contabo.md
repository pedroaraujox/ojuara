# Implantação na Contabo

Arquitetura de produção: o Portainer cria os contêineres a partir da branch
`producao`; o Nginx Proxy Manager é o único serviço exposto à internet; o
Registro.br aponta o subdomínio para o IP da Contabo. O SQLite e os backups
ficam no host, fora do ciclo de vida dos contêineres.

## 1. DNS no Registro.br

Crie um registro `A`:

- nome: `ojuara`
- destino: IP público da Contabo
- TTL: `300` durante a implantação

O endereço final será `ojuara.outboxtech.com.br`. Mantenha os servidores DNS
atuais do domínio no Registro.br.

## 2. Diretórios persistentes

A Stack cria automaticamente os diretórios usados pelo Ojuara e ajusta suas
permissões com o serviço temporário `preparar_diretorios`. Se preferir
prepará-los manualmente, use:

```bash
sudo install -d -m 750 -o 10001 -g 10001 /opt/ojuara/data
sudo install -d -m 750 -o 10001 -g 10001 /opt/ojuara/backups
```

O contêiner roda sem privilégios, com UID e GID `10001`. Essas permissões são
necessárias para gravar o banco e os backups.

## 3. Banco real

Antes da primeira inicialização, envie o arquivo local `data/ojuara.db` para:

```text
/opt/ojuara/data/ojuara.db
```

Pare o Ojuara no notebook durante a cópia e use o backup mais recente e
verificado. Depois do envio:

```bash
sudo chown 10001:10001 /opt/ojuara/data/ojuara.db
sudo chmod 640 /opt/ojuara/data/ojuara.db
```

Nunca envie o banco ao GitHub. Caso o arquivo não exista, o Ojuara criará um
banco vazio com apenas o superadministrador.

## 4. Rede do Nginx Proxy Manager

No Portainer, abra **Networks** e copie o nome exato da rede usada pelo Nginx
Proxy Manager. Nesta Contabo, a rede identificada é `nginx-proxy_default`.

## 5. Stack no Portainer

Crie uma Stack pelo repositório Git privado, selecionando:

- repositório: `https://github.com/pedroaraujox/ojuara.git`
- referência: `refs/heads/producao`
- arquivo Compose: `compose.yaml`

Use uma credencial de leitura do GitHub no Portainer. Não grave token no
repositório nem no arquivo Compose.

Configure estas variáveis no ambiente da Stack:

```text
OJUARA_SECRET_KEY=<valor aleatório com pelo menos 32 caracteres>
OJUARA_SUPERADMIN=superadmin
OJUARA_SUPERADMIN_SENHA=<senha forte e exclusiva>
OJUARA_DATA_DIR=/opt/ojuara/data
OJUARA_BACKUP_DIR=/opt/ojuara/backups
NPM_NETWORK=<nome exato da rede do Nginx Proxy Manager>
```

Mantenha apenas uma réplica do serviço `ojuara`. A Stack não publica a porta
5000 no host: ela fica acessível somente na rede Docker compartilhada.

## 6. Proxy e HTTPS

No Nginx Proxy Manager, crie um **Proxy Host**:

- Domain Names: `ojuara.outboxtech.com.br`
- Scheme: `http`
- Forward Hostname / IP: `ojuara`
- Forward Port: `5000`
- Block Common Exploits: ativado

Na aba SSL, solicite um novo certificado Let's Encrypt e ative **Force SSL**,
**HTTP/2 Support** e **HSTS Enabled**. O certificado só será emitido depois que
o DNS estiver apontando para a Contabo e as portas 80 e 443 alcançarem o Nginx
Proxy Manager.

## 7. Verificação

No Portainer, confirme que `ojuara` está `healthy` e `backup` está em execução.
Teste:

1. acesso HTTPS e login;
2. cadastro simples e persistência após recriar os contêineres;
3. presença de um arquivo em `/opt/ojuara/backups`;
4. restauração desse backup em um ambiente de teste.

Copie os backups periodicamente para outro servidor ou armazenamento. Um
backup mantido apenas na mesma Contabo não protege contra perda da máquina.

## 8. Atualizações

O desenvolvimento entra primeiro em `desenvolvimento`. Depois dos testes, um
Pull Request aprovado é incorporado em `producao`. Antes de atualizar a Stack:

1. confirme que o backup mais recente abre corretamente;
2. mande o Portainer buscar novamente o repositório e reconstruir a imagem;
3. acompanhe o healthcheck e os logs;
4. teste login e uma consulta que use o banco.

Não apague os diretórios `/opt/ojuara/data` e `/opt/ojuara/backups` ao remover
ou recriar a Stack.
