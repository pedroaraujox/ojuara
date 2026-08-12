# Continuidade do serviço

## Objetivos

Para a operação atual, adota-se como referência:

- RPO: até 24 horas, limitado ao intervalo padrão de backup.
- RTO: até 4 horas para falhas de aplicação; até 8 horas para reconstrução da VM.

Esses objetivos dependem de cópia externa recente e acesso ao Registro.br,
Portainer, Nginx Proxy Manager e GitHub.

## Cenários

| Falha | Resposta |
|---|---|
| Container parou | Ler logs, reiniciar Stack e validar `/saude` |
| Atualização defeituosa | Reverter commit e fazer redeploy |
| Banco corrompido | Interromper escrita e restaurar backup validado |
| Disco cheio | Liberar apenas artefatos identificados; preservar dados/backups |
| VM perdida | Recriar Docker/Portainer/NPM, Stack e restaurar banco externo |
| DNS/TLS | Validar registros A, portas 80/443 e renovação no NPM |

## Dependências para reconstrução

- Repositório público e branches `desenvolvimento`/`producao`.
- Variáveis secretas guardadas fora do Git.
- Backup externo do banco de produção.
- Inventário dos domínios e acesso ao DNS.
- Nome da rede compartilhada: `nginx-proxy_default`.

## Exercício

Semestralmente, simule a restauração em diretório e Stack isolados. Meça o
tempo, confirme login e fluxos críticos e atualize este documento se o RTO não
for atingido.
