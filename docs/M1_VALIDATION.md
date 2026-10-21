# M1 — Evidências de validação

Data: 21/10/2026. Branch local: `codex/m1-tenant-monitors`, baseada em `origin/main`
após a integração do PR #1. Pacotes backend/frontend: 0.2.0; API pública: `/api/v1`.

## Resultado

Implementação do M1 validada localmente. Foram executados 83 testes: 61 testes rápidos
de backend, seis de integração real e 16 de frontend. A publicação da branch e a
execução remota do CI não fazem parte destas evidências; o workflow foi atualizado
e seus comandos principais foram exercitados localmente.

| Verificação | Resultado |
| --- | --- |
| Backend sem serviços externos | 61 testes passaram. |
| Cobertura backend | 97,76% (mínimo configurado: 80%). |
| Integração PostgreSQL/TimescaleDB e Redis | Seis testes passaram. |
| Frontend Vitest | 16 testes passaram em cinco arquivos. |
| Ruff e formatação | Sem erros; 49 arquivos verificados. |
| ESLint e TypeScript | Sem erros. |
| Build Vite | Sucesso; 44 módulos; JS de aproximadamente 248 kB / 77 kB gzip. |
| Contrato e tipos gerados | `npm run api:check` passou. |
| Auditoria npm | Zero vulnerabilidades reportadas. |
| Imagens Docker | Backend e frontend construídos com sucesso. |
| Compose | Configurações padrão e de desenvolvimento válidas. |
| Stack isolada | API, frontend, PostgreSQL e Redis saudáveis; migration terminou com exit 0. |
| Alembic check | Nenhuma operação de upgrade nova detectada. |
| Migration em banco novo | 0001 → 0002 → 0001 → 0002; checks sem drift. |
| Nginx | `nginx -t` passou; cabeçalhos CSP, nosniff e anti-framing presentes. |

## Comportamentos comprovados

- Tenant B não consegue listar, ler, alterar ou excluir monitor de A, nem alterar
  membro de A. Os mesmos cenários passaram no PostgreSQL real.
- Owner, admin, operator e viewer obedecem à matriz RBAC; admin não promove outro
  administrador nem altera o owner.
- Alterar papel/ativação revoga sessões. O caso de uso revalida a autorização após
  adquirir o lock, cobrindo promoção concorrente do alvo para administrador.
- Uma sessão não pode referenciar usuário de outro tenant pela foreign key composta.
- O banco guarda Argon2id para senhas e SHA-256 para tokens de sessão.
- Logout, expiração e rotação de sessão invalidam o acesso anterior.
- Mutações sem CSRF, com CSRF inválido ou Origin externo são rejeitadas.
- Erros de validação e de persistência não refletem senhas nem detalhes SQL.
- Credenciais inválidas produzem a mesma mensagem genérica.
- O limitador retorna 429/Retry-After, falha fechado e funciona atomicamente no Redis real.
- URLs privadas/locais, protocolos indevidos, credenciais em URL e formas ambíguas são rejeitados.
- Paginação, pausa, remoção e conflitos de versão são verificados.
- Duas transações PostgreSQL concorrentes com a mesma versão resultam em uma
  alteração e um conflito. Uma linha previamente carregada no identity map também
  é atualizada antes de comparar sua versão sob lock.
- O fluxo de integração sem substituição da dependência de banco comprova commit
  entre requisições, logout e persistência real.
- A geração do contrato funciona sem segredos de deploy nem conexões abertas.
- O frontend inclui versão/CSRF nas mutações, preserva edições em conflito, confirma
  a remoção e não oferece promoção de admin a quem possui apenas esse papel.

## Verificação no navegador

Na stack local `pulse-m1-review`, com uma organização e contas fictícias:

1. Login como owner abriu o dashboard com acesso a monitores e membros.
2. Logout retornou à tela de autenticação.
3. Login como viewer mostrou a lista sem criar/editar/remover ou gerir membros.
4. Novo login como owner permitiu criar `Documentação pública` apontando para
   `https://example.org/docs` pela interface.
5. A edição do intervalo de 60 para 120 segundos foi salva e refletida na lista.
6. A sessão continuou válida após reconstruir containers e recarregar a página.

A verificação visual usou o navegador integrado em largura de desktop. O CSS tem
breakpoints responsivos; não foi feita uma auditoria completa de acessibilidade
ou uma matriz de dispositivos/navegadores móveis.

## Como reproduzir os testes

Backend, a partir de `backend/`:

```powershell
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not integration" --cov=pulse --cov-fail-under=80
```

Frontend, a partir de `frontend/`, após preparar o backend:

```powershell
npm ci
npm run api:check
npm test
npm run lint
npm run build
```

Integração, com PostgreSQL/Redis ativos e migrations aplicadas, a partir de `backend/`:

```powershell
$env:PULSE_DATABASE_URL = "postgresql+psycopg://pulse:pulse_local_only@127.0.0.1:5432/pulse"
$env:PULSE_REDIS_URL = "redis://127.0.0.1:6379/0"
$env:PULSE_INTEGRATION = "1"
uv run pytest -m integration -v
```

Os valores são exclusivos de desenvolvimento local. No ambiente desta execução,
os testes rápidos e de integração usaram Python 3.13.9 no Windows; a aplicação
também foi construída e executada em Python 3.12 dentro do Docker.

O round-trip de migration usou um banco novo chamado `pulse_m1_roundtrip`, no cluster
da stack isolada. A sequência aplicada foi:

```text
alembic upgrade head
alembic check
alembic downgrade 0001
alembic upgrade head
alembic check
```

Essa sequência só foi executada no banco dedicado e vazio. Não aplicar downgrade
em um banco com dados de usuário apenas para repetir a demonstração.

## Estado local e limites

A stack de demonstração usa os arquivos `compose.yaml` e `compose.dev.yaml`, com
o projeto Compose `pulse-m1-review`. Ela contém apenas dados fictícios e fica
disponível em http://localhost:8080. Para inspecionar/parar sem apagar volumes:

```powershell
docker compose -p pulse-m1-review -f compose.yaml -f compose.dev.yaml ps
docker compose -p pulse-m1-review -f compose.yaml -f compose.dev.yaml down
```

Não iniciar simultaneamente a stack padrão nas mesmas portas. Os testes de
integração removem ou revertem somente os próprios registros; dados da demonstração
foram preservados. Não houve alteração em serviços Docker de outros projetos.

Permanece um aviso de depreciação do TestClient/Starlette sobre o adaptador httpx;
não houve falha de teste associada. Não foram executados testes de carga, pentest,
deploy público nem o novo workflow remoto do M1. A compatibilidade do contrato é
verificada por geração e casos mínimos, não por um comparador semântico completo.

As limitações funcionais e de segurança estão no [guia do M1](M1_IMPLEMENTATION.md)
e no [ADR de autenticação](adr/0019-sessoes-e-autenticacao.md).
