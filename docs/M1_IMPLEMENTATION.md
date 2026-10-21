# M1 — Implementação explicada

Este guia acompanha o código e explica o que foi construído, por que foi organizado
assim e como reproduzir o comportamento. O [contexto canônico](PROJECT_CONTEXT.md)
continua sendo a referência do roadmap. O README permanece em inglês.

## 1. Preparação e preservação do trabalho existente

A implementação parte da main que recebeu o PR #1, na branch local
`codex/m1-tenant-monitors`. A alteração preexistente em `main.py`, que usa
`AsyncGenerator` no lifespan, foi preservada. O M1 não altera os processos futuros
de scheduler, workers ou incidentes.

## 2. Modelagem do banco

A migration `backend/migrations/versions/0002_identity_and_monitors.py` cria:

| Tabela | Responsabilidade |
| --- | --- |
| core.tenants | Organização, nome e slug único para login. |
| core.users | Usuário de uma organização, email normalizado, papel e hash da senha. |
| core.sessions | Hash do token de sessão, vínculo com usuário/tenant e expiração. |
| core.monitors | Configuração HTTP, versão, ativação e próximo horário de execução. |

Todos os registros de negócio estão ligados ao tenant. Email é único dentro do
tenant, não em toda a plataforma. Isso permite o mesmo email em organizações
distintas, com credenciais independentes. A sessão tem uma chave estrangeira
composta, evitando associar um usuário de A a uma sessão de B.

Monitores têm constraints de intervalo, timeout, status HTTP e versão. Há índice
para listagem por tenant e um índice parcial de monitores ativos por
`next_check_at`, preparando o M2 sem implementar o agendador antecipadamente.

O Alembic conhece o metadata dos modelos e filtra os schemas da aplicação para não
tratar tabelas internas do TimescaleDB como objetos que deveriam ser removidos.
`alembic check` detecta diferenças entre os modelos e o banco migrado.

## 3. Organização do backend

As features `identity` e `monitors` seguem o mesmo sentido de dependências:

```text
HTTP → caso de uso → contrato de repositório
                        ↑
                  adaptador SQLAlchemy
```

- `domain.py`: papéis, contexto autenticado e invariantes dos monitores; sem FastAPI
  ou SQLAlchemy.
- `application.py`: casos de uso e Protocols pequenos que descrevem o que precisam.
- `repository.py`/`models.py`: consultas e persistência com SQLAlchemy.
- `router.py`: validação e serialização HTTP, códigos de resposta e composição.
- `dependencies.py`: composição das dependências de identidade e da sessão atual.

As camadas são arquivos dentro de cada feature. Não foram criadas hierarquias vazias
nem um repositório genérico para todas as tabelas.

## 4. Transação por requisição

`platform/database.py` fornece uma Session por requisição. Os providers do FastAPI
reutilizam essa instância, de modo que autenticação e operação de negócio usam o
mesmo contexto transacional. A dependência tem escopo de função: commit acontece
antes de enviar a resposta; exceções causam rollback.

Criar organização, owner e sessão é uma única transação. Se o slug conflitar, nada
parcial deve ficar salvo. Testes verificam esse rollback. Em produção não há
`create_all()` no startup: a estrutura vem exclusivamente das migrations.

## 5. Cadastro, login e logout

Cadastro cria a organização e seu owner. Login recebe slug, email e senha. A senha
é verificada com Argon2id; nunca é salva nem retornada em texto puro. O cadastro
aceita frases de 15–128 caracteres, sem regras artificiais de maiúsculas/símbolos.
Quando a conta não existe, também é feita uma verificação de hash fictício, e a
mensagem de erro continua genérica.

Após autenticar, o servidor gera um token aleatório e guarda somente seu SHA-256.
O token bruto vai para um cookie HttpOnly com SameSite=Strict. O frontend guarda
o contexto de sessão em memória, não o cookie em localStorage. Cada requisição
revalida a sessão e o papel atual no PostgreSQL.

Logout exclui a sessão do servidor e remove o cookie. Login rotaciona o cookie
anterior. Mudança de papel ou ativação revoga as sessões do membro afetado.
Sessões expiram após 8 horas por padrão, configuráveis por ambiente.
A resolução usa SELECT sem lock de linha. Requisições já autenticadas podem
terminar com o papel anterior a uma revogação; a próxima requisição após o commit
é negada. Locks exclusivos continuam nas alterações de membros, não nas leituras.

## 6. CSRF, abuso e falhas

O navegador envia cookies automaticamente; por isso, mutações também precisam de
um token anti-CSRF. O servidor devolve `csrf_token` no cadastro, login e `/auth/me`;
o gateway envia esse valor em `X-CSRF-Token` nas alterações e no logout. A comparação
é resistente a diferenças de tempo. Origins fora da lista configurada são negadas.

Redis executa incremento e expiração em um script atômico para limitar cadastro e
login. Há limite por IP de cliente e por conta; as chaves não expõem email/IP em texto.
Se Redis estiver indisponível, novas autenticações falham de forma controlada;
sessões existentes continuam no PostgreSQL. Na borda, Nginx sobrescreve os headers
de IP/protocolo recebidos do cliente. Compose fixa apenas o IP do Nginx na rede
proxy e configura Uvicorn para confiar exclusivamente nesse endereço. Assim,
request.client.host identifica o cliente real visto pelo Nginx, e não o container
Nginx compartilhado por todos. Headers enviados diretamente à API por outros
peers são ignorados. Não se usa confiança global (*). Clientes sob um mesmo NAT
ainda compartilham o bucket; CDN/balanceador adicional requer configuração própria.
O limite de 10 tentativas por conta/minuto admite bloqueio direcionado: um atacante
pode esgotar continuamente o bucket de um tenant/email conhecido. Isso não revoga
sessões existentes. O ADR 0019 registra o risco aceito no M1 e a evolução futura
para backoff e dispositivo previamente validado; essas mitigações não estão prontas.

Erros de validação não refletem o valor enviado, protegendo senhas nas respostas.
Conflitos retornam 409, ausência de sessão 401, falta de permissão 403, recurso
inacessível 404 e indisponibilidade 503. Um limite excedido retorna 429 com Retry-After.
O adaptador HTTP busca o status pela hierarquia de classes do erro, preservando
o status de subclasses. Erros de aplicação sem mapeamento retornam 500 genérico,
sem expor detalhes internos nem gerar KeyError dentro do handler.

## 7. RBAC: autenticação não é autorização

Autenticação responde quem é o usuário. RBAC responde o que ele pode fazer.

| Operação | owner | admin | operator | viewer |
| --- | --- | --- | --- | --- |
| Consultar monitores | Sim | Sim | Sim | Sim |
| Criar/alterar/remover monitores | Sim | Sim | Sim | Não |
| Listar membros | Sim | Sim | Não | Não |
| Gerenciar operator/viewer | Sim | Sim | Não | Não |
| Gerenciar administradores | Sim | Não | Não | Não |
| Transferir propriedade | Fora do M1 | Fora do M1 | Não | Não |

Esconder um botão não autoriza uma ação: a API repete a verificação. Alterar o owner
pela API de membros é proibido. O tenant vem da sessão, e corpos de requisição com
campos extras como `tenant_id` são rejeitados.

## 8. CRUD de monitores e concorrência

Criar um monitor grava nome, URL, intervalo, timeout, status esperado e ativação.
A validação aceita apenas HTTP(S), rejeita credenciais em URL, fragments, hosts
locais, IPs privados/reservados e formas ambíguas de endereço. Não há requisição
HTTP ao destino neste marco. DNS rebinding e redirects precisam ser tratados no
worker antes de qualquer execução real no M2/M3.

MonitorConfig.create aplica validação e normalização a entradas novas/alteradas.
O construtor simples representa um snapshot persistido: o repositório reconstitui
os valores sem executar a política atual de entrada. Assim, uma regra futura não
impede listar ou abrir registros antigos para correção. Uma edição continua
precisando atender à política atual. Novos chamadores (por exemplo, importação)
devem usar a factory para entrada, não o construtor de hidratação.
Não houve afrouxamento de constraints nem migração de dados nesta alteração.
Quando uma regra mudar, planejar migração/estado explícito de configuração inválida
e impedir execução insegura no worker; conseguir ler um registro não autoriza executá-lo.

Listagens são paginadas (20 por padrão, máximo 100). Alterações e remoções exigem
`config_version`. A atualização bloqueia a linha, compara a versão recebida e
incrementa a versão de configuração. Uma versão antiga recebe 409. Um teste com
duas transações PostgreSQL concorrentes comprova uma atualização e um conflito.

O editor preserva os campos após erro. Em conflito, cancele, atualize a lista e
reabra o monitor antes de salvar. Pausar altera `is_active`; remover exige uma
confirmação explícita na interface. Remoção é física no M1; a retenção de histórico
de checks/incidentes deverá rever isso antes de adicionar relacionamentos futuros.

## 9. Contrato OpenAPI e frontend

FastAPI exporta `contracts/openapi.json` sem abrir conexões. O script
`scripts/export-contract.mjs` chama o exportador Python e openapi-typescript gera
`frontend/src/shared/api/schema.d.ts`. Os gateways usam openapi-fetch com esses
paths e DTOs; um endpoint ou payload incompatível passa a causar erro de TypeScript.

```powershell
cd backend
uv sync --frozen
cd ../frontend
npm ci
npm run api:generate
npm run build
```

Não edite o arquivo gerado manualmente. No CI, `api:check` regenera e detecta drift.
Testes também comparam o schema com a aplicação e mantêm os requisitos mínimos do
contrato v1. Esse controle não substitui uma análise semântica completa de breaking changes.

No React, `app/App.tsx` compõe o contexto de sessão e os gateways concretos.
`features/identity` contém formulário de autenticação e gestão de membros;
`features/monitors` contém editor, listagem e adaptador da API. Os componentes
recebem contratos por props, permitindo usar fakes nos testes. Tipos comuns de API
ficam em `shared/api`, e a API pública de cada feature passa por seu `index.ts`.

O dashboard distingue carregamento, vazio, erro, configuração ativa e configuração
pausada. Não exibe disponibilidade inventada: o M1 configura os monitores, mas ainda
não executa checks. Requests do cliente têm cancelamento e timeout de 12 segundos.

## 10. Infraestrutura e navegador

Compose continua com migration como job separado, usuário não root nas aplicações,
volumes e portas locais. Acrescentou-se a passagem explícita de duração da sessão,
origins permitidas e Secure no cookie. O desenvolvimento HTTP usa Secure=false;
um deploy HTTPS deve definir Secure=true e origins reais.

O Nginx mantém a resolução dinâmica do serviço API. Cabeçalhos de segurança incluem
CSP de mesma origem, proibição de framing, nosniff e política de referência. Arquivos
CSS/scripts permanecem locais, sem carregar fontes ou bibliotecas de terceiros em runtime.

## 11. Testes e CI

Os testes rápidos usam SQLite em memória somente como infraestrutura de teste, com
foreign keys habilitadas. Testes de integração repetem os cenários importantes em
PostgreSQL migrado. Cenários com savepoints fazem rollback dos próprios dados; o
fluxo com commit real remove apenas os registros criados pelo próprio teste.

Além do isolamento e RBAC, há testes de expiração, logout, revogação, hash de senha,
CSRF, Origin, 429, falha SQL, validação de URL, paginação e conflitos de versão.
O frontend testa formulários, leitura sem permissão de escrita, criação, edição
com conflito, confirmação de remoção, paginação e os headers/payloads dos gateways.

O CI mantém os três jobs do M0, acrescentando geração do contrato e verificação
de migration/metadata. A reversão para 0001 e aplicação de 0002 acontece apenas
no banco novo e vazio do job de integração, nunca em dados de usuário.

As métricas do M0 continuam disponíveis. `pulse_monitor_mutations_total` separa
create/update/delete com cardinalidade limitada. O contador mede mutações que
chegaram ao flush transacional; ele não é um registro de auditoria nem prova de commit.

## 12. Como experimentar

```powershell
docker compose up -d --build --wait
```

Abra http://localhost:8080, crie uma organização e guarde o slug para o login.
Cadastre um monitor, altere seu intervalo e pause a configuração. Crie um membro
viewer em Pessoas e acessos, saia e entre como esse usuário: a lista fica disponível
sem os controles de escrita. A API direta também nega a escrita com 403.

Para demonstrar isolamento, crie outra organização em uma sessão separada e tente
acessar o UUID do primeiro monitor pela API: a resposta deve ser 404. Os cenários
automatizados em `tests/scenarios.py` reproduzem isso sem manipulação manual de cookies.

Leia os resultados efetivamente executados em [M1_VALIDATION.md](M1_VALIDATION.md).

## 13. Limitações e próximos passos

O cadastro de membros usa uma senha inicial definida pelo administrador. Convites
de uso único, recuperação/troca de senha, verificação de email, MFA e checagem de
senhas comprometidas ainda não foram implementados. Esta é uma base local de M1,
não uma liberação para uso público sem completar o ciclo de identidade e deploy.

Ainda não há RLS, auditoria persistente, transferência de owner, identidade global
com múltiplas memberships nem limpeza automática de sessões expiradas. Há paginação
por offset, sem snapshot estável sob alterações concorrentes. O orçamento global
do readiness identificado na revisão do M0 continua separado deste marco.

No M2, os monitores configurados passam a alimentar scheduler/outbox/Redis Streams.
Antes de adicionar usuários reais, evolua identidade e segurança operacional conforme
o [ADR 0019](adr/0019-sessoes-e-autenticacao.md).

## 14. Ordem sugerida de leitura do código

1. `features/monitors/domain.py`: invariantes e entidades sem framework.
2. `features/identity/domain.py`: contexto e políticas de autorização.
3. `features/monitors/application.py`: caso de uso dependendo de um Protocol.
4. `features/monitors/repository.py`: filtro por tenant, lock e versão.
5. `platform/database.py`: ciclo da transação por requisição.
6. `features/identity/dependencies.py`: autenticação e CSRF na borda HTTP.
7. `features/identity/security.py` e `repository.py`: hash, sessão e persistência.
8. `features/monitors/router.py`: transformação de HTTP em caso de uso.
9. `frontend/src/shared/api` e os gateways: contrato gerado usado pelo cliente.
10. `MonitorDashboard.tsx`, `MonitorEditor.tsx` e `AuthForm.tsx`: composição da interface.
11. `tests/scenarios.py` e os testes de integração: evidências das garantias.

Os caminhos 1–8 são relativos a `backend/src/pulse/`.
