"""Transforma em Reels os posts agendados que caem nos horarios de Reels."""
from datetime import datetime

import reels
from comum import CONFIG, SLIDES, carregar_fila, salvar_fila, sincronizar


def main():
    fila = carregar_fila()
    horarios = CONFIG["reels_horarios"]
    feitos = 0
    for post in fila:
        hora = f"{datetime.fromisoformat(post['quando']):%H:%M}"
        if post["status"] != "agendado" or hora not in horarios or post.get("tipo") == "reels":
            continue
        video = f"{post['id']:04d}.mp4"
        reels.gerar(post["frase"], SLIDES / video)
        post["tipo"], post["video"] = "reels", video
        feitos += 1
        print(f"Reel {post['id']} pronto ({feitos})", flush=True)
    salvar_fila(fila)
    sincronizar(f"Converte {feitos} posts em Reels")


if __name__ == "__main__":
    main()
