# M0 — Evidências de validação

Data: 21/10/2026. Ambiente: Windows, Node.js 24.18.0, Python 3.13.9, uv 0.12.20.

## Atualização após a revisão do PR #1

As evidências abaixo complementam o registro inicial, preservado nas próximas seções.
O Docker voltou a estar disponível; a limitação inicial não bloqueia mais os testes
de containers. A consulta ao GitHub confirmou os três jobs verdes para `3685a71`
([execução original](https://github.com/ViniRover/incident-platform/actions/runs/39593149212)).

Após implementar os quatro ajustes solicitados na revisão:

- 13 testes de backend sem dependências externas passaram; cobertura de 91,06%.
- Ruff lint e formatação passaram (19 arquivos Python).
- O teste integrado com PostgreSQL/TimescaleDB e Redis reais passou, usando URLs IPv4
  explícitas no host Windows. A resolução de `localhost` não concluiu a primeira
  tentativa local, que foi interrompida antes de repetir com `127.0.0.1`.
- As duas imagens foram construídas e a stack isolada `pulse-pr1-review` ficou saudável.
- Migrations foram aplicadas em volume novo e `upgrade head` executado novamente.
- `nginx -t` passou e o proxy respondeu `200`.
- A API foi recriada com IP diferente (`172.20.0.4` → `172.20.0.6`), sem reiniciar o
  frontend; o proxy voltou a responder `200`.
- Testes de configuração verificam falha antes do startup quando falta qualquer URL.
- Um teste inspeciona os parâmetros entregues pelo SQLAlchemy ao driver libpq,
  incluindo timeout TCP e keepalives, e cobre o retorno `false` após timeout do driver.

O workflow agora executa push somente em `main` e eventos de pull request. Também
inclui regressões Linux para perda real de pacotes em conexão PostgreSQL já aberta
e recriação da API com mudança obrigatória de IP. A perda de pacotes usa uma regra
temporária no namespace de rede da API e remove a regra ao sair do passo.
Esses cenários precisam passar na nova execução de CI; os resultados originais
não são evidência dos ajustes posteriores. A revisão visual continua pendente.

## Resultado inicial (commit `3685a71`)

Base do M0 implementada. A conclusão integral do marco depende de executar a stack
Docker e os testes de integração reais; essa etapa está bloqueada pelo Docker
Desktop desta máquina. Nenhum resultado de CI remoto foi presumido.

| Verificação executada | Evidência |
| --- | --- |
| Ruff lint | Sem erros. |
| Ruff format | 16 arquivos formatados. |
| Testes backend sem serviços externos | 7 passaram; 1 teste de integração excluído. |
| Cobertura backend | 86,99%; mínimo do CI: 80%. |
| ESLint frontend | Sem erros. |
| Vitest | 4 testes passaram com Vitest 5.0.5. |
| TypeScript e build Vite | Sucesso; 35 módulos processados. |
| Auditoria npm após atualização | Zero vulnerabilidades reportadas. |
| Compose padrão e override dev | `docker compose config --quiet` passou nos dois casos. |
| Migration Alembic offline | SQL gerado com extensão, schemas e revisão `0001`. |

## Comportamentos comprovados pelos testes executados

- Quatro combinações de disponibilidade PostgreSQL/Redis no caso de uso.
- Liveness independente de serviços externos.
- Substituição da dependência de readiness e retorno HTTP `503`.
- Incremento da métrica HTTP para resposta `503`.
- Contrato OpenAPI versionado.
- Recuperação da tela depois de falha de rede.
- Integração entre componente, hook e adaptador HTTP, inclusive resposta `503`.
- Rejeição de resposta HTTP malformada e cancelamento ao desmontar o componente.

## Bloqueio de infraestrutura local

O Docker CLI e o Compose estão instalados. A tentativa de iniciar o Docker Desktop
falhou antes de disponibilizar o engine Linux. O log do host registrou:

```text
starting services: initializing Ingest server:
listening on unix://.../Docker/run/sailor-ingest.sock:
The file cannot be accessed by the system.
```

Não foi feita restauração de fábrica nem remoção de arquivos internos do Docker.
A instalação gerenciada do Python 3.12 pelo uv também falhou nesta máquina;
os testes locais usaram o Python 3.13 já instalado. Docker e CI estão configurados
para Python 3.12, que ainda precisa da validação nesses ambientes.

## Verificações pendentes para encerrar o M0

1. Iniciar o engine Docker Linux e executar `docker compose up -d --build --wait`.
2. Executar o teste integrado com banco novo e migrations aplicadas conforme README.
3. Validar a API pelo proxy do frontend e conferir a tela em navegador.
4. Reproduzir parada/recuperação do Redis: readiness `503`, liveness `200`,
   recuperação para readiness `200`.
5. Executar o workflow de CI após publicar o repositório no GitHub.

O workflow versionado automatiza builds, migrations, teste integrado, proxy e
falha/recuperação. A revisão visual no navegador continua sendo uma verificação
manual necessária. A geração SQL offline não substitui a aplicação da migration
em PostgreSQL real.
