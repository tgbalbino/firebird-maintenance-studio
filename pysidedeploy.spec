[app]
title = Firebird Maintenance Studio
project_dir = .
input_file = run_app.py
exec_directory = dist
icon = C:\Users\Dev\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages\PySide6\scripts\deploy_lib\pyside_icon.ico

[python]
packages = Nuitka==4.1.1

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Widgets
plugins = styles

[nuitka]
mode = standalone
extra_args = --quiet --noinclude-qt-translations --include-package=firebird_studio --include-package=firebird --include-package=fdb --include-package=keyring

