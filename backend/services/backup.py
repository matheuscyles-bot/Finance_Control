"""Backups automáticos e manuais (a lógica de arquivo fica em database/)."""

from datetime import datetime

import database
from database import DatabaseError


def auto_backup_if_needed():
    """Cria no máximo um backup automático por dia. Devolve o caminho
    criado ou None se já existia um de hoje."""
    today = datetime.now().strftime("%Y%m%d")
    for backup in database.list_backups():
        if f"finance_control_{today}_" in backup["name"] and "automatico" in backup["name"]:
            return None
    return database.create_backup("automatico")


def manual_backup():
    return database.create_backup("manual")


def list_backups():
    return database.list_backups()


def restore(path):
    database.restore_backup(path)


def save_copy(destination):
    return database.copy_database_file(destination)
