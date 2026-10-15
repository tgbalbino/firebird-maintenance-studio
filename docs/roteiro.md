# Escopo, etapas e critérios de aceite

## Etapa 0 — laboratório de compatibilidade

Preparar bancos descartáveis 2.5, 3, 4 e 5, cada um com tabelas, domínios, views, procedures, triggers, índices e dados de amostra. Testar em Windows 64 bits com servidor local e remoto. Registrar versão do servidor, ODS, DLL cliente, utilitários e resultados. Concluir esta etapa antes de prometer suporte de produção.

## Etapa 1 — conexão e scripts

- CRUD de vários perfis, agrupamento, busca, teste de conexão e favoritos.
- Senha em Windows Credential Manager; configuração exportável sem segredo.
- Explorador de objetos e editor SQL com múltiplas abas.
- Execução de instrução selecionada e de arquivo `.sql`, com `SET TERM`, codificação configurável, saída completa, duração e erro com posição quando disponível.
- Transação explícita para execução interativa; scripts mostram a política de commit do `isql` antes de executar.

**Aceite:** abrir dois bancos de versões diferentes, executar consulta e script com procedure e trigger, ver resultados e erros, e reconectar após reiniciar o aplicativo.

## Etapa 2 — backup e restore

- Backup lógico sob demanda, nome de arquivo com data, progresso, log e verificação de arquivo gerado.
- Restore para novo destino por padrão, com checagem prévia de existência do arquivo, compatibilidade e espaço.
- Teste de abertura do banco restaurado; relatório com versão/ODS. Opção de substituição somente com fluxo separado e confirmação explícita.
- Histórico de operações; agendamento fica para etapa posterior.

**Aceite:** backup e restore completos em cada versão; falhas interrompem a operação e deixam relatório claro; um banco de origem permanece acessível e inalterado.

## Etapa 3 — comparação de estrutura

- Extrair e normalizar catálogo nas quatro versões.
- Comparar origem/destino por objeto, exportar relatório e script de migração revisável.
- Aplicar apenas mudanças classificadas como seguras após prévia, backup recente confirmado e confirmação do banco alvo. Mudanças destrutivas ficam para execução manual.

**Aceite:** detectar adição/remoção/alteração em amostras conhecidas; gerar DDL que reproduza diferenças seguras em banco descartável; sinalizar o que não é gerado com segurança.

## Etapa 4 — saúde e recomendações

- Painel de disponibilidade, transações, conexões e tarefas recentes.
- Alertas baseados em tendência e contexto; justificativa e ação sugerida em cada alerta.
- Validação de integridade via utilitário oficial em janela de manutenção, sem reparo automático.

**Aceite:** relatório correto nos quatro bancos de teste, sem bloquear a interface; nenhuma sugestão modifica um banco sem ação explícita.

## Funcionalidades a avaliar após a primeira versão

1. Agendamento e retenção de backups, com teste periódico de restore.
2. Comparação opcional de dados por chave primária, com plano de conflitos.
3. Plano de consultas, estatísticas e diagnóstico de índices.
4. Exportação/importação CSV e JSON com prévia de tipos e charset.
5. Auditoria de acessos e operações; perfis de permissões.
6. Alertas por e-mail ou outro canal, mediante configuração do usuário.
7. Modo somente leitura e execução de tarefas em lote para vários bancos.
8. Biblioteca versionada de scripts com histórico e checksum.

## Matriz mínima de testes

| Eixo | Casos |
|---|---|
| Versão | 2.5, 3, 4, 5 |
| Acesso | Local e remoto; usuário administrador e usuário limitado |
| Dados | UTF-8, WIN1252, nomes com acentos, BLOB e campos numéricos |
| Script | DDL, DML, PSQL com `SET TERM`, erro intermediário, rollback |
| Backup | Sucesso, falha de permissão, pouco espaço, interrupção |
| Restore | Banco novo, arquivo inválido, versão de destino diferente, destino existente |
| Comparação | Objetos simples, dependências, privilégios, tipos exclusivos de versões novas |
| Saúde | Banco ocioso, carga, transação longa, permissões insuficientes |

## Definição de lançamento

O aplicativo só deve ser chamado de compatível com uma versão depois de passar por todos os testes críticos dessa versão. Publicar código e documentação antes disso é possível, mas releases executáveis devem identificar claramente versões e recursos validados.
