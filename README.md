# Juvenal Canalha: automação de posts

Publica 5 carrosséis por dia no `@juvenalcanalha`: a arte da frase mais o slide fixo "Siga".

## Como funciona

1. A planilha entra em `entrada/` com a coluna `frase` e, se quiser, `legenda`.
2. O workflow **Importar** gera as artes, ignora frases repetidas e ocupa os próximos horários livres.
3. O workflow **Publicar** roda a cada 10 minutos e publica o post que chegou no horário.
4. O painel mostra a fila, os publicados e os problemas.

Horários e legendas padrão ficam em `config.json`.

## Status no painel

| Status | Significado |
|---|---|
| Agendado | Aguardando o horário |
| Publicando | Pedido enviado agora ao Instagram |
| Publicado | Saiu no perfil |
| Erro | Falhou 3 vezes antes de publicar. Nada saiu |
| Verificar | Resposta incerta. Confira no Instagram. Não é repetido, para não duplicar |

## Configuração inicial

### 1. GitHub
1. Crie um repositório **público** chamado `juvenal-canalha`, vazio.
2. Envie este projeto para ele.
3. Em **Settings > Pages**, em **Source**, escolha **GitHub Actions**.

### 2. Instagram
A conta entra em um portfólio da Meta, e o acesso usa um usuário do sistema, com token que não expira.

1. Ligue `@juvenalcanalha` ao portfólio e o app a esse portfólio.
2. Crie um usuário do sistema, atribua o app e o perfil do Instagram a ele.
3. Gere o token com `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` e `business_management`.

### 3. Segredo
Em **Settings > Secrets and variables > Actions**, crie `IG_ACCESS_TOKEN` com o token gerado.

Esse token não expira. O workflow **Renovar acesso** fica desativado.

### 4. Primeiro teste
1. Importe uma planilha com 2 frases.
2. Em **Actions > Publicar**, use **Run workflow** depois que chegar o horário.
3. Confira no Instagram se o carrossel saiu em 4:5, com os dois slides sem corte.

## Comandos locais

```bash
pip install -r requirements.txt pytest
pytest -q
python scripts/importar.py entrada/frases.xlsx --simular
python scripts/importar.py entrada/frases.xlsx --inicio 2026-11-10
```

## Limitações

- Não dá para escolher música da biblioteca do Instagram pela API.
- O horário pode atrasar alguns minutos: o agendador do GitHub não é exato.
- A documentação da Meta indica corte 1:1 como padrão em carrosséis. O primeiro teste confirma se o formato 4:5 é mantido.
- Fila, frases e artes ficam públicas no site e no repositório, inclusive antes de sair. Nenhuma senha ou token fica neles.
