#!/bin/bash
# Abre o Finance Control direto do código-fonte (sem gerar o .app).
cd "$(dirname "$0")" || exit 1
for candidate in /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /usr/local/bin/python3 \
  /opt/homebrew/bin/python3 "$(command -v python3)"; do
  [ -x "$candidate" ] || continue
  if "$candidate" -c 'import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)' 2>/dev/null; then
    exec "$candidate" -m backend.main
  fi
done
open "https://www.python.org/downloads/macos/"
echo "Instale o Python 3.12 de python.org e abra este arquivo de novo."; read -r _
