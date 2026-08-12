# Segurança

## Controles implementados

- Senhas com hash `scrypt` do Werkzeug.
- Perfis `SUPERADMIN`, `ADMIN` e `VENDEDOR`, validados nas rotas.
- Bloqueio temporário após tentativas de login.
- Cookies `HttpOnly`, `SameSite=Lax` e `Secure` em HTTPS.
- HSTS, bloqueio de iframe, `nosniff` e política de permissões.
- Container sem root, filesystem somente leitura e capabilities removidas.
- Porta da aplicação apenas na rede Docker privada.
- Banco e backup fora da imagem e do Git.

## Segredos

- `OJUARA_SECRET_KEY` deve ter pelo menos 32 caracteres e ser diferente por ambiente.
- Senhas e chaves ficam apenas nas variáveis protegidas do Portainer.
- Nunca cole segredos em issue, commit, documentação, chat ou captura de tela.
- Troque a senha inicial do superadministrador no primeiro acesso.

Se um segredo for exposto, gere outro, atualize a Stack e faça redeploy. A
troca da `SECRET_KEY` invalida sessões existentes, o que é desejável.

## Infraestrutura

- Somente Nginx Proxy Manager publica 80/443.
- Portainer e painéis administrativos devem permanecer restritos à interface local/VPN.
- Proxy Host aponta para o IP da rede `nginx-proxy_default`, nunca para o IP público.
- Mantenha `Block Common Exploits` ativo e TLS válido.
- IPs internos podem mudar após redeploy; confira antes de diagnosticar `502`.

## Rotina

- Atualizar imagens e sistema operacional em janela controlada.
- Revisar usuários ativos e privilégios mensalmente.
- Conferir renovações TLS e logs de autenticação.
- Manter cópia externa de backups.
- Não registrar dados pessoais reais em dev.

## Incidente

1. Preserve logs e horário do evento.
2. Revogue/troque credenciais potencialmente expostas.
3. Isole o serviço se houver exploração ativa.
4. Verifique integridade do banco e containers.
5. Restaure apenas de backup validado.
6. Documente causa, impacto, período e ações preventivas.
