#!/bin/bash
# Gera o aplicativo "Finance Control.app" (e um .dmg) no seu Mac.
# Como usar: dê um duplo clique neste arquivo. Não é preciso digitar nada.
# (Na primeira vez: clique com o botão direito > Abrir > Abrir.)

cd "$(dirname "$0")" || exit 1
APP_NAME="Finance Control"
DATA_DIR="$HOME/Library/Application Support/$APP_NAME"

say_step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
fail() {
  printf "\n\033[31mNão foi possível terminar:\033[0m %s\n" "$1"
  printf "\nNenhum dado seu foi alterado.\nPressione Enter para fechar."; read -r _; exit 1
}

say_step "1/6 Procurando um Python com Tk 8.6 ou mais novo"
PYTHON=""
for candidate in \
  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  /usr/local/bin/python3 /opt/homebrew/bin/python3 "$(command -v python3)"; do
  [ -x "$candidate" ] || continue
  if "$candidate" -c 'import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= 8.6 and sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PYTHON="$candidate"; break
  fi
done
if [ -z "$PYTHON" ]; then
  open "https://www.python.org/downloads/macos/"
  fail "Instale o Python 3.12 (instalador 'macOS 64-bit universal2' em python.org, que acabou de abrir) e rode este arquivo de novo."
fi
echo "Usando: $PYTHON ($("$PYTHON" --version))"

say_step "2/6 Rodando os testes automáticos"
"$PYTHON" -m unittest discover -s tests -t . 2>&1 | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || fail "Algum teste falhou. Envie esta janela para quem está te ajudando."

say_step "3/6 Preparando o ambiente de construção (precisa de internet)"
rm -rf .build_venv
"$PYTHON" -m venv .build_venv || fail "Não consegui criar o ambiente virtual."
.build_venv/bin/pip install --quiet --upgrade pip
.build_venv/bin/pip install --quiet -r requirements-build.txt || fail "Não consegui baixar o PyInstaller (verifique a internet)."

say_step "4/6 Construindo o aplicativo"
.build_venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/FinanceControl.spec \
  > build.log 2>&1 || { tail -20 build.log; fail "A construção falhou (log completo em build.log)."; }
[ -d "dist/$APP_NAME.app" ] || fail "O aplicativo não foi gerado (veja build.log)."
codesign --force --deep --sign - "dist/$APP_NAME.app" >/dev/null 2>&1 || true

say_step "5/6 Trazendo seus dados da versão anterior (sem sobrescrever nada)"
mkdir -p "$DATA_DIR"
if [ -f "data/finance_control.db" ] && [ ! -f "$DATA_DIR/finance_control.db" ]; then
  cp -n "data/finance_control.db" "$DATA_DIR/finance_control.db" && echo "Dados copiados. O app faz um backup antes de atualizar o banco."
else
  echo "Nada a copiar (já existem dados no destino ou não há banco antigo)."
fi

say_step "6/6 Instalando e criando o instalador .dmg"
TARGET="/Applications"
[ -w "$TARGET" ] || { TARGET="$HOME/Applications"; mkdir -p "$TARGET"; }
rm -rf "$TARGET/$APP_NAME.app"
ditto "dist/$APP_NAME.app" "$TARGET/$APP_NAME.app" || fail "Não consegui copiar para $TARGET."
osascript -e "tell application \"Finder\" to make alias file to POSIX file \"$TARGET/$APP_NAME.app\" at (path to desktop folder)" >/dev/null 2>&1 \
  || echo "Não consegui criar o atalho na Mesa; arraste o app de $TARGET para a Mesa se quiser."
STAGE="$(mktemp -d)"
cp -R "dist/$APP_NAME.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "dist/FinanceControl.dmg" \
  && echo "Instalador: $(pwd)/dist/FinanceControl.dmg"
rm -rf "$STAGE" .build_venv

printf "\n\033[32mPronto!\033[0m O app está em: %s/%s.app\n" "$TARGET" "$APP_NAME"
open "$TARGET/$APP_NAME.app"
printf "Pressione Enter para fechar esta janela."; read -r _
