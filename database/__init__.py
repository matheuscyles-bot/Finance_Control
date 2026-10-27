"""Acesso ao SQLite, migrações versionadas e backups.

O esquema é versionado com ``PRAGMA user_version``. Ao abrir um banco mais
antigo, o app salva um backup e aplica as migrações em uma única transação:
se algo falhar, nada é alterado.
"""

import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from backend.config import (
    BACKUP_KEEP,
    DEFAULT_ACCOUNT_NAME,
    DEFAULT_CATEGORIES,
    DEFAULT_CURRENCY,
    DEFAULT_THEME,
    LEGACY_CATEGORY_RENAMES,
)
from backend.utils.text import normalize_text

log = logging.getLogger("finance_control.database")

BASE_DIR = Path(__file__).resolve().parent.parent


def default_data_dir():
    """Pasta dos dados do usuário, separada dos arquivos do aplicativo.

    - variável FINANCE_CONTROL_DATA (se definida);
    - macOS: ~/Library/Application Support/Finance Control;
    - Linux/Windows: ~/.finance_control se empacotado; no desenvolvimento: pasta ``data`` do projeto.
    """
    override = os.environ.get("FINANCE_CONTROL_DATA")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Finance Control"
    if getattr(sys, "frozen", False):
        return Path.home() / ".finance_control"
    return BASE_DIR / "data"


DATA_DIR = default_data_dir()
DB_PATH = DATA_DIR / "finance_control.db"
BACKUP_DIR = DATA_DIR / "backups"

SCHEMA_VERSION = 3


class DatabaseError(RuntimeError):
    """Erro de banco com mensagem amigável para o usuário."""


def set_db_path(path):
    """Troca o arquivo do banco (usado em testes e na restauração)."""
    global DB_PATH, DATA_DIR, BACKUP_DIR
    DB_PATH = Path(path)
    DATA_DIR = DB_PATH.parent
    BACKUP_DIR = DATA_DIR / "backups"


def _configure(connection):
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.create_function("norm", 1, normalize_text, deterministic=True)
    return connection


@contextmanager
def get_connection():
    """Conexão com commit automático e rollback em caso de erro."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = _configure(sqlite3.connect(DB_PATH, timeout=10))
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_all(query, params=()):
    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def fetch_one(query, params=()):
    with get_connection() as conn:
        return conn.execute(query, params).fetchone()


def execute(query, params=()):
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid


class Database:
    """Wrapper simples mantido por compatibilidade com a versão 1.0."""

    def init_db(self):
        init_db()

    def get_connection(self):
        return get_connection()

    def fetch_all(self, query, params=()):
        return fetch_all(query, params)

    def fetch_one(self, query, params=()):
        return fetch_one(query, params)

    def execute(self, query, params=()):
        return execute(query, params)


# ----------------------------------------------------------------------
# Migrações
# ----------------------------------------------------------------------

def _run(conn, statements):
    for statement in statements:
        conn.execute(statement)


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _migration_1_baseline(conn):
    """Normaliza o banco da versão 1.0 (ou cria a estrutura básica)."""
    _run(conn, [
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
            UNIQUE(name, kind)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
            category_id INTEGER,
            transaction_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
                ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount INTEGER NOT NULL,
            UNIQUE(category_id, month),
            FOREIGN KEY (category_id) REFERENCES categories(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """,
    ])

    # Banco antigo: a coluna da data se chamava "date".
    columns = _columns(conn, "transactions")
    if "date" in columns and "transaction_date" not in columns:
        conn.execute(
            "ALTER TABLE transactions RENAME COLUMN date TO transaction_date"
        )


def _migration_2_accounts(conn):
    """Contas, transferências, recorrências, parcelas, restrições e índices."""
    invalid = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE amount = 0"
    ).fetchone()[0]
    if invalid:
        raise DatabaseError(
            "O banco contém movimentações com valor zero e não pôde ser "
            "atualizado. Nenhum dado foi alterado; o backup foi preservado."
        )

    _run(conn, [
        """
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            type TEXT NOT NULL DEFAULT 'checking'
                CHECK (type IN ('checking', 'savings', 'cash', 'credit_card')),
            opening_balance INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE recurring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK (amount > 0),
            kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            account_id INTEGER NOT NULL REFERENCES accounts(id)
                ON DELETE RESTRICT,
            frequency TEXT NOT NULL
                CHECK (frequency IN ('weekly', 'monthly', 'yearly')),
            anchor_day INTEGER NOT NULL DEFAULT 1,
            next_date TEXT NOT NULL,
            end_date TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account_id INTEGER NOT NULL REFERENCES accounts(id)
                ON DELETE RESTRICT,
            to_account_id INTEGER NOT NULL REFERENCES accounts(id)
                ON DELETE RESTRICT,
            amount INTEGER NOT NULL CHECK (amount > 0),
            transfer_date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CHECK (from_account_id <> to_account_id)
        )
        """,
        "INSERT INTO accounts (name, type, opening_balance) VALUES "
        f"('{DEFAULT_ACCOUNT_NAME}', 'checking', 0)",
        """
        CREATE TABLE transactions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK (amount > 0),
            kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            account_id INTEGER NOT NULL REFERENCES accounts(id)
                ON DELETE RESTRICT,
            transaction_date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            installment_group TEXT,
            installment_no INTEGER,
            installment_total INTEGER,
            recurring_id INTEGER REFERENCES recurring(id) ON DELETE SET NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        INSERT INTO transactions_new
            (id, description, amount, kind, category_id, account_id,
             transaction_date, notes, created_at)
        SELECT id, description, ABS(amount), kind, category_id,
               (SELECT id FROM accounts ORDER BY id LIMIT 1),
               transaction_date, COALESCE(notes, ''),
               COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM transactions
        """,
        "DROP TABLE transactions",
        "ALTER TABLE transactions_new RENAME TO transactions",
        "CREATE INDEX idx_transactions_date ON transactions(transaction_date)",
        "CREATE INDEX idx_transactions_category ON transactions(category_id)",
        "CREATE INDEX idx_transactions_account ON transactions(account_id)",
        "CREATE INDEX idx_transactions_kind_date "
        "ON transactions(kind, transaction_date)",
        "CREATE INDEX idx_transactions_group ON transactions(installment_group)",
        "CREATE UNIQUE INDEX idx_transactions_recurring_once "
        "ON transactions(recurring_id, transaction_date) "
        "WHERE recurring_id IS NOT NULL",
        "CREATE INDEX idx_transfers_date ON transfers(transfer_date)",
        "CREATE INDEX idx_transfers_from ON transfers(from_account_id)",
        "CREATE INDEX idx_transfers_to ON transfers(to_account_id)",
        "CREATE INDEX IF NOT EXISTS idx_budgets_month ON budgets(month)",
        "CREATE INDEX idx_recurring_next ON recurring(active, next_date)",
    ])


def _migration_3_defaults(conn):
    """Categorias em português e configurações iniciais."""
    for (old, kind), new in LEGACY_CATEGORY_RENAMES.items():
        conn.execute(
            """
            UPDATE categories SET name = ?
            WHERE name = ? AND kind = ?
              AND NOT EXISTS (
                  SELECT 1 FROM categories WHERE name = ? AND kind = ?
              )
            """,
            (new, old, kind, new, kind),
        )

    # Só semeia as categorias padrão em um banco realmente novo.
    has_data = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if not has_data:
        conn.executemany(
            "INSERT OR IGNORE INTO categories (name, kind) VALUES (?, ?)",
            DEFAULT_CATEGORIES,
        )

    conn.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        [("currency_symbol", DEFAULT_CURRENCY), ("theme", DEFAULT_THEME)],
    )


MIGRATIONS = [
    (1, _migration_1_baseline),
    (2, _migration_2_accounts),
    (3, _migration_3_defaults),
]


def _has_user_tables(conn):
    return _table_exists(conn, "transactions") or _table_exists(
        conn, "categories"
    )


def init_db():
    """Cria o banco ou atualiza um existente. Seguro para chamar sempre."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existed = DB_PATH.exists() and DB_PATH.stat().st_size > 0

    connection = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        try:
            check = connection.execute("PRAGMA quick_check").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(
                "O arquivo do banco de dados está danificado. "
                "Restaure um backup em data/backups/."
            ) from exc
        if check != "ok":
            raise DatabaseError(
                "O banco de dados apresentou erros de integridade. "
                "Restaure um backup em data/backups/."
            )

        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise DatabaseError(
                "Este banco foi criado por uma versão mais nova do "
                "Finance Control. Atualize o aplicativo."
            )

        if version < SCHEMA_VERSION:
            if existed and _has_user_tables(connection):
                _backup_connection(
                    connection, f"antes_da_migracao_v{version}_para_v{SCHEMA_VERSION}"
                )
            _apply_migrations(connection, version)

        connection.execute("PRAGMA journal_mode = WAL")
    finally:
        connection.close()


def _apply_migrations(connection, current_version):
    connection.execute("PRAGMA foreign_keys = OFF")
    for target, migration in MIGRATIONS:
        if current_version >= target:
            continue
        connection.execute("BEGIN IMMEDIATE")
        try:
            migration(connection)
            connection.execute(f"PRAGMA user_version = {target}")
            problems = connection.execute("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise DatabaseError(
                    "Falha de integridade ao atualizar o banco. "
                    "Nenhum dado foi alterado."
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        log.info("Banco atualizado para a versão %s", target)
    connection.execute("PRAGMA foreign_keys = ON")


# ----------------------------------------------------------------------
# Backups
# ----------------------------------------------------------------------

def _safe_label(label):
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
    return cleaned[:60] or "backup"


def _backup_connection(connection, label):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"finance_control_{stamp}_{_safe_label(label)}.db"
    counter = 1
    while target.exists():
        target = BACKUP_DIR / (
            f"finance_control_{stamp}_{_safe_label(label)}_{counter}.db"
        )
        counter += 1
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return target


def create_backup(label="manual"):
    """Cria uma cópia consistente do banco. Devolve o caminho do arquivo."""
    if not DB_PATH.exists():
        raise DatabaseError("Ainda não existe um banco de dados para copiar.")
    source = sqlite3.connect(DB_PATH, timeout=10)
    try:
        path = _backup_connection(source, label)
    finally:
        source.close()
    prune_backups()
    return path


def list_backups():
    """Backups existentes, do mais recente para o mais antigo."""
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("finance_control_*.db"), reverse=True)
    result = []
    for path in files:
        info = path.stat()
        result.append({
            "path": path,
            "name": path.name,
            "size": info.st_size,
            "modified": datetime.fromtimestamp(info.st_mtime),
        })
    return result


def prune_backups(keep=BACKUP_KEEP):
    """Remove backups automáticos antigos. Backups manuais e de segurança
    antes de migrar/restaurar nunca são apagados automaticamente."""
    removable = [
        b["path"] for b in list_backups()
        if b["name"].endswith(("_automatico.db",)) or "_automatico_" in b["name"]
    ]
    for path in removable[keep:]:
        try:
            path.unlink()
        except OSError:
            log.warning("Não foi possível remover o backup %s", path.name)


def restore_backup(path):
    """Restaura o banco a partir de um backup, guardando antes uma cópia
    de segurança do estado atual."""
    path = Path(path)
    if not path.exists():
        raise DatabaseError("O arquivo de backup não foi encontrado.")

    try:
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        try:
            if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise DatabaseError("O backup selecionado está danificado.")
            if not _has_user_tables(source):
                raise DatabaseError(
                    "O arquivo selecionado não parece ser um backup do "
                    "Finance Control."
                )
            if source.execute("PRAGMA user_version").fetchone()[0] > SCHEMA_VERSION:
                raise DatabaseError(
                    "Este backup foi criado por uma versão mais nova do app."
                )

            if DB_PATH.exists():
                create_backup("antes_de_restaurar")

            destination = sqlite3.connect(DB_PATH, timeout=10)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(
            "Não foi possível ler o arquivo selecionado como um banco de dados."
        ) from exc

    init_db()  # migra caso o backup seja de uma versão anterior


def integrity_report():
    """Resultado da verificação de integridade, para a tela de Configurações."""
    with get_connection() as conn:
        quick = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
    return {"integrity": quick, "foreign_key_errors": len(foreign)}


def copy_database_file(destination):
    """Cópia de arquivo simples (usada pelo botão 'Salvar cópia')."""
    destination = Path(destination)
    source = sqlite3.connect(DB_PATH, timeout=10)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination



def legacy_database_path():
    """Banco da pasta do projeto (versões 1.x), se existir e ainda não tiver
    sido copiado para a pasta de dados atual."""
    old = BASE_DIR / "data" / "finance_control.db"
    if old.exists() and old.stat().st_size > 0 and old.resolve() != DB_PATH.resolve():
        return old
    return None


def import_database_file(path):
    """Copia (sem alterar o original) um banco existente para a pasta de
    dados atual e o atualiza. Só funciona se ainda não houver banco com dados."""
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        raise DatabaseError("Já existe um banco de dados em uso.")
    restore_backup(path)
