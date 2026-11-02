# Política de segurança

O Finance Control guarda dados financeiros pessoais localmente, em um banco SQLite no computador do usuário, e não usa a internet.

## Como reportar uma vulnerabilidade
Não abra uma issue pública para falhas de segurança. Envie o relatório por mensagem privada ao mantenedor do repositório, pelo perfil do GitHub `matheuscyles-bot`, com:
- a versão do app e o sistema operacional;
- os passos para reproduzir;
- o impacto que você identificou.

Responderemos o quanto antes e combinaremos a correção antes de qualquer divulgação pública.

## Escopo
Relatórios úteis incluem, por exemplo: leitura ou escrita indevida no banco, corrupção de backups, execução de código a partir de arquivos importados (CSV, banco de backup) e vazamento de dados em logs.

## Dados do usuário
- Os dados ficam em `~/Library/Application Support/Finance Control/` (ou no caminho definido em `FINANCE_CONTROL_DATA`).
- O app não envia dados para fora do computador.
