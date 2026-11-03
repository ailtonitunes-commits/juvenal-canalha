"""Publica no Instagram o post mais antigo que ja chegou no horario.

Regra de seguranca: o post e marcado como 'publicando' e enviado ao GitHub ANTES
do pedido de publicacao. Se algo falhar nesse ponto ele vira 'verificar' e nunca
e repetido automaticamente, para o mesmo post nao sair duas vezes.
"""
import os
import sys
import time
from datetime import datetime

import requests

from comum import CONFIG, agora, carregar_fila, salvar_fila, salvar_status, sincronizar, site_url

API = f"https://graph.instagram.com/{CONFIG['api_versao']}"
MAX_TENTATIVAS = 3
ESPERA_S = int(os.environ.get("ESPERA_CONTAINER_S", "10"))
ESPERA_MAX = 18


class ErroApi(Exception):
    pass


class Api:
    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _chamar(self, metodo, caminho, **kw):
        try:
            r = self.s.request(metodo, f"{API}/{caminho}", timeout=60, **kw)
        except requests.RequestException as e:
            raise ErroApi(f"Falha de rede: {type(e).__name__}") from None
        try:
            dados = r.json()
        except ValueError:
            dados = {}
        if not r.ok:
            info = dados.get("error", {}) if isinstance(dados, dict) else {}
            raise ErroApi(f"HTTP {r.status_code} ({info.get('code', '?')}): {info.get('message', 'sem detalhe')}")
        return dados

    def conta(self):
        return self._chamar("GET", "me", params={"fields": "user_id,username"})

    def item(self, ig, url):
        return self._chamar("POST", f"{ig}/media", data={"image_url": url, "is_carousel_item": "true"})["id"]

    def carrossel(self, ig, filhos, legenda):
        dados = {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda}
        return self._chamar("POST", f"{ig}/media", data=dados)["id"]

    def aguardar(self, container):
        for _ in range(ESPERA_MAX):
            codigo = self._chamar("GET", container, params={"fields": "status_code"}).get("status_code")
            if codigo == "FINISHED":
                return
            if codigo in ("ERROR", "EXPIRED"):
                raise ErroApi(f"Instagram recusou a midia: {codigo}")
            time.sleep(ESPERA_S)
        raise ErroApi("Tempo esgotado aguardando o Instagram processar")

    def publicar(self, ig, container):
        return self._chamar("POST", f"{ig}/media_publish", data={"creation_id": container})["id"]


def data_de(post):
    return datetime.fromisoformat(post["quando"])


def proximo_post(fila, momento):
    hoje = momento.date()
    feitos_hoje = sum(
        1 for p in fila
        if p["publicado_em"] and datetime.fromisoformat(p["publicado_em"]).date() == hoje
    )
    if feitos_hoje >= CONFIG["maximo_por_dia"]:
        return None
    vencidos = [p for p in fila if p["status"] == "agendado" and data_de(p) <= momento]
    return min(vencidos, key=data_de) if vencidos else None


def registrar_pendentes(fila):
    """Post que ficou em 'publicando' em uma execucao interrompida precisa de conferencia."""
    achou = False
    for p in fila:
        if p["status"] == "publicando":
            p["status"] = "verificar"
            p["erro"] = "Execucao interrompida. Confira no Instagram se saiu."
            achou = True
    return achou


def executar(api=None):
    fila = carregar_fila()
    if registrar_pendentes(fila):
        salvar_fila(fila)
        sincronizar("Marca post interrompido para verificacao")
    momento = agora()
    post = proximo_post(fila, momento)
    if post is None:
        print("Nenhum post no horario.")
        return 0
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token and api is None:
        print("ERRO: IG_ACCESS_TOKEN nao configurado.")
        return 1
    api = api or Api(token)
    # 1) prepara. Falhas aqui sao seguras: nada foi publicado.
    try:
        conta = api.conta()
        esperado = CONFIG["conta"].lower()
        if conta.get("username", "").lower() != esperado:
            raise ErroApi(f"Conta conectada ({conta.get('username')}) difere de {esperado}")
        ig = conta["user_id"]
        base = site_url()
        filhos = [
            api.item(ig, f"{base}/slides/{post['slide']}"),
            api.item(ig, f"{base}/slides/siga.jpg"),
        ]
        for filho in filhos:
            api.aguardar(filho)
        container = api.carrossel(ig, filhos, post["legenda"])
        api.aguardar(container)
    except ErroApi as erro:
        post["tentativas"] += 1
        post["erro"] = str(erro)
        if post["tentativas"] >= MAX_TENTATIVAS:
            post["status"] = "erro"
        salvar_fila(fila)
        sincronizar(f"Falha ao preparar post {post['id']}")
        print(f"ERRO no post {post['id']}: {erro}")
        return 1
    # 2) reserva antes de publicar.
    post["status"] = "publicando"
    salvar_fila(fila)
    sincronizar(f"Publicando post {post['id']}")
    # 3) publica uma unica vez.
    try:
        media_id = api.publicar(ig, container)
    except ErroApi as erro:
        post["status"] = "verificar"
        post["erro"] = f"Resposta incerta ao publicar: {erro}. Confira no Instagram."
        salvar_fila(fila)
        sincronizar(f"Post {post['id']} precisa de verificacao")
        print(f"ERRO no post {post['id']}: {post['erro']}")
        return 1
    post["status"] = "publicado"
    post["erro"] = ""
    post["media_id"] = media_id
    post["publicado_em"] = agora().isoformat()
    salvar_fila(fila)
    salvar_status(ultima_publicacao=post["publicado_em"])
    sincronizar(f"Publicado post {post['id']}")
    print(f"Post {post['id']} publicado.")
    return 0


if __name__ == "__main__":
    sys.exit(executar())
