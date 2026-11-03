"""Gera a imagem da frase no modelo aprovado do Juvenal (1080x1350, JPEG)."""
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from comum import RAIZ

BASE = RAIZ / "assets" / "base.png"
FONTE = RAIZ / "assets" / "Poppins-Medium.ttf"
TINTA = (24, 34, 44)
LARGURA_MAX = 950
CENTRO_Y = 585
LIMITE_INFERIOR = 735
LIMITE_SUPERIOR = 70


class FraseLonga(ValueError):
    pass


@lru_cache(maxsize=16)
def _fonte(tamanho):
    return ImageFont.truetype(str(FONTE), tamanho)


def _quebrar_bloco(texto, fonte):
    """Divide um paragrafo em linhas equilibradas, preferindo quebrar apos pontuacao."""
    palavras = texto.split()
    if not palavras:
        return []
    medir = fonte.getlength
    n = len(palavras)
    melhor = [(float("inf"), -1)] * (n + 1)
    melhor[0] = (0, -1)
    espaco = medir(" ")
    largura_ideal = min(LARGURA_MAX, medir(" ".join(palavras)) * 0.62 + 200)
    for fim in range(1, n + 1):
        for ini in range(fim - 1, -1, -1):
            linha = " ".join(palavras[ini:fim])
            larg = medir(linha)
            if larg > LARGURA_MAX:
                if ini == fim - 1:
                    raise FraseLonga(f"Palavra grande demais: {palavras[ini]}")
                break
            custo = ((largura_ideal - larg) / 100) ** 2 + 8
            if fim < n and not re.search(r"[.,!?;:]$", palavras[fim - 1]):
                custo += 3
            total = melhor[ini][0] + custo
            if total < melhor[fim][0]:
                melhor[fim] = (total, ini)
    linhas, fim = [], n
    while fim > 0:
        ini = melhor[fim][1]
        linhas.append(" ".join(palavras[ini:fim]))
        fim = ini
    return linhas[::-1]


def diagramar(frase):
    """Retorna (linhas, tamanho, entrelinha) que cabem na area de texto."""
    for tamanho in (56, 52, 48, 44, 40, 36):
        fonte = _fonte(tamanho)
        linhas = []
        for bloco in frase.strip().split("\n"):
            linhas.extend(_quebrar_bloco(bloco, fonte) or [""])
        passo = round(tamanho * 1.38)
        altura = passo * len(linhas)
        if altura <= LIMITE_INFERIOR - LIMITE_SUPERIOR:
            return linhas, tamanho, passo
    raise FraseLonga(f"Frase longa demais para a arte: {frase[:50]}...")


def gerar(frase, destino):
    linhas, tamanho, passo = diagramar(frase)
    img = Image.open(BASE).convert("RGB")
    desenho = ImageDraw.Draw(img)
    fonte = _fonte(tamanho)
    altura = passo * len(linhas)
    topo = min(CENTRO_Y - altura / 2, LIMITE_INFERIOR - altura)
    for i, linha in enumerate(linhas):
        desenho.text((540, topo + passo * (i + 0.5)), linha, font=fonte, fill=TINTA, anchor="mm")
    img.save(destino, "JPEG", quality=92, subsampling=0, optimize=True)
