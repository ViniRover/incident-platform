# ADR 0019 — Sessões revogáveis e proteção da autenticação

## Status
Aceito no M1.

## Contexto
O dashboard precisa autenticar usuários, encerrar acessos e aplicar mudanças de papel
imediatamente. O M1 não requer autenticação distribuída entre serviços externos.

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
sessões já autenticadas continuam consultando PostgreSQL. O endereço usado pelo
limite de origem é o peer ASGI, sem confiar em X-Forwarded-For arbitrário.

Nginx aplica CSP de mesma origem, bloqueio de framing, nosniff e política de referência.
Validações e erros de persistência não refletem senhas ou detalhes SQL nas respostas.

## Consequências positivas
Revogação simples, ausência de chave JWT de assinatura e permissões sempre atuais.
Controles podem ser verificados por testes HTTP e de infraestrutura.

## Consequências negativas
Cada sessão depende de PostgreSQL e tem custo de consulta/lock por requisição.
Não há MFA, recuperação de senha, verificação de email, convite por email, troca de
senha ou bloqueio por lista de credenciais vazadas no M1. O administrador define
a senha inicial do membro; isso é uma limitação do fluxo local, não um convite seguro.
Antes de exposição pública, esses fluxos e o proxy confiável precisam ser tratados.
O limite por peer pode ser compartilhado atrás do Nginx até configurar ingress confiável.
Sessões expiradas precisam de rotina de limpeza operacional. CSP não elimina XSS.

## Validação
Testes cobrem hash de senha, ausência de token bruto no banco, expiração, logout,
rotação, revogação por mudança de papel, CSRF, Origin, 429 e falha de dependência.
O script Redis é testado no Redis real e o fluxo HTTP usa transações PostgreSQL reais.

## Quando reconsiderar
Adotar OIDC/MFA e convite de uso único antes de atender usuários externos. Rever
limites e parâmetros Argon2 com medição de capacidade. Implementar ciclo completo
de recuperação de conta, credenciais comprometidas e limpeza de sessões.

## Referências
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
