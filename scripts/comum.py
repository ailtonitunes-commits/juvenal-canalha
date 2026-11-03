"""Funcoes compartilhadas: caminhos, fila e sincronizacao com o Git."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
SLIDES = DOCS / "slides"
FILA = DOCS / "fila.json"
STATUS = DOCS / "status.json"
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
FUSO = ZoneInfo(CONFIG["fuso"])


def agora():
    return datetime.now(FUSO)


def carregar_fila():
    if not FILA.exists():
        return []
    return json.loads(FILA.read_text(encoding="utf-8"))


def _gravar(caminho, dados):
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(caminho)


def salvar_fila(fila):
    _gravar(FILA, fila)


def carregar_status():
    return json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}


def salvar_status(**novos):
    status = carregar_status()
    status.update(novos)
    _gravar(STATUS, status)


def site_url():
    if CONFIG.get("site_url"):
        return CONFIG["site_url"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        raise RuntimeError("Defina site_url em config.json ou GITHUB_REPOSITORY.")
    dono, nome = repo.split("/", 1)
    return f"https://{dono.lower()}.github.io/{nome}"


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True, text=True).stdout


def sincronizar(mensagem):
    """Faz commit e push. Retorna True se havia mudanca. Falha alto se nao conseguir enviar."""
    if os.environ.get("SEM_GIT"):
        return True
    _git("add", "docs", "entrada")
    if not _git("status", "--porcelain"):
        return False
    _git("commit", "-m", mensagem)
    ultimo = None
    for _ in range(5):
        try:
            _git("pull", "--rebase", "origin", "main")
            _git("push", "origin", "HEAD:main")
            saida = os.environ.get("GITHUB_OUTPUT")
            if saida:
                with open(saida, "a", encoding="utf-8") as f:
                    f.write("mudou=true\n")
            return True
        except subprocess.CalledProcessError as erro:
            ultimo = erro
    raise RuntimeError(f"Nao foi possivel enviar para o GitHub: {ultimo.stderr}")
