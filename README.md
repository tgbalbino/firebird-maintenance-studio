# Firebird Maintenance Studio

Projeto de uma aplicação desktop Windows, de código aberto, para administração e manutenção de bancos Firebird 2.5, 3, 4 e 5. A referência de experiência é o IBExpert, com foco inicial nas tarefas de manutenção mais frequentes.

**Estado atual:** base executável em validação técnica. A interface oferece perfis de conexão, senha opcional no cofre do Windows, árvore de objetos, conexão por duplo clique, execução SQL, múltiplas abas, grid paginado, copiar seleção, exportação CSV/JSON, execução de arquivos SQL pelo `isql`, backup/restore pelo `gbak`, leitura de estrutura sob demanda, plano em árvore com sugestões, painel de saúde baseado em MON$ e comparação visual entre perfis. A comparação mostra diferenças e prévia de migração sem aplicar alterações. A compatibilidade precisa ser comprovada com bancos de teste de cada versão.

Para preparar um ambiente de desenvolvimento:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m firebird_studio --check
python -m unittest discover -v
```

## Objetivo da primeira versão

- Cadastrar várias conexões locais e remotas, com teste de conexão e senha guardada no cofre de credenciais do Windows.
- Executar consultas e scripts SQL, incluindo `SET TERM`, com resultado, mensagens, duração e opção explícita de confirmar ou desfazer transações.
- Comparar a **estrutura** de dois bancos, mostrar diferenças e gerar um script de atualização para revisão. Não inclui sincronização automática de registros.
- Fazer backup lógico e restore com progresso e registro de execução. Restore começa em um **novo banco de destino**; substituir um banco existente é uma operação separada.
- Mostrar indicadores de saúde e recomendações explicadas. Correções são ações manuais, com prévia e registro.

## Decisão técnica

| Parte | Escolha inicial | Motivo |
|---|---|---|
| Linguagem | Python 3.12 | Código aberto e bibliotecas disponíveis sem IDE paga; versão alvo estável para validar todas as dependências. |
| Interface Windows | PySide6 / Qt Widgets | Interface desktop rica: árvore de bancos, editor, painéis e tabelas. Exige cumprimento da licença LGPLv3 ao distribuir binários. |
| Firebird 2.5 | FDB + cliente Firebird compatível | Driver legado oficial para a API clássica. |
| Firebird 3, 4 e 5 | `firebird-driver` e `firebird-lib` | Driver oficial atual e biblioteca de metadados/monitoramento. |
| Isolamento de clientes | Processos auxiliares por família de versão | Evita conflito entre versões de `fbclient.dll` no Windows. |
| Scripts | `isql` correspondente ao servidor | Preserva comandos próprios do `isql`, incluindo `SET TERM`, sem criar um analisador SQL parcial. |
| Backup/restore | Serviços Firebird ou `gbak` correspondente ao servidor | Usa as ferramentas do próprio Firebird e registra saída e erros. |
| Segredos | Windows Credential Manager | Senhas fora dos arquivos de configuração e do repositório. |
| Distribuição | Empacotamento Windows após testes | O executável e as DLLs exigem revisão de licença e compatibilidade antes de publicação. |

O produto será independente de IDE comercial. **IBExpert é apenas referência funcional; o projeto não reutilizará sua marca, interface ou código.**

## Documentos

- [Validação técnica e arquitetura](docs/validacao-tecnica.md)
- [Escopo, etapas e critérios de aceite](docs/roteiro.md)
- [Segurança e regras para operações sensíveis](docs/seguranca.md)
- [Revisão comparativa e plano de melhorias](docs/melhorias.md)

## Executável Windows para testes

O build portátil x64 fica em `outputs/FirebirdMaintenanceStudio/FirebirdMaintenanceStudio.exe` no ambiente de desenvolvimento. Para usar o aplicativo, mantenha a pasta `_internal` ao lado do executável. Configure no perfil os caminhos do `isql.exe` e `gbak.exe` correspondentes à versão do Firebird do banco.

O pacote publicado nesta fase é **Windows x64**. Um build x86 exige um ambiente Python, PySide6 e clientes Firebird de 32 bits; ele não é gerado misturando componentes x64 e x86.

## Próxima validação prática

Montar quatro bancos descartáveis (2.5, 3, 4 e 5) e executar a matriz de testes do roteiro. Não publicar senhas, arquivos `.fdb`, backups ou dados reais.

## Referências oficiais

- [Drivers Python do Firebird](https://firebirdsql.org/en/python-driver/)
- [Documentação do firebird-driver](https://firebird-driver.readthedocs.io/en/stable/)
- [Documentação do firebird-lib](https://firebird-lib.readthedocs.io/en/stable/)
- [Manual do isql](https://firebirdsql.org/file/documentation/html/en/firebirddocs/isql/firebird-isql.html)
- [Manual do gbak](https://firebirdsql.org/file/documentation/html/en/firebirddocs/gbak/firebird-gbak.html)
- [Manual do gfix](https://firebirdsql.org/file/documentation/html/en/firebirddocs/gfix/firebird-gfix.html)
- [Qt for Python](https://doc.qt.io/qtforpython-6/)

## Licença

Código deste repositório: MIT. Dependências e binários de terceiros mantêm suas próprias licenças. Conferir avisos e obrigações de distribuição antes de publicar instaladores.
