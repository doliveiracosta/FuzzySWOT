# FuzzySWOT Strategy Prioritizer

Projeto web-ready extraido do notebook `FuzzySWOT StrategyPrioritizer.ipynb`.

## O que foi separado

- `fuzzyswot/core.py`: calculos fuzzy, consenso, ranking e geracao TOWS.
- `fuzzyswot/models.py`: estruturas de projeto e avaliadores.
- `fuzzyswot/exports.py`: exportacao do relatorio consultivo em PDF.
- `streamlit_app.py`: MVP web em Streamlit.
- `tests/test_core.py`: testes do nucleo de negocio.

## Rodar localmente

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Rodar testes

```powershell
python -m unittest discover -s tests
```

## Exportacao

O MVP disponibiliza apenas o relatorio consultivo em PDF.

Na aba `Exportacao`, use `Gerar e salvar PDF nesta maquina` para gravar o arquivo em:

```text
outputs/relatorio_consultivo_fuzzy_swot.pdf
```

O botao `Baixar PDF consultivo` continua disponivel, mas depende do comportamento de downloads do navegador.

Para deploy publico, defina a variavel de ambiente:

```text
FUZZYSWOT_DEPLOYMENT_MODE=public
```

Nesse modo, o app nao salva PDFs no servidor; ele apenas entrega o arquivo pelo botao de download.

## Matriz fuzzy

A matriz de avaliacao usa uma escala visual de vermelho a verde e sliders de 0 a 1 para orientar o julgamento de cada relacionamento.

## Pesos dos avaliadores

O peso do avaliador e automatico. A pessoa usuaria escolhe a funcao hierarquica e o sistema aplica o peso correspondente: quanto maior a funcao, maior o peso na consolidacao.

## Publicar online como MVP

Opcoes simples:

- Streamlit Community Cloud, para validacao rapida e link publico.
- Render ou Railway, com o comando `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`.
- Docker em qualquer cloud, usando o mesmo comando acima.

Veja o passo a passo em [`DEPLOYMENT.md`](DEPLOYMENT.md).

Checklist minimo para divulgacao publica:

- Publicar o codigo em um repositorio GitHub.
- Configurar o app apontando para `streamlit_app.py`.
- Definir `FUZZYSWOT_DEPLOYMENT_MODE=public`.
- Revisar o texto metodologico e incluir aviso de privacidade/uso academico.
- Testar o fluxo completo em janela anonima antes de divulgar o link.

## Evolucao para plataforma SaaS

Para virar plataforma multiusuario, os proximos passos recomendados sao:

- Autenticacao e permissoes por organizacao.
- Banco PostgreSQL para projetos, avaliadores, itens SWOT e matrizes.
- Storage para relatorios PDF/Excel.
- Backend FastAPI para regras de negocio e jobs de exportacao.
- Frontend React/Next.js quando a experiencia precisar ir alem do MVP.

O MVP atual usa estado de sessao do Streamlit. Isso e suficiente para demonstracao e validacao, mas ainda nao substitui persistencia em banco de dados.
