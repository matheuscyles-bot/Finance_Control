# Finance Control 2.0

Controle financeiro pessoal para desktop (Python + Tkinter + SQLite). Funciona 100% offline:
**nenhum dado financeiro sai do seu computador** e o app não usa internet.

## O que o app faz
- **Painel**: saldo total, receitas/despesas/resultado do mês (com comparação ao mês anterior), gráfico de 6 meses, despesas por categoria, orçamentos e últimas movimentações.
- **Movimentações**: cadastro rápido, busca (sem diferenciar acentos), filtros (período, tipo, categoria, conta), ordenação, duplicar, editar, excluir **com desfazer**, parcelamento (valor dividido sem perder centavos), exportar/importar CSV.
- **Contas e transferências**: várias contas (corrente, poupança, dinheiro, cartão) com saldo próprio. Transferências movem dinheiro entre contas e **não contam como receita nem despesa**.
- **Orçamentos** mensais por categoria, com copiar do mês anterior.
- **Relatórios**: qualquer período, por conta, comparação com o período anterior e ranking de categorias.
- **Recorrências**: aluguel, assinaturas, salário… criados automaticamente (semanal/mensal/anual), sem duplicar.
- **Backup**: automático (1 por dia + 1 antes de cada atualização do banco), manual, cópia e restauração.
- Tema escuro premium como padrão em instalações novas (a preferência existente é preservada), tema claro opcional, moedas £ € $ R$, atalhos (⌘N nova movimentação, ⌘F buscar, ⌘1…6 telas, ⌘, configurações).

## Instalar no Mac (sem VS Code)
1. Instale o **Python 3.12** de <https://www.python.org/downloads/macos/> (uma única vez; o Python que já vem no Mac tem um Tk antigo e não serve).
2. Dê **duplo clique** em `Criar_App_Mac.command` (primeira vez: botão direito → Abrir → Abrir). Ele roda os testes, gera `Finance Control.app` e `dist/FinanceControl.dmg`, instala em Aplicativos, cria um atalho na Mesa e abre o app. Precisa de internet só para baixar o PyInstaller.
3. Pronto: abra pelo ícone. Para só testar sem instalar, use `Abrir_Finance_Control.command`.

Alternativa sem usar o Terminal do Mac: `.github/workflows/build-macos.yml` gera o `.dmg` na nuvem do GitHub (Actions → Build macOS app → Run workflow).

> Status honesto: o código e os testes foram verificados em Linux. A geração do `.app/.dmg` **não pôde ser testada** fora de um Mac; veja `CHANGELOG.md`.

## Onde ficam seus dados
- macOS: `~/Library/Application Support/Finance Control/` (banco `finance_control.db`, `backups/`, `logs/`).
- Mudar o local: variável de ambiente `FINANCE_CONTROL_DATA`.
- Na primeira abertura, se existir `data/finance_control.db` na pasta do projeto e ainda não houver banco no local acima, ele é **copiado** (o original nunca é alterado) e atualizado com backup automático.
- Trazer dados de outro arquivo: Configurações → Backup → *Restaurar de arquivo…* (o app guarda uma cópia do estado atual antes).

## Atualizar sem perder dados
Gere o app novamente (`Criar_App_Mac.command`). Os dados ficam fora do app e nunca são apagados na atualização. Mudanças de estrutura do banco são migrações versionadas, sempre precedidas de backup.

## Desenvolvimento
```
python3.12 -m backend.main               # executar
python3.12 -m unittest discover -s tests -t .   # testes automatizados
```
Os testes de interface precisam de tela (em servidor: `xvfb-run -a ...`); sem tela eles são pulados. Só biblioteca padrão; `requirements-build.txt` é usado apenas para empacotar.

Estrutura: `backend/` (entrada do app, configurações, regras de negócio e utilitários) · `frontend/` (telas) · `database/` (SQLite, migrações e backup) · `tests/` · `packaging/` · `_arquivo_antigo/` (arquivos da versão 1 que não eram usados, guardados por segurança).

## Regras importantes
- Valores guardados como inteiros (centavos); entrada aceita `25,50`, `25.50`, `1.234,56`, `1,234.56`; rejeita zero, negativos, letras e mais de 2 casas.
- Datas em DD/MM/AAAA na tela e ISO no banco. Lançamentos futuros não alteram o saldo de hoje (aparecem como "previsto").
- Excluir categoria em uso exige escolher outra para receber os lançamentos; conta com histórico só pode ser arquivada (e só com saldo zero).
