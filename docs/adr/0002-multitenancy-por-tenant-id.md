# ADR 0002 — Multi-tenancy por tenant_id e RBAC na aplicação

## Status
Aceito no M1.

## Contexto
Cada organização precisa gerenciar usuários e monitores sem acessar dados de outra.
Manter um banco por cliente elevaria a operação antes de medir uma necessidade real.

## Forças da decisão
Isolamento verificável, migrations únicas, consultas simples e autorização explícita.

## Alternativas consideradas
1. Banco ou schema por tenant: isolamento físico maior, com mais operação.
2. Shared schema com PostgreSQL RLS: defesa adicional, mas exige configurar e
   validar contexto da conexão, papéis e comportamento do pool.
3. Shared schema com tenant_id obrigatório nos repositórios e RBAC na aplicação.

## Decisão
Usar `core.tenants`, `core.users`, `core.sessions` e `core.monitors` no mesmo cluster.
O login identifica o tenant pelo slug e o usuário pelo email normalizado; emails
podem existir em organizações diferentes, com identidades e credenciais independentes.

O contexto autenticado vem exclusivamente da sessão, nunca de um tenant_id enviado
no corpo. Repositórios de monitores e membros recebem tenant_id explicitamente e
incluem esse filtro em leitura, listagem, alteração e remoção. Um identificador de
outra organização retorna 404. UUID não substitui autorização.

Aplicar quatro papéis: owner, admin, operator e viewer. Owner administra todos os
papéis exceto transferência de propriedade; admin administra operator/viewer;
operator altera monitores; viewer apenas consulta monitores. Leitura da identidade
usa lock compartilhado e alteração de membro usa lock de linha no PostgreSQL para
serializar mudanças concorrentes de autorização. Alterar acesso revoga sessões.

Usar unicidade `(tenant_id, email)` e chave estrangeira composta entre sessões e
`(tenant_id, user_id)`, impedindo associar sessão e usuário de tenants diferentes.

## Consequências positivas
Uma cadeia de migrations, repositórios testáveis e políticas explícitas em domínio.
As mesmas regras valem para UI, Swagger e chamadas HTTP diretas.

## Consequências negativas
Sem RLS, um novo acesso SQL mal filtrado ainda pode vazar dados. Revisão, contratos
de repositório e testes negativos são obrigatórios. A mesma pessoa usa identidades
separadas em organizações distintas. Não há transferência de propriedade no M1.

## Validação
Os cenários HTTP tentam listar, ler, alterar e excluir um monitor de outro tenant,
e alterar um membro externo. A matriz RBAC testa os quatro papéis e impede promover
administradores ou alterar o owner indevidamente. Os cenários também rodam no
PostgreSQL migrado, além dos testes rápidos SQLite.

## Quando reconsiderar
Adicionar RLS como defesa adicional se a superfície de consultas crescer ou os
requisitos de isolamento aumentarem. Avaliar memberships globais quando uma pessoa
precisar alternar organizações com uma única identidade. Reavaliar separação física
após as medições do M6.
