"""Configurações gerais do Finance Control."""

APP_TITLE = "Finance Control"
APP_VERSION = "2.0.0"

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
MIN_WIDTH = 1040
MIN_HEIGHT = 680

# Moeda padrão (pode ser trocada em Configurações).
DEFAULT_CURRENCY = "£"
CURRENCY_OPTIONS = ["£", "€", "$", "R$"]

DEFAULT_THEME = "dark"
THEMES = {"light": "Claro", "dark": "Escuro"}

ACCOUNT_TYPES = {
    "checking": "Conta corrente",
    "savings": "Poupança",
    "cash": "Dinheiro",
    "credit_card": "Cartão de crédito",
}

FREQUENCIES = {
    "weekly": "Semanal",
    "monthly": "Mensal",
    "yearly": "Anual",
}

# Categorias criadas em um banco novo.
DEFAULT_CATEGORIES = [
    ("Salário", "income"),
    ("Freelance", "income"),
    ("Investimentos", "income"),
    ("Outras receitas", "income"),
    ("Moradia", "expense"),
    ("Alimentação", "expense"),
    ("Transporte", "expense"),
    ("Contas e serviços", "expense"),
    ("Saúde", "expense"),
    ("Educação", "expense"),
    ("Lazer", "expense"),
    ("Compras", "expense"),
    ("Outras despesas", "expense"),
]

# Nomes em inglês usados na versão 1.0, renomeados na migração.
LEGACY_CATEGORY_RENAMES = {
    ("Salary", "income"): "Salário",
    ("Investments", "income"): "Investimentos",
    ("Other income", "income"): "Outras receitas",
    ("Housing", "expense"): "Moradia",
    ("Food", "expense"): "Alimentação",
    ("Transport", "expense"): "Transporte",
    ("Bills", "expense"): "Contas e serviços",
    ("Health", "expense"): "Saúde",
    ("Education", "expense"): "Educação",
    ("Entertainment", "expense"): "Lazer",
    ("Shopping", "expense"): "Compras",
    ("Other expense", "expense"): "Outras despesas",
}

# Categorias usadas quando uma importação traz um nome desconhecido.
FALLBACK_CATEGORY = {"income": "Outras receitas", "expense": "Outras despesas"}

PAGE_SIZE = 200          # linhas carregadas por vez na lista de movimentações
BACKUP_KEEP = 20         # quantidade de backups automáticos mantidos
MAX_INSTALLMENTS = 60
