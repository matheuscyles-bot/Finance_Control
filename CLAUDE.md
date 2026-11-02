# Finance Control — mapa do projeto

## Stack
- Python 3.12 + Tkinter/ttk (desktop macOS), Pillow; SQLite em ~/Library/Application Support/Finance Control.
- Valores em centavos inteiros. Textos via `t()` em 9 idiomas (`locales/*.json`, todos com as mesmas chaves).
- Fontes empacotadas: Manrope + Lucide (ícones), registradas via CoreText (`frontend/fonts.py`).

## Rodar
- App: `python3 -m backend.main` (dados de teste: `FINANCE_CONTROL_DATA=/tmp/x python3 -m backend.main`)
- Testes: `python3 -m unittest discover -s tests -t .` · idiomas: `python3 scripts/check_locales.py`
- Pacote: `Criar_App_Mac.command` (PyInstaller, `packaging/FinanceControl.spec`)

## Pastas
- `backend/services/` dados (transactions, accounts, budgets, recurring, reports, planning = leituras das telas novas)
- `frontend/theme.py` tokens (cores, fontes, raios, durações) · `draw.py` formas/degradê/curvas · `motion.py` animações (EdgeSlider = pílula do gsap)
- `frontend/widgets.py` Button, Card, Segmented, EmptyState, Toasts, tabela, datas · `ui.py` CircleButton, Panel, Chip, Badge, AvatarStack, PillSelect, SearchField, Toggle, MonthSwitcher, Popover
- `frontend/charts.py` AreaChart, StackedBars, GroupedBars, Donut, Gauge, ProgressBar
- `frontend/app.py` casca: barra superior + abas, barra lateral, cabeçalho (título 2 linhas + KPIs via `Page.publish`)
- `frontend/pages/*.py` uma tela por arquivo · `tests/` unittest (inclui fluxo de UI real)

## Redesign (branch `redesign-dashboard`)
- Pronto: tokens, fontes, animações, componentes, gráficos, casca, serviço `planning`.
- Páginas: 1 de 8 redesenhadas (dashboard ✓). As demais mostram o conteúdo antigo dentro da casca nova.
- Ordem: 1 dashboard (Visão geral) ✓ · 2 pipeline (Vencimentos, nova) ← próxima · 3 accounts · 4 schedule (Agenda, substitui recurring) · 5 transactions · 6 reports · 7 budgets · 8 settings.
- Ao trocar `NAV` em app.py: abas = todas menos settings; atalhos ⌘1…⌘7.

## Regras
- Respostas curtas e diretas. Sem introdução, sem elogio, sem repetir o que o usuário disse, sem recapitular.
- Nunca releia um arquivo que acabou de editar; use `git diff` para conferir.
- Leia só os arquivos necessários; use grep antes de abrir arquivo grande.
- Prefira editar trechos a reescrever o arquivo inteiro.
- Não explore o projeto inteiro de novo; use este CLAUDE.md como mapa.
- Uma página/etapa por vez e um commit curto por etapa; pare para aprovação após cada página.
- Se um erro se repetir 2 vezes, pare e explique a causa em vez de tentar às cegas.
- Saída de comandos longos: mostre só o final ou as linhas de erro.
- Tkinter: nunca use `self._w` em widgets (nome interno do Tk). Chaves novas de idioma vão nos 9 catálogos.

## PENDENCIAS 
- Pendência (planning.bills_board): despesa de hoje cai em "pago" (o futuro começa amanhã) e não há status de pago. Decidir na página Vencimentos: renomear coluna ou criar campo paid (migração v4).
- Pendência i18n: frontend/dialogs.py, erros de backend/services/* e "Sem categoria" (reports.py, planning.py) estão fixos em português.