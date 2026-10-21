# ADR 0019 — Sessões revogáveis e proteção da autenticação

## Status
Aceito no M1.

## Contexto
O dashboard precisa autenticar usuários, encerrar acessos e aplicar mudanças de papel
nas próximas requisições após o commit. O M1 não requer autenticação distribuída
entre serviços externos.

## Forças da decisão
Revogação, armazenamento de credenciais, CSRF, resistência a tentativas automatizadas
e uma implementação pequena o bastante para ser auditada e testada.

## Alternativas consideradas
1. JWT em localStorage: fácil de enviar, com revogação e exposição a scripts adicionais.
2. OIDC gerenciado: boas capacidades de identidade, mas acrescenta provedor e integração.
3. Sessão opaca persistida no PostgreSQL e cookie HttpOnly no browser.

## Decisão
Usar tokens aleatórios com 256 bits, persistindo somente seu SHA-256 em `core.sessions`.
O cookie tem HttpOnly, SameSite=Strict, Path=/ e duração configurável (8 horas por
padrão). Em HTTPS, `PULSE_COOKIE_SECURE=true` é obrigatório operacionalmente.
O cookie não fica em localStorage/sessionStorage nem aparece nas respostas JSON.

Cada requisição revalida validade da sessão, usuário ativo, tenant e papel no banco.
Login rotaciona a sessão atual. Logout e alterações de papel/ativação revogam sessões.
Resolver a sessão usa SELECT sem FOR SHARE: uma leitura autenticada não deve
adquirir lock de linha nem atrasar a revogação até o fim da requisição. Mantemos
populate_existing para não reaproveitar estado antigo do identity map.
Aceitamos que uma requisição que já resolveu a identidade termine com o papel
anterior, inclusive uma mutação. Após o commit da revogação, a próxima requisição
é negada. Alterações de membros mantêm o lock exclusivo e a revalidação do alvo.
Senhas têm 15–128 caracteres e hash Argon2id com 19 MiB, duas iterações e paralelismo 1.
Não são impostas combinações artificiais de classes de caracteres. Um hash fictício
também é verificado quando a conta não existe, e erros de login são genéricos.

Mutações autenticadas exigem `X-CSRF-Token`, derivado do token de sessão por hash
com separação de domínio e retornado na resposta de sessão. Origin é validado quando
presente; requests cross-site sem Origin também são bloqueados pelo Fetch Metadata.
Clientes de API sem Origin continuam possíveis, mas precisam da sessão e do CSRF.
Origin e SameSite são camadas adicionais, não substitutos do token CSRF.

Redis limita cadastro e login com incremento e expiração atômicos. Chaves são
resumos sem email/IP legíveis. Redis indisponível impede novas autenticações;
sessões já autenticadas continuam consultando PostgreSQL. O limite usa o cliente
ASGI depois do tratamento de proxy do Uvicorn, nunca lê X-Forwarded-For diretamente.
Na stack Compose, o Nginx de borda sobrescreve X-Forwarded-For e X-Real-IP com
$remote_addr e X-Forwarded-Proto com $scheme. A API usa --proxy-headers e
--forwarded-allow-ips apenas para o IP fixo desse Nginx (PULSE_PROXY_IP).
A rede proxy tem subnet configurável (PULSE_PROXY_SUBNET), separada da rede dos
bancos. O IP fixo fica fora de PULSE_PROXY_DYNAMIC_RANGE, evitando que a API o
receba antes da inicialização do Nginx. A API participa das duas redes; o Nginx
participa somente da rede proxy.
Não confiar em *, no gateway Docker ou na subnet inteira. Conexões diretas à API
continuam usando o peer TCP, ignorando headers de outros containers/host.
A imagem backend fora do Compose desabilita proxy headers por padrão.

Nginx aplica CSP de mesma origem, bloqueio de framing, nosniff e política de referência.
Validações e erros de persistência não refletem senhas ou detalhes SQL nas respostas.

## Consequências positivas
Revogação simples, ausência de chave JWT de assinatura e permissões consultadas
a cada resolução da sessão, sem lock de linha em leituras autenticadas.
Controles podem ser verificados por testes HTTP e de infraestrutura.

## Consequências negativas
Cada sessão depende de PostgreSQL e tem custo de consulta por requisição.
Revogação não cancela requisições em andamento. Se houver necessidade de revogação
estritamente serializada com operações sensíveis, adicionar um mecanismo específico
nesses casos de uso, medido em carga, em vez de bloquear todas as leituras.
Não há MFA, recuperação de senha, verificação de email, convite por email, troca de
senha ou bloqueio por lista de credenciais vazadas no M1. O administrador define
a senha inicial do membro; isso é uma limitação do fluxo local, não um convite seguro.
Antes de exposição pública, esses fluxos precisam ser tratados. Clientes atrás de
um mesmo NAT ainda compartilham o limite por IP. Um balanceador/CDN antes deste
Nginx exige redesenhar explicitamente a cadeia de confiança; não basta aceitar
o X-Forwarded-For externo. Subnets devem evitar conflitos com VPNs/outras stacks.
Sessões expiradas precisam de rotina de limpeza operacional. CSP não elimina XSS.

### Risco aceito: bloqueio direcionado por conta

O limite login-account é de 10 tentativas por 60 segundos por tenant/ email
normalizado, incluindo tentativas válidas. Quem conhece esses identificadores
pode consumir o bucket repetidamente e impedir novos logins da vítima, mesmo de
outro IP. Não é bloqueio persistente: cada janela expira, mas o atacante pode
renovar o abuso a cada janela. Sessões já abertas não são revogadas pelo limite.
O limite por IP não elimina um ataque direcionado/distribuído. Aceitamos essa
limitação no M1 local; ela não está resolvida pela correção de proxy.

Antes de exposição pública, avaliar backoff progressivo por conta combinado com
limites por origem e um caminho controlado para dispositivo previamente validado.
Dispositivo confiável deve usar uma credencial revogável, não IP, User-Agent ou
header fornecido pelo cliente. Alertas, recuperação segura e MFA complementam o
controle. Não desabilitar o limite por conta sem uma proteção substituta.

## Validação
Testes cobrem hash de senha, ausência de token bruto no banco, expiração, logout,
rotação, revogação por mudança de papel, CSRF, Origin, 429 e falha de dependência.
Um teste PostgreSQL resolve a sessão em transação READ ONLY, mantém essa leitura
aberta durante atualização/revogação em outra conexão com lock_timeout de 500 ms
e verifica que a sessão removida retorna 401 na próxima requisição.
O script Redis é testado no Redis real e o fluxo HTTP usa transações PostgreSQL reais.
O teste opt-in test_proxy_identity.py usa dois containers com IPs TCP distintos:
esgota login/cadastro de um sem bloquear o outro, tenta falsificar headers na borda
e conecta diretamente à API para verificar que somente Nginx é confiável.

## Quando reconsiderar
Adotar OIDC/MFA e convite de uso único antes de atender usuários externos. Rever
limites e parâmetros Argon2 com medição de capacidade. Implementar ciclo completo
de recuperação de conta, credenciais comprometidas e limpeza de sessões.

## Referências
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- https://www.postgresql.org/docs/17/explicit-locking.html#LOCKING-ROWS
