# Distribuição Windows

## x64

O build atual é Windows x64, feito com Python 3.12 x64, PySide6 e PyInstaller. O executável é distribuído como pasta porque o Qt precisa carregar DLLs e plugins ao lado do programa:

`dist/FirebirdMaintenanceStudio/FirebirdMaintenanceStudio.exe`

O pacote não inclui um servidor Firebird nem os utilitários `isql.exe` e `gbak.exe`. Configure no perfil os caminhos correspondentes à versão do servidor. O cliente `fbclient.dll` também deve estar disponível para o driver usado.

Existe também uma versão de arquivo único, `FirebirdMaintenanceStudioOnefile.exe`. Ela extrai as DLLs para uma pasta temporária ao iniciar e é a opção recomendada quando o usuário não quer distribuir uma pasta com dependências. Mesmo assim, o arquivo deve ser extraído do ZIP antes de executar.

Para corrigir incompatibilidades de DLL do Qt em algumas máquinas, foi gerado o pacote final `FirebirdMaintenanceStudio-x64-final.zip`. Ele usa um hook de inicialização que força o Windows a priorizar as DLLs internas do Qt. O executável dentro dele é `FirebirdMaintenanceStudioFinal.exe`.

O pacote portátil `FirebirdMaintenanceStudio-x64-portable.zip` distribui a pasta inteira do aplicativo e é a opção preferida quando o modo arquivo único apresentar falha. Execute `FirebirdMaintenanceStudio/FirebirdMaintenanceStudio.exe` depois de extrair.

O primeiro início deve ser feito em uma máquina de teste, com um banco descartável. O build foi validado iniciando a janela por mais de três segundos; não foi possível validar conexão ou backup porque nenhum banco de teste foi fornecido.

## Instalador

O arquivo `installer/FirebirdMaintenanceStudio.iss` está pronto para ser compilado pelo Inno Setup em uma máquina Windows que tenha o Inno Setup instalado. Ele gera um instalador x64 com atalho no menu Iniciar e, opcionalmente, na área de trabalho. O ambiente atual não possui o compilador do Inno Setup, portanto o instalador não foi gerado aqui.

Para reconstruir:

```powershell
python -m pip install -e .
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name FirebirdMaintenanceStudio --paths . --collect-submodules firebird --collect-submodules fdb --collect-submodules keyring run_app.py
pyinstaller --noconfirm --clean --onefile --windowed --name FirebirdMaintenanceStudioOnefile --paths . --collect-submodules firebird --collect-submodules fdb --collect-submodules keyring run_app.py
pyinstaller --noconfirm --clean --onefile --windowed --name FirebirdMaintenanceStudioFull --paths . --collect-all PySide6 --collect-all shiboken6 --collect-submodules firebird --collect-submodules fdb --collect-submodules keyring run_app.py
pyinstaller --noconfirm --clean --onefile --windowed --name FirebirdMaintenanceStudioFinal --paths . --runtime-hook qt_runtime_hook.py --collect-submodules firebird --collect-submodules fdb --collect-submodules keyring run_app.py
```

## x86 (32 bits)

Não será gerado x86 nesta etapa. As rodas atuais do PySide6 usadas pelo projeto são Windows x64 (`win_amd64`), e o Python x86 exigiria uma cadeia de dependências separada. Manter uma versão 32 bits exigiria trocar a interface ou fixar versões antigas de Python/Qt, aumentando o risco e o custo de manutenção. Se houver um cliente legado que exija 32 bits, a alternativa é um worker separado compatível com ele, mantendo a interface principal x64.
