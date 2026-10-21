# ADR 0001 — Monólito modular por funcionalidades

## Status
Aceito

## Contexto
O Pulse precisa evoluir por marcos, preservando regras de negócio reutilizáveis
entre API e futuros processos de scheduler, workers e incidentes.

## Forças da decisão
Operação inicial simples, isolamento de responsabilidades, contratos testáveis,
SOLID e capacidade de separar processos sem duplicar regras.

## Alternativas consideradas
1. Microsserviços desde o início: contratos de rede e operação antecipados.
2. Organização global por camadas: uma pasta de routers, outra de services e outra
   de repositories; cada mudança se espalha pelo projeto.
3. Monólito modular por features, com camadas internas proporcionais à complexidade.

## Decisão
Adotar monorepo com `backend` e `frontend`. Backend organizado por features e
contratos `Protocol`, com DI por construtor e providers FastAPI na borda HTTP.
Frontend usa composição, props, hooks e gateways específicos por feature.
Adicionar camadas de domínio conforme aparecerem regras reais. Processos futuros
usarão entrypoints separados no mesmo pacote Python.

## Consequências positivas
Testes podem substituir dependências sem banco ou rede. Cada funcionalidade mantém
seus contratos, rotas e adaptadores próximos. Uma única cadeia de build e CI.

## Consequências negativas
Limites internos precisam de revisão e testes; a distribuição física não impede
imports indevidos. Backend e frontend evoluem no mesmo repositório.

## Validação
`health` demonstra caso de uso independente de framework, adaptadores Redis e
PostgreSQL e substituição via `dependency_overrides`. O frontend testa recuperação
de rede com gateway injetado e integração com o adaptador HTTP.
Comandos e resultados da validação do M0 ficam em `docs/M0_VALIDATION.md`.

## Quando reconsiderar
Após medir gargalos no M6 e comparar custo de operação, contratos e benefício
de extração no M8. Alto acoplamento observado nos testes exige revisar os limites
antes de extrair serviços.
