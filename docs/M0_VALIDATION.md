# M0 — Evidências de validação

Data: 21/10/2026. Ambiente: Windows, Node.js 24.18.0, Python 3.13.9, uv 0.12.20.

## Resultado

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
