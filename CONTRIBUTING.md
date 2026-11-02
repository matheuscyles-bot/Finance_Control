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
- Testes de interface são pulados quando não há tela. No Linux, rode com `xvfb-run -a python3.12 -m unittest discover -s tests -t .` para não deixar de testá-los.
- Nunca inclua dados financeiros reais em issues, PRs, capturas ou testes. Use sempre dados de teste.
- Idioma: o README e este guia estão em inglês; comentários e textos internos do código estão em português. PRs e issues em inglês ou português são bem-vindos.

## Pull requests
- Um assunto por PR, com descrição do que muda e como testar.
- Antes de abrir o PR, rode os testes e `check_locales.py`. O CI faz o mesmo.
- Mudanças visuais: inclua uma captura de tela.

## Licença
Ao contribuir, você concorda que sua contribuição é distribuída sob a licença MIT do projeto.
