# Public deployment guide

Este guia prepara o FuzzySWOT Strategy Prioritizer para divulgacao publica como MVP.

## Opcao recomendada: Streamlit Community Cloud

1. Crie um repositorio no GitHub.
2. Envie estes arquivos para o repositorio.
3. Acesse `https://share.streamlit.io`.
4. Clique em `Create app`.
5. Selecione o repositorio, branch e arquivo principal:

```text
streamlit_app.py
```

6. Em `Advanced settings`, configure Python 3.12 se a opcao aparecer.
7. Em `Secrets`, adicione:

```toml
FUZZYSWOT_DEPLOYMENT_MODE = "public"
```

8. Clique em `Deploy`.
9. Teste o fluxo completo em uma janela anonima antes de divulgar o link.

## Comportamento em modo publico

Quando `FUZZYSWOT_DEPLOYMENT_MODE` esta como `public`:

- O app mostra aviso de uso publico e privacidade.
- O PDF e gerado em memoria e entregue pelo botao de download.
- O app nao grava relatorios em pasta local do servidor.
- Nao ha login, banco de dados ou historico de analises.

## Aviso recomendado para divulgacao

Use uma comunicacao parecida com esta ao divulgar:

```text
Ferramenta academica para priorizacao estrategica por SWOT Fuzzy e TOWS.
Nao insira dados pessoais, sigilosos ou sensiveis. A versao publica nao possui login,
banco de dados ou historico; o relatorio e gerado apenas para download durante a sessao.
```

## Limites do MVP publico

- Nao ha persistencia entre sessoes.
- Nao ha controle de acesso.
- O desempenho depende dos limites da hospedagem gratuita.
- Usuarios simultaneos podem exigir migracao futura para uma arquitetura SaaS.

## Proxima evolucao

Para uma plataforma mais robusta:

- Autenticacao de usuarios.
- Organizacoes/projetos com permissoes.
- Banco PostgreSQL.
- Historico de analises.
- Dominio proprio.
- Politica de privacidade formal.
