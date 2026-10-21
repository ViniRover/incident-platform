# Convenções de implementação

## Backend: features e dependências

Cada funcionalidade fica em `pulse/features/<feature>`. No M0, `health` demonstra
`application.py` (caso de uso e contrato), `infrastructure.py` (adaptadores),
`dependencies.py` (composição FastAPI) e `router.py` (contrato HTTP).
Features com regras de negócio passam a ter `domain/`, `application/`,
`infrastructure/` e `presentation/` quando o volume justificar. Não criar pastas vazias.

- Domínio não importa FastAPI, Redis nem SQLAlchemy.
- Casos de uso recebem dependências pelo construtor e dependem de contratos pequenos
  (`Protocol`); adaptadores implementam esses contratos por tipagem estrutural.
- Rotas validam/serializam HTTP e chamam casos de uso. A composição fica em providers
  com `Depends`; não usar `Depends` dentro das regras de negócio.
- Recursos como pools são criados no lifespan e fechados no shutdown.
- `platform/` contém apenas recursos técnicos compartilhados. Não virar uma pasta
  de serviços de negócio genéricos.
- Uma feature acessa outra por contrato público/caso de uso, nunca pelo repositório
  interno da outra feature. Novos entrypoints usam os mesmos casos de uso.
- Adicionar transações, sessão por unidade de trabalho e filtros obrigatórios de
  tenant ao implementar persistência de negócio no M1.

## Frontend: composição e limites

- `app/` compõe a aplicação e injeta implementações concretas.
- `features/<feature>/index.ts` é a API pública de cada feature.
- `shared/ui` recebe componentes visuais realmente compartilhados, sem regras de negócio.
- Componentes apresentam dados e emitem eventos por props; hooks gerenciam estado e
  ciclo de vida; adaptadores encapsulam HTTP e validação de respostas.
- Features recebem contratos específicos em vez de depender diretamente de `fetch`.
- Não compartilhar estado por conveniência: manter o estado perto dos consumidores.
- ESLint impede importação externa de diretórios internos das features.

## SOLID na prática

| Princípio | Aplicação |
| --- | --- |
| Responsabilidade única | Transporte, apresentação, estado e regras têm donos distintos. |
| Aberto/fechado | Novos adaptadores atendem contratos existentes sem alterar os consumidores. |
| Substituição | Fakes e adaptadores reais respeitam o mesmo comportamento, inclusive falhas. |
| Segregação de interfaces | Contratos pequenos, definidos pela necessidade do consumidor. |
| Inversão de dependências | Casos de uso e UI dependem de contratos; composition roots escolhem implementações. |

SOLID orienta fronteiras e testes; não exige classes em React, um container de DI
externo ou repositórios genéricos para cada tabela.

## Infraestrutura e mudanças

- Manter configuração declarativa no Compose e no CI, com lockfiles versionados.
- Não usar `latest`, não versionar `.env`, não embutir segredos nas imagens.
- Aplicações usam usuário não root, permissões reduzidas e builds em etapas.
- Dependências têm health checks e volumes nomeados. Migration é um job separado.
- Liveness não consulta serviços externos. Readiness informa capacidade de atendimento.
- Logs vão para stdout/stderr; métricas ficam em `/metrics`.
- Migrations são explícitas e revisadas; não executar `create_all()` no startup.
- Alterações arquiteturais relevantes exigem ADR com alternativas e evidências.
- Uma PR descreve problema, comportamento resultante, testes e limitações.

Estas escolhas seguem os guias oficiais de
[composição React](https://react.dev/learn/thinking-in-react),
[módulos FastAPI](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
[injeção de dependências](https://fastapi.tiangolo.com/tutorial/dependencies/) e
[builds Docker](https://docs.docker.com/build/building/best-practices/).
