# Segurança e operações sensíveis

- Armazenar senhas no cofre de credenciais do Windows. Nunca em JSON, logs, arquivos de script, argumentos visíveis de processo ou repositório.
- Não incluir arquivos `.fdb`, `.fbk`, dumps, logs com dados pessoais, senhas ou certificados em commits.
- Exibir sempre servidor, caminho/alias e versão do **destino** antes de SQL de alteração, restore ou migração.
- Backup concluído não equivale a backup recuperável: testar restore periodicamente.
- Restore cria novo banco por padrão. Substituição exige backup recente e confirmação específica.
- Comparação de esquema gera prévia e destaca `DROP`, perda de dados, mudança de tipo, dependências e objetos não suportados.
- Monitoramento é somente leitura. `gfix` de reparo, sweep, encerramento de conexão e cancelamento de consulta são comandos separados, com explicação dos efeitos.
- Logs usam redação de segredos e caminhos sensíveis quando exportados; histórico local registra quem iniciou, quando, banco, operação e resultado.
- Tarefas demoradas rodam fora da thread da interface, com cancelamento e estado visível. Interromper um processo não garante rollback de todas as etapas; o relatório deve informar o último ponto confirmado.
- Instalação/distribuição de PySide6 e bibliotecas Firebird exige revisão das licenças dos componentes efetivamente incluídos.
