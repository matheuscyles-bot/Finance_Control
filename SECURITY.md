# Política de segurança

O Finance Control guarda dados financeiros pessoais localmente, em um banco SQLite no computador do usuário, e não usa a internet.

## Versões suportadas
Apenas a versão mais recente (2.x) recebe correções.

## Como reportar uma vulnerabilidade
Não abra uma issue pública para falhas de segurança. Use o recurso **Report a vulnerability** na aba **Security** do repositório no GitHub (relatório privado). Inclua:
- a versão do app e o sistema operacional;
- os passos para reproduzir;
- o impacto que você identificou.

O projeto é mantido por uma pessoa e não há prazo de resposta garantido. Os relatórios serão analisados, e a correção será combinada antes de qualquer divulgação pública.

## Escopo
Relatórios úteis incluem, por exemplo:
- leitura ou escrita indevida no banco de dados;
- corrupção ou restauração indevida de backups;
- execução de código a partir de arquivos importados (CSV ou banco de backup);
- exposição de dados financeiros em logs.

## Limitações conhecidas
- O banco de dados **não é criptografado nem tem senha** (o app não pede senha ao abrir). A proteção depende da conta de usuário do sistema operacional e da criptografia de disco do computador (FileVault, no macOS).
- Cópias de backup e exportações CSV ficam sem criptografia. Guarde-as em local seguro.

## Dados do usuário
- Os dados ficam em `~/Library/Application Support/Finance Control/` (ou no caminho definido em `FINANCE_CONTROL_DATA`).
- O app não envia dados para fora do computador.
