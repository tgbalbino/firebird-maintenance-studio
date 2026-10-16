# Revisão e plano de melhorias

Data da revisão: 16/10/2026.

## Validação visual adicional

Data da validação: 16/10/2026.

Foram comparados os fluxos atuais com as documentações oficiais do IBExpert e do DBeaver e com a abordagem leve do FlameRobin. A conclusão é manter o foco Firebird e tornar a tela principal mais parecida com uma estação de trabalho: navegador lateral persistente, cabeçalho da conexão ativa, editor central e resultados em abas.

| Referência | Padrão confirmado | Aplicação no Studio |
|---|---|---|
| IBExpert Database Explorer | Duplo clique conecta o banco; bancos conectados exibem uma árvore lógica de objetos; o painel auxiliar mostra detalhes do objeto. | Manter a árvore multi-banco, ícones de conexão, grupos expansíveis, filtro e menu contextual. |
| IBExpert SQL Editor | Histórico, plano em árvore, análise de desempenho e resultados no próprio editor. | Manter abas SQL/Resultado/Plano e dar destaque permanente a duração, conexão e quantidade de linhas. |
| DBeaver SQL Editor | Editor, toolbar, painel de resultados e várias consultas por conexão; layout pode alternar entre editor e resultado. | Priorizar três ações visíveis: executar, resultado e plano; agrupar ações administrativas em menus. |
| DBeaver Database Navigator | Cor da conexão, estado expandido persistido, filtro salvo, abrir SQL por conexão e ações distintas para duplo clique. | Persistir estado da árvore e manter o duplo clique como ação de conexão/abertura. |
| FlameRobin | Interface leve, árvore direta, operações assíncronas e poucos controles no caminho principal. | Evitar uma fileira extensa de botões e mostrar progresso/status sem bloquear a janela. |

### Melhorias visuais priorizadas após a validação

1. **Cabeçalho da estação de trabalho:** nome do aplicativo, banco ativo, versão, host, porta e estado da conexão.
2. **Navegador lateral:** título curto, busca sempre visível, largura persistida, ícone de conectado/desconectado e menu contextual.
3. **Área SQL:** abas de consulta, resultado e diagnóstico; toolbar curta com executar, resultado e menu de ações.
4. **Feedback de operação:** barra de progresso, duração, quantidade de linhas e mensagens copiáveis.
5. **Grade:** paginação configurável, filtro geral, filtro por coluna, cabeçalho fixo e menu de contexto.
6. **Acessibilidade:** contraste nos dois temas, foco visível, atalhos exibidos e significado sem depender somente da cor.

### Critérios de aceite visual

- Em 1280×720, os nomes dos menus, abas e banco ativo permanecem legíveis sem sobreposição.
- Em 150% de escala do Windows, a árvore continua utilizável e o editor conserva espaço para SQL.
- Ao conectar dois bancos, cada item da árvore mantém seu estado e a consulta mostra claramente a conexão escolhida.
- Ao executar uma consulta, o usuário consegue identificar a duração, o número de linhas e a aba de resultado sem abrir outro diálogo.
- A troca de tema mantém contraste suficiente no cabeçalho, editor, grade, árvore, menus e mensagens.

### Referências consultadas

- [IBExpert SQL Editor](https://ibexpert.com/docu/doku.php?id=02-ibexpert%3A02-08-ibexpert-tools-menu%3Asql-editor)
- [IBExpert Database Explorer](https://ibexpert.com/docu/doku.php?id=02-ibexpert%3A02-01-getting-started%3Aibexpert-screen%3Adatabase-explorer)
- [DBeaver SQL Editor](https://dbeaver.com/docs/dbeaver/SQL-Editor/)
- [DBeaver Database Navigator](https://dbeaver.com/docs/dbeaver/Database-Navigator/)
- [DBeaver Toolbar Customization](https://dbeaver.com/docs/dbeaver/Toolbar-Customization/)
- [FlameRobin](https://flamerobin.sourceforge.net/flamerobin_paper.pdf)

## Revisão visual validada com referências atuais

Foram revisadas as documentações atuais do IBExpert, DBeaver Community e o material público do FlameRobin. Os padrões abaixo foram considerados somente quando combinam com o foco Firebird e com o MDI já existente no projeto.

| Padrão observado | Referência | Situação no Studio | Decisão |
|---|---|---|---|
| Navegador em árvore com bancos, servidores e objetos | FlameRobin; IBExpert | Já existe árvore com vários perfis e grupos de objetos | Manter e melhorar contexto, filtro e largura persistida |
| Editor ligado a uma conexão, com resultados em abas próximas | DBeaver | Cada consulta já tem perfil e abas SQL/Resultado | Manter; adicionar nome do banco no título e no cabeçalho |
| Toolbar com ações personalizáveis e resultados separados | DBeaver | Toolbar existe, mas ainda pode ficar extensa em telas menores | Agrupar ações secundárias em menus e manter executar/resultado visíveis |
| Plano em árvore, histórico e análise de desempenho | IBExpert; DBeaver | Plano em árvore e histórico básico já existem | Priorizar duração, linhas, banco e mensagem por execução |
| Menu de contexto por conexão e objeto | FlameRobin; DBeaver | Parte das ações existe na árvore | Completar com abrir SQL, ler dados, copiar nome e desconectar |
| Grade com navegação por páginas e filtros | DBeaver | Grid paginado e filtro global já existem | Evoluir para filtro por coluna e escolha de tamanho da página |

### Melhorias visuais aprovadas para a próxima implementação

1. **Cabeçalho da conexão ativa:** nome do perfil, Firebird, host, caminho/alias e estado conectado/desconectado.
2. **Toolbar compacta:** manter Executar, Resultado e Plano visíveis; mover exportação, manutenção e administração para menus agrupados.
3. **Árvore mais legível:** largura persistida, filtro no topo, ícones de estado e menu de contexto consistente.
4. **Editor e resultado:** preservar as abas atuais e adicionar uma faixa de status com duração, quantidade de linhas e conexão usada.
5. **Grid:** menu por coluna, copiar valor/célula/linha, filtro por coluna e limite de linhas configurável.
6. **Estados visuais:** usar a mesma linguagem de cores para conectado, execução, sucesso, aviso e erro em árvore, status e diálogos.
7. **Acessibilidade:** foco visível, contraste nos dois temas, atalhos exibidos nos menus e textos sem depender apenas de cor.

### Ordem de validação visual

1. Validar o cabeçalho e a toolbar em 1280×720 e 1920×1080.
2. Abrir dois bancos e três consultas, verificando que o título e o estado de cada janela permanecem claros.
3. Executar consulta, plano, backup e restore simulados, conferindo o mesmo padrão de status e erro.
4. Reabrir o aplicativo e confirmar que larguras, tema e posição dos painéis continuam persistidos.
5. Repetir a revisão nos temas claro e escuro com escala do Windows em 100%, 125% e 150%.

As referências usadas nesta revisão são a [documentação do SQL Editor do DBeaver](https://dbeaver.com/docs/dbeaver/SQL-Editor/), a [documentação do SQL Editor do IBExpert](https://ibexpert.com/docu/doku.php?id=02-ibexpert%3A02-08-ibexpert-tools-menu%3Asql-editor) e o material público do [FlameRobin](https://flamerobin.sourceforge.net/flamerobin_paper.pdf).

## O que o projeto já oferece

- Perfis locais e remotos para Firebird 2.5, 3, 4 e 5.
- Senha opcional no Gerenciador de Credenciais do Windows.
- Abertura assíncrona e árvore inicial de tabelas, views, procedures, functions e triggers.
- Explorador em árvore no estilo IBExpert: vários bancos ficam abertos no mesmo painel, cada um com seus grupos de objetos.
- DDL e modelos de DML para tabelas.
- Editor SQL com várias abas, execução de consulta, scripts e análise de plano.
- Cada janela SQL pode apontar para um banco diferente; o resultado e o plano ficam em abas separadas, com sugestões preservadas.
- Controle explícito de transação: alterações ficam desfeitas por padrão; a confirmação exige marcar a opção e confirmar o diálogo.
- Backup/restore com `gbak`, leitura de saúde e comparação inicial de estruturas.
- Executável portátil Windows x64 em uma pasta fixa para testes.

## Comparação com ferramentas existentes

| Referência | Recursos que se destacam | O que vale trazer para este projeto |
|---|---|---|
| IBExpert | Editores visuais de objetos, SQL/script, debugger de PSQL, query builder, designer, documentação, exportação, usuários/grants e Trace/Audit. [Fonte](https://ibexpert.net/cms/ibexpert-developer-studio) | Catálogo completo, editor visual seguro, exportação, grants e monitoramento. Debugger e designer ficam para uma fase posterior. |
| FlameRobin | Leve, multiplataforma e open source; versões recentes destacam DataGrid, serviços assíncronos de backup/restore e suporte a tipos modernos. [Site](https://flamerobin.sourceforge.io/index.php) [Recursos recentes](https://sourceforge.net/projects/flamerobin/files/v26.5.2/) | Manter inicialização rápida, operações não bloqueantes, grid robusto e baixo acoplamento. |
| DBeaver | Suporte a vários bancos por drivers, editor de dados e recursos de administração em uma interface ampla. [Documentação](https://dbeaver.com/docs/dbeaver/Database-drivers/) | Aplicar padrões de grade, filtros, abas e exportação sem tentar virar uma ferramenta genérica para todos os bancos. |
| Ferramentas nativas Firebird | `isql`, `gbak`, `gfix`, Services API, tabelas `MON$` e Trace API. Trace registra conexão, preparação e execução de comandos. [Recursos Firebird](https://firebirdsql.org/en/features) [Trace](https://firebirdsql.org/docs/chunk/en/refdocs/fbconf/fbconf-trace.html) | Usar as ferramentas oficiais, mostrar saída completa, progresso, permissões necessárias e diferenças entre Firebird 2.5 e 3+. |

## Prioridade 0: confiabilidade e experiência

1. Criar uma barra de operações com estado, duração, cancelamento quando possível e log por execução.
2. Tornar backup, restore, scripts, estrutura, saúde e comparação assíncronos, sem congelar a janela.
3. Padronizar mensagens de erro em diálogo com detalhes copiáveis, status resumido e ação sugerida.
4. Validar antes de executar: caminho do utilitário, banco acessível, senha, espaço livre, destino existente e versão do cliente.
5. Adicionar modo somente leitura e confirmação explícita para DDL, DML, restore e ações de manutenção.
6. Criar testes automatizados da matriz Firebird 2.5/3/4/5, local/remoto, usuário limitado e charset.

## Prioridade 1: explorador e dados

1. Expandir o catálogo para domínios, índices, chaves, constraints, sequences/generators, exceptions, packages, grants e usuários quando a versão permitir.
2. Ao abrir uma tabela, mostrar abas **Dados**, **Estrutura**, **Índices**, **Constraints**, **DDL** e **DML**.
3. Implementar grid de dados com paginação, filtro, ordenação, busca, copiar/colar, exportação CSV/JSON e visualização segura de BLOB.
4. Permitir edição somente após ativar explicitamente o modo edição; gerar `INSERT`, `UPDATE` e `DELETE` parametrizados e mostrar a transação antes do commit.
5. Mostrar dependências de cada objeto e navegação de referências.

## Prioridade 2: editor SQL

1. Editor grande com destaque de sintaxe, indentação, números de linha, busca, substituir, comentários e atalhos.
2. Autocomplete baseado no catálogo do banco, nomes de campos após selecionar a tabela e ajuda contextual de funções.
3. Separar abas de consulta, resultados, mensagens e plano; manter histórico de consultas com duração e quantidade de linhas.
4. Evoluir o controle atual de confirmação para transações mantidas entre comandos, com **Iniciar transação**, **Commit**, **Rollback** e **Cancelar**.
5. Plano em árvore com custo/tempo quando disponível, SQL original, versão do Firebird e sugestões explicadas.

## Prioridade 3: comparação e migração

1. Comparar todos os objetos suportados, não somente uma fotografia simplificada de tabelas e PSQL.
2. Exibir origem e destino lado a lado, com filtros por tipo, diferença e severidade.
3. Ordenar o script pela dependência: domains, tables, sequences, constraints, indexes, views, procedures, functions, triggers e grants.
4. Marcar alterações destrutivas, pedir confirmação por objeto e permitir exportar uma migração revisável.
5. Oferecer comparação opcional de dados por chave primária, sempre com prévia e plano de conflitos.

## Prioridade 4: administração e diagnóstico

1. Dashboard com versão, ODS, tamanho, páginas, conexões, transações longas, OIT/OAT/OST, crescimento e última verificação.
2. Tela de sessões usando `MON$ATTACHMENTS`, `MON$TRANSACTIONS` e `MON$STATEMENTS`, com filtro e ação administrativa protegida.
3. Assistente de validação com `gfix`, mostrando comando, risco e confirmação; nunca executar reparo automaticamente.
4. Trace de usuário para a própria conexão e trace administrativo somente quando a permissão existir; diferenciar Firebird 2.5 da sintaxe 3+.
5. Histórico de backup/restore, verificação do arquivo gerado e teste opcional de restore em banco temporário.
6. Exportar relatório de diagnóstico em HTML/PDF e pacote de suporte sem senha nem dados sensíveis.

## Melhorias visuais

- Layout em três áreas: árvore de bancos/objetos, conteúdo da seleção e abas SQL/resultados.
- Toolbar com ações agrupadas: conexão, consulta, manutenção e exportação; evitar uma fileira extensa de botões.
- Ícones e cores de estado: conectado, desconectado, execução, sucesso, aviso e erro.
- Barra de progresso e painel de mensagens persistente para tarefas demoradas.
- Cabeçalho do banco ativo com nome, versão, host e indicador de leitura/gravação.
- Grid com cabeçalho fixo, largura ajustável, filtros por coluna e menu de contexto.
- Tema claro/escuro, escala de fonte e atalhos configuráveis.
- Larguras e abas persistidas por usuário; nomes longos sem corte e busca rápida na árvore.
- Confirmações específicas para operações destrutivas, sem esconder o motivo técnico.

## Ordem recomendada de execução

1. **Confiabilidade:** corrigir todos os fluxos assíncronos, logs, erros e testes de versão.
2. **Dados:** grid paginado, estrutura completa e edição transacional controlada.
3. **SQL:** editor profissional, histórico, transações e plano mais rico.
4. **Migração:** comparação completa com dependências e prévia revisável.
5. **Administração:** MON$, gfix, Trace, usuários/grants e relatórios.
6. **Acabamento:** tema, atalhos, instalação, atualização e documentação.

## Decisões de escopo

- O foco continua sendo Firebird; não vale transformar o produto em um DBeaver genérico.
- A interface deve continuar independente de IDE paga e baseada em Python/PySide6.
- Recursos que podem alterar dados devem sempre ter prévia, transação e confirmação.
- O suporte a Firebird 2.5 deve ter caminhos próprios quando o catálogo ou a autenticação diferirem das versões atuais.
- A distribuição x64 é a principal. x86 só deve ser criado se houver um cliente real que não possa migrar.
