# Contribuindo

Obrigado pelo interesse em melhorar o Finance Control.

## Antes de começar
- Abra uma issue para mudanças maiores, para combinarmos a direção antes do código.
- Mantenha o app offline: não adicione chamadas de rede nem envio de dados financeiros.

## Ambiente
```
python3.12 -m backend.main                         # executar
python3.12 -m unittest discover -s tests -t .      # testes
python3.12 scripts/check_locales.py                # idiomas
```
Use dados de teste ao rodar o app: `FINANCE_CONTROL_DATA=/tmp/x python3.12 -m backend.main`.

## Regras do projeto
- Valores monetários são inteiros (centavos). Não use `float` para dinheiro.
- Textos visíveis passam por `t()`. Chaves novas precisam existir nos 9 catálogos em `locales/`.
- Testes que mexem na interface devem funcionar sem tela (são pulados quando não há display).

## Pull requests
- Um assunto por PR, com descrição do que muda e como testar.
- Antes de abrir o PR, rode os testes e `check_locales.py`. O CI faz o mesmo.
- Mudanças visuais: inclua uma captura de tela.

## Licença
Ao contribuir, você concorda que sua contribuição é distribuída sob a licença MIT do projeto.
