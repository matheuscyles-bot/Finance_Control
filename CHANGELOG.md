# Changelog

## 2.0.0
### Bugs corrigidos (versão 1)
- O app abria com erro: telas importavam funções que não existiam (`edit_transaction`, `today_iso`, `get_budgets`…).
- Coluna do banco `date` x `transaction_date`: salvar/ler movimentações falhava.
- Valores truncados (`int(float*100)`: 19,99 virava 19,98) → agora Decimal exato.
- Salvar orçamento com argumentos trocados; relatórios omitiam lançamentos sem categoria (INNER JOIN).
- Arquivos duplicados/mortos (`app.py` e `*_page.py` na raiz, `database.py.bak`) → movidos para `_arquivo_antigo/`, nada foi apagado.
### Base
- Migrações versionadas (`PRAGMA user_version`), em transação, com backup automático antes; WAL; `quick_check` na abertura; índices; restrições (`amount > 0`, chaves estrangeiras).
- Textos em português; categorias padrão em português (renomeia as antigas em inglês sem duplicar).
- Testes automatizados de dinheiro, CRUD, filtros, transferências, parcelas, recorrências, importação, backup/restauração, migração e fluxo da interface.
### Interface
- Nova interface (menu lateral, painel com indicadores e gráficos, tema claro/escuro, estados vazios, avisos com "Desfazer", atalhos, paginação, tabelas ordenáveis).
### Recursos novos
- Contas, transferências, parcelamento, recorrências, importar/exportar CSV, backup/restauração, comparação de períodos.

## Limitações conhecidas
- **Empacotamento macOS não testado**: o ambiente de desenvolvimento era Linux (sem PyInstaller disponível). Receita em `packaging/FinanceControl.spec`; a interface foi testada com Tk 9 no Linux, e o Mac usa Tk 8.6 (diferenças visuais pequenas são possíveis).
- App sem assinatura da Apple: se o `.dmg` for baixado/enviado de outro computador, o macOS pede confirmação (botão direito → Abrir). Gerado no seu próprio Mac pelo `.command`, isso normalmente não ocorre.
- Cartão de crédito é tratado como uma conta comum (sem fechamento de fatura).
- Sem sincronização entre computadores e sem senha no banco (os dados ficam na sua conta do macOS).
