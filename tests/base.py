import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database  # noqa: E402
from backend.services import accounts, categories  # noqa: E402


class DbTestCase(unittest.TestCase):
    """Cada teste usa um banco novo e temporário (nunca dados reais)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="fc_test_")
        self._old = database.DB_PATH
        database.set_db_path(Path(self._tmp) / "test.db")
        database.init_db()
        self.account = accounts.get_default_account_id()
        self.food = self.cat("Alimentação", "expense")
        self.salary = self.cat("Salário", "income")

    def tearDown(self):
        database.set_db_path(self._old)
        shutil.rmtree(self._tmp, ignore_errors=True)

    @staticmethod
    def cat(name, kind):
        for c in categories.get_categories(kind):
            if c["name"] == name:
                return c["id"]
        raise AssertionError(name)
