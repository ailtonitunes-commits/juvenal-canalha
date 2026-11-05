"""Le frases de um Excel, gera as artes e coloca cada post no proximo horario livre.

Uso: python scripts/importar.py entrada/frases.xlsx [--inicio AAAA-MM-DD] [--simular]
Sem caminho, processa todo .xlsx de entrada/ e move para entrada/processados/.
"""
import argparse
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import load_workbook

import arte
import reels
from comum import CONFIG, FUSO, RAIZ, SLIDES, agora, carregar_fila, salvar_fila, sincronizar


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in texto if not unicodedata.combining(c))).strip()


def ler_excel(caminho):
    aba = load_workbook(caminho, read_only=True, data_only=True).active
    linhas = [list(l) for l in aba.iter_rows(values_only=True)]
    linhas = [l for l in linhas if any(c not in (None, "") for c in l)]
    if not linhas:
        return []
    cab = [normalizar(str(c or "")) for c in linhas[0]]
    tem_cab = "frase" in cab or "frases" in cab
    col_f = cab.index("frase") if "frase" in cab else cab.index("frases") if "frases" in cab else 0
    col_l = cab.index("legenda") if "legenda" in cab else None
    itens = []
    for linha in linhas[1 if tem_cab else 0:]:
        frase = str(linha[col_f] or "").strip() if col_f < len(linha) else ""
        frase = re.sub(r"[ \t]{3,}", "\n\n", frase)
        if not frase:
            continue
        legenda = ""
        if col_l is not None and col_l < len(linha) and linha[col_l]:
            legenda = str(linha[col_l]).strip()
        itens.append({"frase": frase, "legenda": legenda})
    return itens


def horarios_livres(fila, inicio):
    ocupados = {p["quando"] for p in fila}
    limite = agora() + timedelta(hours=1)
    dia = inicio or limite.date()
    horas = [time(*map(int, h.split(":"))) for h in CONFIG["horarios"]]
    while True:
        for h in horas:
            quando = datetime.combine(dia, h, tzinfo=FUSO)
            if quando > limite and quando.isoformat() not in ocupados:
                yield quando
        dia += timedelta(days=1)


def importar(itens, inicio=None, simular=False):
    fila = carregar_fila()
    vistas = {normalizar(p["frase"]) for p in fila}
    proximo = max((p["id"] for p in fila), default=0) + 1
    legendas = CONFIG["legendas"]
    vagas = horarios_livres(fila, inicio)
    novos, duplicadas, recusadas = [], [], []
    for item in itens:
        chave = normalizar(item["frase"])
        if chave in vistas:
            duplicadas.append(item["frase"])
            continue
        try:
            arte.diagramar(item["frase"])
            arte.diagramar(item["frase"], reels.AREA["largura"], reels.AREA["topo"], reels.AREA["base"])
        except arte.FraseLonga as erro:
            recusadas.append(str(erro))
            continue
        vistas.add(chave)
        slide = f"{proximo:04d}.jpg"
        quando = next(vagas)
        tipo = "reels" if f"{quando:%H:%M}" in CONFIG.get("reels_horarios", []) else "post"
        post = {
            "id": proximo,
            "frase": item["frase"],
            "legenda": item["legenda"] or legendas[proximo % len(legendas)],
            "quando": quando.isoformat(),
            "slide": slide,
            "tipo": tipo,
            "video": f"{proximo:04d}.mp4" if tipo == "reels" else "",
            "status": "agendado",
            "tentativas": 0,
            "erro": "",
            "media_id": "",
            "publicado_em": "",
        }
        if not simular:
            arte.gerar(item["frase"], SLIDES / slide)
            if tipo == "reels":
                reels.gerar(item["frase"], SLIDES / post["video"])
        novos.append(post)
        proximo += 1
    if not simular:
        salvar_fila(fila + novos)
    return novos, duplicadas, recusadas


def relatorio(novos, duplicadas, recusadas):
    print(f"Novos: {len(novos)} | Repetidas: {len(duplicadas)} | Recusadas: {len(recusadas)}")
    if novos:
        print(f"Periodo: {novos[0]['quando'][:16]} ate {novos[-1]['quando'][:16]}")
    for texto in recusadas:
        print(f"  RECUSADA: {texto}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("arquivo", nargs="?")
    p.add_argument("--inicio", type=date.fromisoformat)
    p.add_argument("--simular", action="store_true")
    a = p.parse_args()
    entrada = RAIZ / "entrada"
    arquivos = [Path(a.arquivo)] if a.arquivo else sorted(entrada.glob("*.xlsx"))
    if not arquivos:
        print("Nenhuma planilha para importar.")
        return 0
    recusou = False
    for arq in arquivos:
        novos, dup, rec = importar(ler_excel(arq), a.inicio, a.simular)
        relatorio(novos, dup, rec)
        recusou = recusou or bool(rec)
        if not a.simular and arq.parent.resolve() == entrada.resolve():
            shutil.move(str(arq), entrada / "processados" / f"{agora():%Y%m%d-%H%M%S}-{arq.name}")
        if not a.simular:
            sincronizar(f"Importa {len(novos)} posts de {arq.name}")
    return 1 if recusou else 0


if __name__ == "__main__":
    sys.exit(main())
