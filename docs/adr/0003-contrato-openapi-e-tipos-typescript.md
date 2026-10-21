# ADR 0003 — OpenAPI versionado e cliente TypeScript tipado

## Status
Aceito no M1.

## Contexto
Campos de formulário, respostas e endpoints não devem manter contratos divergentes
entre FastAPI e React. Mudanças precisam ser detectadas antes do deploy.

## Forças da decisão
Fonte única, reprodução offline, tipos reais usados pelos gateways e compatibilidade.

## Alternativas consideradas
1. Interfaces e URLs mantidas manualmente em cada feature.
2. Gerar um SDK completo com runtime próprio a partir de templates.
3. Gerar tipos com openapi-typescript e usar openapi-fetch como cliente tipado.

## Decisão
FastAPI gera o contrato canônico em `contracts/openapi.json`. O exportador instancia
a aplicação com configuração explícita sem abrir conexões. Um script Node exporta
o schema e o gerador produz `frontend/src/shared/api/schema.d.ts`.

Os gateways de identidade e monitores usam openapi-fetch parametrizado pelos paths
gerados. Defaults do backend permanecem opcionais no tipo de entrada por meio de
`--default-non-nullable false`. Tipos de saída, IDs de operação e erros esperados
são publicados pelo mesmo schema. DTOs de formulário usam esses tipos.

`npm run api:generate` atualiza os artefatos. `npm run api:check` regenera e compara
os arquivos versionados no CI. Um teste compara o schema salvo com o gerado em
memória e mantém um contrato mínimo para entradas e respostas essenciais do M1.

Toda API de produto usa `/api/v1`. Adições opcionais são preferidas; remover campos,
adicionar entradas obrigatórias ou alterar significado exige uma versão de API nova
ou uma migração explícita com período de compatibilidade. A versão de implementação
0.2.0 não altera o prefixo v1.

## Consequências positivas
O TypeScript detecta payloads e paths incompatíveis. Não é necessário copiar DTOs
manualmente. A geração não depende de um servidor rodando ou de credenciais reais.

## Consequências negativas
É necessário preparar o ambiente Python antes da geração. Tipos TypeScript não
validam JSON arbitrário em runtime; o servidor continua responsável pela validação.
O teste de contrato mínimo não é um comparador semântico completo de OpenAPI.

## Validação
CI regenera contrato e tipos, valida ausência de drift e compila o frontend. Testes
verificam envio de config_version e CSRF pelo cliente e tradução de erros HTTP.
Testes de contrato cobrem entradas mínimas, campos de sessão, papéis e operationIds.

## Quando reconsiderar
Adicionar comparação semântica completa e consumidores externos quando houver uma
API pública estável com clientes independentes. Gerar SDKs adicionais se surgirem
consumidores em outras linguagens.

## Referência
https://openapi-ts.dev/openapi-fetch/
