# ADR 0018 — Compose, lockfiles e CI como base do M0

## Status
Aceito

## Contexto
Uma pessoa deve conseguir executar a base do Pulse e os testes a partir do README.
Os números 0002–0017 ficam reservados às decisões planejadas no contexto canônico.

## Forças da decisão
Reprodutibilidade, desenvolvimento Windows/Linux, poucas dependências operacionais,
configuração declarativa e detecção de falhas de infraestrutura.

## Alternativas consideradas
1. Instalar PostgreSQL e Redis manualmente em cada máquina.
2. Kubernetes desde o início, com maior custo de manutenção.
3. Docker Compose local e no CI, uv para Python e npm para TypeScript.

## Decisão
Usar Compose com TimescaleDB no mesmo PostgreSQL, Redis com AOF e `noeviction`,
job de migration e health checks. A stack padrão expõe somente frontend e API
no loopback; um override expõe bancos ao host para desenvolvimento.
Aplicações rodam sem root, com builds em etapas, filesystem somente leitura e
capacidades removidas. Imagens são identificadas por versão, dependências por
`uv.lock` e `package-lock.json`. CI valida lint, testes, migration em banco novo,
build das imagens e falha/recuperação de dependência.

## Consequências positivas
Ambientes reproduzíveis e um fluxo único de bootstrap. Readiness distingue falhas
de dependências de falhas do processo. Serviços internos não são expostos por padrão.

## Consequências negativas
Docker Desktop e virtualização precisam estar disponíveis. Tags de imagem podem
mudar sem mudar o nome; digests ainda precisam ser fixados antes do deploy.
As credenciais locais têm privilégios amplos e não servem para produção.

## Validação
Validar Compose, instalações congeladas, lint, testes e builds. O teste integrado
verifica schemas `core`/`telemetry`, revisão Alembic e extensão TimescaleDB.
O CI para Redis e espera readiness `503` mantendo liveness `200`, depois recupera.
O registro de evidências executadas fica em `docs/M0_VALIDATION.md`.

## Quando reconsiderar
No M6, medir disputa de recursos entre dados transacionais e telemetria.
No M9, configurar segredos, TLS, papéis PostgreSQL, backups, imagens por digest
e deploy conforme os requisitos do ambiente escolhido.

## Referências
- https://docs.docker.com/build/building/best-practices/
- https://docs.docker.com/compose/how-tos/production/
- https://docs.docker.com/compose/how-tos/environment-variables/best-practices/
- https://docs.timescale.com/self-hosted/latest/install/installation-docker/
