"""Ponto de entrada do Finance Control."""

import logging
import sys
import tkinter as tk
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

from backend import config
from backend.utils import i18n
import database


# setup_logging: configura o registro de eventos (logs) do app.
# Grava em <pasta de dados>/logs/app.log, com rotação: quando o arquivo passa de 500 KB,
# ele é arquivado e são mantidos só 2 backups, para não crescer sem limite.
# Se não conseguir criar a pasta ou o arquivo, cai para um log simples (só avisos).
def setup_logging():
    log_dir = database.DATA_DIR / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_dir / "app.log", maxBytes=500_000,
                                      backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    except OSError:
        logging.basicConfig(level=logging.WARNING)


# adopt_legacy_db: migra o banco da versão antiga do app.
# Se existe um banco na pasta antiga do projeto (data/finance_control.db) e ainda
# não existe um na pasta de dados do usuário, faz uma cópia segura (modo somente
# leitura na origem, sem mover nem sobrescrever nada).
# Retorna True se copiou, False se não havia nada a fazer.
def adopt_legacy_db():
    """Primeira execução fora da pasta ``data`` do projeto: copia (nunca move,
    nunca sobrescreve) o banco da versão anterior para a pasta de dados do
    usuário. O init_db então faz o backup e a migração."""
    legacy = database.BASE_DIR / "data" / "finance_control.db"
    if database.DB_PATH.exists() or not legacy.exists():
        return False
    if legacy.resolve() == database.DB_PATH.resolve():
        return False
    import sqlite3
    database.DATA_DIR.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(database.DB_PATH)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return True


# main: função principal que inicia o app, em ordem:
# 1. configura o log;
# 2. tenta copiar o banco antigo (se falhar, só registra aviso e continua);
# 3. inicializa o banco (cria tabelas, backup, migração). Se falhar, mostra uma
#    janela de erro dizendo que os dados não foram apagados e retorna 1;
# 4. se deu tudo certo, abre a interface gráfica (App) e retorna 0.
# O retorno (0 = sucesso, 1 = erro) vira o código de saída do programa.
def main():
    setup_logging()
    try:
        if adopt_legacy_db():
            logging.getLogger("finance_control").info("Banco anterior copiado para a pasta do usuário")
    except Exception as exc:
        logging.getLogger("finance_control").warning("Não foi possível copiar o banco anterior: %s", type(exc).__name__)
    try:
        i18n.configure(database.DATA_DIR, database.BASE_DIR)
    except i18n.LocaleConfigError:
        pass
    try:
        database.init_db()
    except Exception as exc:
        logging.getLogger("finance_control").error("Falha ao abrir o banco: %s", type(exc).__name__, exc_info=True)
        root = tk.Tk()
        root.withdraw()
        message = str(exc) if isinstance(exc, database.DatabaseError) else (
            "Não foi possível abrir o banco de dados.")
        messagebox.showerror(
            config.APP_TITLE,
            f"{message}\n\nSeus dados não foram apagados. Pasta dos dados:\n{database.DATA_DIR}")
        root.destroy()
        return 1

    from frontend.app import App
    App().run()
    return 0


# Só executa main() quando o arquivo é rodado diretamente (não quando importado).
if __name__ == "__main__":
    sys.exit(main())