"""Renova o token do Instagram e grava o novo valor no segredo do GitHub."""
import os
import subprocess
import sys
from datetime import timedelta

import requests

from comum import agora, salvar_status, sincronizar

URL = "https://graph.instagram.com/refresh_access_token"


def renovar(token):
    try:
        r = requests.get(URL, params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    except requests.RequestException as e:
        raise RuntimeError(f"Falha de rede: {type(e).__name__}") from None
    dados = r.json() if r.content else {}
    if not r.ok:
        msg = dados.get("error", {}).get("message", "sem detalhe")
        raise RuntimeError(f"HTTP {r.status_code}: {msg}")
    return dados["access_token"], int(dados["expires_in"])


def main():
    token = os.environ.get("IG_ACCESS_TOKEN")
    pat = os.environ.get("GH_ADMIN_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not pat or not repo:
        print("ERRO: faltam IG_ACCESS_TOKEN, GH_ADMIN_TOKEN ou GITHUB_REPOSITORY.")
        return 1
    try:
        novo, expira_s = renovar(token)
    except RuntimeError as erro:
        salvar_status(token_erro=str(erro), token_erro_em=agora().isoformat())
        sincronizar("Falha ao renovar token")
        print(f"ERRO: {erro}")
        return 1
    print(f"::add-mask::{novo}")
    subprocess.run(
        ["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", repo],
        input=novo, text=True, check=True, env={**os.environ, "GH_TOKEN": pat},
        capture_output=True,
    )
    salvar_status(
        token_renovado_em=agora().isoformat(),
        token_expira_em=(agora() + timedelta(seconds=expira_s)).isoformat(),
        token_erro="",
    )
    sincronizar("Token renovado")
    print("Token renovado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
