# Pulse — contexto canônico do projeto

> Este documento substitui, para fins de continuidade, as discussões anteriores do projeto.
> Cassandra foi descartado. React e FastAPI estão confirmados, e a arquitetura abaixo é a base que deve ser mantida nas próximas decisões.

## Pedido consolidado do usuário

Construir o **Pulse**, uma plataforma multi-tenant de monitoramento de disponibilidade e incidentes, mantendo o seguinte fluxo:

| Passo | Quem faz | O que acontece |
| ---: | --- | --- |
| 1 | Dashboard → API | O cliente cadastra um monitor, por exemplo `https://loja.com` a cada minuto. A API valida e grava no PostgreSQL. |
| 2 | Agendador | A cada poucos segundos, lê no PostgreSQL os monitores vencidos e coloca um job para cada um na fila. |
| 3 | Workers | Workers consomem jobs em paralelo, fazem a requisição HTTP e gravam status e tempo de resposta no TimescaleDB. |
| 4 | Motor de incidentes | Lê os resultados; se 2 de 3 regiões falharem, abre um incidente no PostgreSQL. Quando o serviço volta, fecha o incidente. |
| 5 | Notificador | Recebe eventos de incidente aberto ou fechado e notifica por email, webhook ou Slack sem duplicar alertas. |
| 6 | Cache → página pública | O estado da página é projetado no Redis. A página pública lê do cache para suportar picos sem consultar o banco a cada request. |

Stack mantida:

- React + TypeScript;
- FastAPI + Python;
- PostgreSQL;
- TimescaleDB;
- Redis Streams;
- Redis como cache;
- OpenTelemetry, Prometheus e Grafana;
- Docker Compose inicialmente, evoluindo para Kubernetes, Render ou Fly.io quando justificado.

Cada marco deve terminar com código funcionando, testes e pelo menos um ADR curto em `docs/adr/NNNN-titulo.md`. Os ADRs são a parte principal do portfólio: devem demonstrar a decisão, alternativas, trade-offs, evidências e condições para revisão.

## Resposta e decisões arquiteturais

### Princípios

1. TimescaleDB será inicialmente uma extensão do mesmo PostgreSQL, com separação lógica por schemas.
2. Redis não será fonte da verdade. Fila e cache devem ser recuperáveis ou reconstruíveis.
3. O motor de incidentes será acionado por eventos e consultará resultados persistidos para completar o quórum.
4. O sistema aceita entrega **at-least-once** e torna seus consumidores idempotentes.
5. A arquitetura começa como monólito modular e processos separados no mesmo monorepo. Extrações físicas só ocorrerão mediante evidência.

Estrutura inicial do banco:

```text
PostgreSQL + TimescaleDB
├── core
│   ├── tenants
│   ├── users
│   ├── monitors
│   ├── incidents
│   ├── outbox
│   └── status_page_projection
└── telemetry
    ├── check_results
    └── agregados
```

Usar o mesmo cluster inicialmente reduz operação e permite transações entre resultados e outbox. O custo aceito é o risco de a carga de séries temporais afetar dados transacionais. A separação física deve ser reavaliada após os testes de carga do M6.

## Passo 1 — Dashboard, API e domínio

**Escolha:** React + TypeScript, FastAPI, PostgreSQL, SQLAlchemy e Alembic.

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Multi-tenancy | `tenant_id` por linha | Schema ou banco por tenant | Operação simples, mas exige disciplina em todas as consultas. |
| Autorização | RBAC na aplicação | PostgreSQL RLS ou serviço externo | Regras ficam explícitas no domínio, mas um filtro esquecido pode vazar dados. |
| Contrato | OpenAPI gerado pelo FastAPI | Tipos mantidos manualmente | Reduz divergência, mas adiciona geração de código no frontend. |
| Arquitetura | Monólito modular | Microsserviços desde o início | Menor custo operacional, mas requer fronteiras internas claras. |
| Migrations | Alembic | SQL manual | Histórico reproduzível, mas migrations precisam ser revisadas como código. |

Habilidades demonstradas:

- isolamento entre tenants;
- autenticação versus autorização;
- contratos evolutivos;
- migrations reproduzíveis;
- fronteiras em um monólito modular.

ADRs planejados:

```text
docs/adr/0001-monolito-modular.md
docs/adr/0002-multitenancy-por-tenant-id.md
docs/adr/0003-contrato-openapi-e-tipos-typescript.md
```

Evidências esperadas:

- tenant A não acessa dados do tenant B;
- testes de RBAC;
- banco criado do zero pelo CI;
- cliente TypeScript gerado do OpenAPI;
- política de versionamento da API.

## Passo 2 — Agendador e fila

**Escolha:** serviço Python, PostgreSQL como fonte dos agendamentos, `FOR UPDATE SKIP LOCKED`, transactional outbox e Redis Streams.

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Agendamento | `next_check_at` no PostgreSQL | Um job persistido por monitor no APScheduler | Modelo simples e centralizado, mas o banco recebe polling periódico. |
| Coordenação | `FOR UPDATE SKIP LOCKED` | Scheduler único com advisory lock | Permite réplicas ativas, mas aumenta a complexidade transacional. |
| Fila | Redis Streams | RabbitMQ, Kafka ou SQS | Menos infraestrutura, mas menos recursos de broker. |
| Garantia | At-least-once | Exactly-once presumido | Jobs podem ser reenviados; idempotência é obrigatória. |
| Publicação | Transactional outbox | Atualizar PostgreSQL e chamar `XADD` diretamente | Evita perder jobs, mas adiciona tabela e publisher. |

Fluxo:

```text
1. Buscar monitores vencidos com SKIP LOCKED.
2. Gerar check_id determinístico.
3. Atualizar next_check_at.
4. Inserir job na scheduler_outbox.
5. Confirmar transação.
6. Publisher enviar a outbox ao Redis Streams.
```

Identidade do job:

```text
check_id = UUIDv5(monitor_id + region + scheduled_at + config_version)
```

Se o publisher publicar e cair antes de marcar a outbox, a mensagem poderá ser duplicada, mas continuará representando o mesmo job lógico.

Habilidades demonstradas:

- entrega at-least-once;
- idempotência por identidade de negócio;
- coordenação sem lock global;
- solução do dual write entre PostgreSQL e Redis;
- back-pressure e recuperação após atrasos.

ADRs planejados:

```text
docs/adr/0004-agendador-orientado-pelo-postgresql.md
docs/adr/0005-redis-streams-e-entrega-at-least-once.md
docs/adr/0006-transactional-outbox-do-agendador.md
```

Evidências esperadas:

- duas réplicas do scheduler sem duplicação lógica;
- recuperação da outbox após reinicialização;
- teste de queda após publicar e antes de marcar;
- métrica da idade do job mais atrasado;
- política de coalescência depois de uma parada longa.

## Passo 3 — Workers e resultados

**Escolha:** workers Python com `asyncio`, HTTPX, Redis Streams e TimescaleDB.

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Concorrência | `asyncio` | Threads ou processos síncronos | Eficiente para I/O, mas requer limites explícitos. |
| Cliente HTTP | HTTPX `AsyncClient` compartilhado | Requests ou aiohttp | Pooling e integração assíncrona, mas timeouts precisam ser ajustados. |
| Escala | Réplicas horizontais | Um worker com concorrência muito alta | Isola falhas, mas depende da coordenação da fila. |
| Regiões | Stream/pool por região | Campo `region` em stream único | Isolamento claro, mas cria mais streams e deploys. |
| Retry HTTP | Apenas falhas transitórias | Retry indiscriminado | Evita amplificação e não esconde indisponibilidade real. |
| Persistência | Resultado e outbox na mesma transação | Gravar resultado e publicar separadamente | Evita resultado sem avaliação; pressupõe Timescale no mesmo cluster. |

Fluxo:

```text
XREADGROUP
    ↓
validação de SSRF
    ↓
HTTP check
    ↓
BEGIN
    INSERT check_result
    INSERT check.recorded na outbox
COMMIT
    ↓
XACK
```

Controles obrigatórios:

- concorrência global;
- limite por tenant;
- limite por hostname;
- timeouts separados;
- limite de tamanho da resposta;
- shutdown gracioso;
- recuperação de mensagens pendentes;
- DLQ para mensagens inválidas;
- proteção contra SSRF, redirects maliciosos e DNS rebinding.

Habilidades demonstradas:

- concorrência não equivale a capacidade infinita;
- back-pressure em todas as camadas;
- timeouts como parte do contrato;
- retry pode amplificar falhas;
- isolamento de vizinhos barulhentos;
- ACK somente depois do efeito durável.

ADRs planejados:

```text
docs/adr/0007-workers-assincronos-com-httpx.md
docs/adr/0008-limites-de-concorrencia-e-back-pressure.md
docs/adr/0009-protecao-ssrf-nos-workers.md
```

Evidências esperadas:

- worker morto antes do ACK e job recuperado;
- benchmark de concorrência;
- endpoints lentos e timeouts;
- tenant tentando monopolizar a fila;
- bloqueio de localhost, IP privado e metadata de cloud.

## Passo 4 — Motor de incidentes

**Escolha:** processo Python separado, máquina de estados explícita, quórum por rodada e estado oficial no PostgreSQL.

O motor será event-driven, mas continuará lendo os resultados persistidos:

```text
Worker grava resultado
        ↓
Outbox publica check.recorded
        ↓
Motor recebe o evento
        ↓
Consulta resultados da rodada
        ↓
Calcula quórum e transição
```

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Detecção | Evento `check.recorded` | Polling periódico | Menor latência e menos consultas vazias, mas depende da entrega de eventos. |
| Estado | Máquina explícita em Python | Condicionais espalhadas ou biblioteca genérica | Mais código de domínio, porém comportamento auditável. |
| Concorrência | `SELECT FOR UPDATE` no estado do monitor | Controle otimista | Fácil de raciocinar, mas serializa eventos do mesmo monitor. |
| Quórum | Resultados agrupados por rodada | Últimos N resultados sem janela | Determinístico, mas precisa tratar regiões atrasadas. |
| Deduplicação | Inbox `processed_events` | Confiar na fila | Impede aplicar transição duas vezes, ao custo de estado adicional. |
| Flapping | Rodadas consecutivas e cooldown | Alertar em toda mudança | Menos ruído, mas aumenta o tempo de confirmação. |

Máquina de estados:

```text
UNKNOWN
   ↓ quórum saudável
UP
   ↓ falha parcial
DEGRADED
   ↓ quórum de falha por N rodadas
DOWN
   ↓ quórum saudável
RECOVERING
   ↓ estabilidade por M rodadas
UP
```

Configuração inicial sugerida:

```text
Abrir incidente:
    2 de 3 regiões falham por 2 rodadas consecutivas

Resolver incidente:
    2 de 3 regiões funcionam por 2 rodadas consecutivas

Prazo da rodada:
    timeout do monitor + margem operacional
```

Habilidades demonstradas:

- eventos duplicados e fora de ordem;
- observação versus estado oficial;
- latência versus redução de falso positivo;
- estados intermediários para falhas parciais;
- consumidores idempotentes.

ADRs planejados:

```text
docs/adr/0010-motor-de-incidentes-orientado-a-eventos.md
docs/adr/0011-maquina-de-estados-e-quorum-regional.md
docs/adr/0012-deduplicacao-com-consumer-inbox.md
```

Evidências esperadas:

- falha em apenas uma região;
- falha em 2 de 3 regiões;
- evento duplicado;
- resultados fora de ordem;
- região sem resposta;
- recuperação parcial;
- flapping;
- eventos simultâneos para o mesmo monitor.

## Passo 5 — Notificador

**Escolha:** transactional outbox no PostgreSQL, worker próprio, chave de deduplicação, retry exponencial e DLQ.

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Criação | Outbox na mesma transação do incidente | Chamar canal diretamente | Incidente não depende do provedor, mas a entrega é assíncrona. |
| Garantia | At-least-once com deduplicação | Exactly-once presumido | Chamadas externas podem repetir e exigem chave estável. |
| Retry | Backoff exponencial com jitter | Intervalo fixo | Reduz pressão, mas pode aumentar o tempo de entrega. |
| Falha permanente | DLQ | Retry infinito ou descarte | Preserva diagnóstico, mas exige inspeção e replay. |
| Canais | Adaptadores independentes | Condicionais no worker | Melhor evolução e testes, com mais interfaces. |

Chave de deduplicação:

```text
incident_id + transition_version + channel + destination
```

Habilidades demonstradas:

- banco e provedor externo não compartilham transação;
- exatamente uma vez não deve ser presumido;
- retries precisam de limite;
- DLQ precisa de inspeção e replay;
- falhas externas não devem impedir a transição do incidente.

ADRs planejados:

```text
docs/adr/0013-outbox-de-notificacoes.md
docs/adr/0014-retry-deduplicacao-e-dlq.md
```

Evidências esperadas:

- provedor indisponível;
- timeout depois de o provedor aceitar;
- reinicialização durante entrega;
- evento duplicado;
- envio para DLQ;
- replay sem alerta duplicado.

## Passo 6 — Cache e página pública

**Escolha:** read model durável no PostgreSQL, projeção no Redis e cache HTTP/CDN.

```text
Incidente muda
    ↓
Atualiza status_page_projection no PostgreSQL
    ↓
Insere status_page.changed na outbox
    ↓
Projection worker atualiza Redis
    ↓
Página pública lê Redis
    ↓
CDN armazena a resposta
```

| Decisão | Escolha | Alternativas | Trade-off |
| --- | --- | --- | --- |
| Modelo de leitura | Projeção pré-calculada | Consultar incidentes por request | Leitura rápida, mas consistência eventual. |
| Redis | Cache descartável | Fonte exclusiva | Reconstruível, mas exige reidratação. |
| Invalidação | Evento e versão da projeção | Somente TTL | Atualização rápida, mas pipeline mais complexo. |
| HTTP | `ETag` e `Cache-Control` | Apenas Redis | Menos carga, mas aceita conteúdo brevemente antigo. |
| CDN | Cachear página pública | FastAPI atender tudo | Absorve picos, mas invalidação global não é instantânea. |

Habilidades demonstradas:

- cache não é fonte da verdade;
- invalidação depende do frescor exigido;
- read models trocam consistência imediata por desempenho;
- picos acontecem durante incidentes;
- página pública deve ser desacoplada da API administrativa.

ADRs planejados:

```text
docs/adr/0015-read-model-da-pagina-de-status.md
docs/adr/0016-redis-cache-e-invalidacao.md
docs/adr/0017-cache-http-e-cdn.md
```

Evidências esperadas:

- Redis apagado e reconstruído;
- mudança de incidente refletida no cache;
- teste de pico com cache quente e frio;
- comportamento com projection worker atrasado;
- hit ratio e idade da projeção.

## Roadmap e narrativa de aprendizado

| Marco | Decisão principal a defender | Evidência de aprendizado |
| ---: | --- | --- |
| M0 | Monorepo, convenções, Compose e CI como contrato | Uma nova pessoa executa projeto e testes usando apenas o README. |
| M1 | Shared schema com `tenant_id`, RBAC e contratos OpenAPI | Testes provam isolamento entre tenants e evolução compatível da API. |
| M2 | Scheduler ativo-ativo, Redis Streams e at-least-once | Duplicações e crashes são reproduzidos sem perda lógica de jobs. |
| M3 | TimescaleDB, índices, retenção e downsampling | `EXPLAIN ANALYZE` e benchmarks sustentam índices e agregações. |
| M4 | Máquina de estados, quórum, inbox/outbox e DLQ | Falhas parciais, duplicação e reordenação são cobertas por testes. |
| M5 | OpenTelemetry, SLIs, SLOs e error budgets | Um check é rastreado do scheduler até a notificação. |
| M6 | Capacidade medida e cache em camadas | Limite e gargalo dominante são demonstrados com dados. |
| M7 | Back-pressure, isolamento e shutdown gracioso | O sistema degrada de forma controlada quando dependências falham. |
| M8 | Extração baseada em evidência | Contrato, custo e benefício da separação são comparados. |
| M9 | Deploy seguro, expand/contract e runbooks | Deploy e rollback são executados sem indisponibilidade evitável. |
| M10 | Pulse v2 baseado nas medições | Estimativas e mudanças têm números e critérios verificáveis. |

## Definition of Done de cada marco

Cada marco só termina quando houver:

- funcionalidade executável;
- testes unitários;
- pelo menos um teste de integração;
- migrations reproduzíveis;
- métricas relevantes;
- documentação de execução;
- demonstração do principal modo de falha;
- ADR com alternativas e trade-offs;
- evidência mensurável;
- limitações conhecidas e condição para rever a decisão.

## Template de ADR

```markdown
# ADR NNNN — Título

## Status
Aceito

## Contexto
Qual problema estamos resolvendo?

## Forças da decisão
Quais requisitos e restrições importam?

## Alternativas consideradas
1. Alternativa A
2. Alternativa B
3. Alternativa C

## Decisão
O que escolhemos e por quê?

## Consequências positivas
O que ficou mais simples ou seguro?

## Consequências negativas
Que custo e limitação aceitamos?

## Validação
Quais testes, métricas ou experimentos sustentam a escolha?

## Quando reconsiderar
Que sinais indicariam que a decisão deixou de ser adequada?
```

## Orientação para futuras conversas

Ao continuar o projeto, usar este documento como fonte principal de contexto. Decisões posteriores podem alterá-lo, mas mudanças arquiteturais devem ser explícitas e acompanhadas de ADR. O objetivo do portfólio não é apenas mostrar ferramentas, mas demonstrar por que foram escolhidas, quais custos introduzem e quais evidências justificam mantê-las ou substituí-las.

## Estado implementado — M1

O M0 foi integrado pelo PR #1. O M1 foi desenvolvido na branch local
`tenant-monitors` (renomeada de `codex/m1-tenant-monitors`), mantendo a arquitetura acima e a alteração preexistente
do lifespan em `main.py`.

Foram implementados cadastro de organização/owner, login/logout com sessão opaca
revogável, senhas Argon2id, cookie HttpOnly, CSRF e limitação de tentativas no Redis.
O RBAC usa owner/admin/operator/viewer. Usuários pertencem a um tenant; não há
identidade global compartilhada entre organizações nesta versão.

O CRUD de monitores tem filtros obrigatórios por tenant, paginação, validação
preliminar de URL e controle de edição por config_version. O dashboard React usa
tipos e cliente derivados do OpenAPI. Monitores ainda não executam checks.

ADRs adicionados: 0002 (multi-tenancy/RBAC), 0003 (contrato OpenAPI/cliente) e 0019
(autenticação/sessões). A explicação detalhada está em `docs/M1_IMPLEMENTATION.md`;
os resultados locais e limitações estão em `docs/M1_VALIDATION.md`.

A validação local inclui 61 testes rápidos de backend, seis de integração real,
16 de frontend, builds, verificação de contrato, migrations em banco novo e
round-trip de migration em banco dedicado. O CI remoto do M1 depende da futura
publicação da branch; essa evidência original não certifica commits posteriores.

A revisão do PR #3 identificou que o limite por IP era compartilhado pelo proxy.
A correção sobrescreve headers no Nginx e limita a confiança do Uvicorn ao IP fixo
desse container em uma rede proxy dedicada. Um teste de deployment com dois IPs
TCP reais cobre isolamento de buckets e falsificação de headers. Não ampliar a
confiança para * ou para toda a subnet. As observações sobre revalidação de
MonitorConfig na leitura e locks FOR SHARE por requisição continuam pendentes
para antes do M2; não foram alteradas pela correção de proxy.

Antes de uso público, completar convites, recuperação/troca de senha, verificação
de email e demais controles de identidade/deploy descritos no ADR 0019. No M2,
continuar pelo agendador/outbox/Redis Streams definido neste documento.
