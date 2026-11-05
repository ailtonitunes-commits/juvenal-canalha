"""Gera o Reel vertical da frase: 5,6 s com a frase e o fim com o aviso Siga."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import arte
from comum import RAIZ

LARGURA, ALTURA = 1080, 1920
FUNDO = (176, 200, 214)
AUDIO = RAIZ / "assets" / "audio.m4a"
BASE_Y = 570
AREA = dict(largura=860, centro=860, topo=210, base=1310)
SIGA = "SIGA JUVENAL CANALHA !"


def quadro(frase, destino):
    tela = Image.new("RGB", (LARGURA, ALTURA), FUNDO)
    tela.paste(Image.open(arte.BASE).convert("RGB"), (0, BASE_Y))
    desenho = ImageDraw.Draw(tela)
    arte.escrever(desenho, frase, **AREA)
    tela.save(destino, "PNG")


def gerar(frase, destino):
    with tempfile.TemporaryDirectory() as pasta:
        a, b = Path(pasta) / "a.png", Path(pasta) / "b.png"
        quadro(frase, a)
        quadro(SIGA, b)
        filtro = (
            "[0:v][1:v]xfade=transition=fade:duration=0.4:offset=5.2,"
            "scale=2160:3840,"
            "zoompan=z='1+0.03*on/210':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s=1080x1920:fps=30,"
            "format=yuv420p[v]"
        )
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-loop", "1", "-framerate", "30", "-t", "5.6", "-i", str(a),
             "-loop", "1", "-framerate", "30", "-t", "1.8", "-i", str(b),
             "-i", str(AUDIO),
             "-filter_complex", filtro, "-map", "[v]", "-map", "2:a", "-t", "7",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-profile:v", "high",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-movflags", "+faststart", str(destino)],
            check=True,
        )
