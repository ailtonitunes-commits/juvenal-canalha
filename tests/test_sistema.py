import json
from datetime import datetime, timedelta

import pytest
from openpyxl import Workbook
from PIL import Image

import arte
import comum
import importar
import publicar


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("SEM_GIT", "1")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "x")
    monkeypatch.setitem(comum.CONFIG, "site_url", "https://site.exemplo")
    slides = tmp_path / "slides"
    slides.mkdir()
    for mod in (comum, importar):
        monkeypatch.setattr(mod, "SLIDES", slides, raising=False)
    monkeypatch.setattr(comum, "FILA", tmp_path / "fila.json")
    monkeypatch.setattr(comum, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(publicar, "ESPERA_S", 0)
    return tmp_path


class ApiFalsa:
    def __init__(self, conta="juvenalcanalha", falha_item=False, falha_pub=False):
        self._conta, self.falha_item, self.falha_pub = conta, falha_item, falha_pub
        self.urls, self.publicados, self.legenda = [], [], None

    def conta(self):
        return {"id": "1", "username": self._conta}

    def item(self, ig, url):
        if self.falha_item:
            raise publicar.ErroApi("HTTP 400")
        self.urls.append(url)
        return f"c{len(self.urls)}"

    def carrossel(self, ig, filhos, legenda):
        self.legenda = legenda
        return "car"

    def reel(self, ig, url, legenda):
        self.urls.append(url); self.legenda = legenda
        return "reel"

    def aguardar(self, c, tentativas=0):
        pass

    def publicar(self, ig, c):
        if self.falha_pub:
            raise publicar.ErroApi("HTTP 500")
        self.publicados.append(c)
        return "m1"


def post(i=1, atras_min=5, status="agendado"):
    q = comum.agora() - timedelta(minutes=atras_min)
    return dict(id=i, frase=f"f{i}", legenda="l", quando=q.isoformat(), slide=f"{i:04d}.jpg", status=status,
                tentativas=0, erro="", media_id="", publicado_em="")


def test_cinco_por_dia_nos_horarios(ambiente):
    itens = [{"frase": f"Frase numero {i}", "legenda": ""} for i in range(150)]
    novos, dup, rec = importar.importar(itens, simular=True)
    assert len(novos) == 150 and not dup and not rec
    por_dia = {}
    for p in novos:
        d = datetime.fromisoformat(p["quando"])
        por_dia.setdefault(d.date(), []).append(f"{d:%H:%M}")
        assert f"{d:%H:%M}" in comum.CONFIG["horarios"]
    assert len({p["quando"] for p in novos}) == 150
    meio = sorted(por_dia)[1:-1]
    assert all(len(por_dia[d]) == 5 for d in meio)
    assert len(meio) >= 28


def test_repetidas_e_reimportacao_nao_duplicam(ambiente):
    novos, _, _ = importar.importar([{"frase": "Olá, mundo!", "legenda": ""}, {"frase": "ola mundo", "legenda": ""}])
    assert len(novos) == 1
    novos2, dup, _ = importar.importar([{"frase": "OLÁ MUNDO", "legenda": ""}])
    assert not novos2 and len(dup) == 1


def test_excel_com_e_sem_cabecalho(ambiente):
    wb = Workbook(); ws = wb.active
    ws.append(["Frase", "Legenda"]); ws.append(["Primeira", "Minha legenda"]); ws.append(["Segunda", None])
    p1 = ambiente / "a.xlsx"; wb.save(p1)
    wb = Workbook(); wb.active.append(["So frase"]); p2 = ambiente / "b.xlsx"; wb.save(p2)
    assert importar.ler_excel(p1) == [{"frase": "Primeira", "legenda": "Minha legenda"}, {"frase": "Segunda", "legenda": ""}]
    assert importar.ler_excel(p2) == [{"frase": "So frase", "legenda": ""}]


def test_arte_jpeg_no_formato_certo(ambiente):
    destino = ambiente / "x.jpg"
    arte.gerar("Frase de teste com acentuação: não, é, ç.", destino)
    img = Image.open(destino)
    assert img.format == "JPEG" and img.size == (1080, 1350)


def test_frase_absurda_e_recusada(ambiente):
    novos, _, rec = importar.importar([{"frase": "palavra " * 200, "legenda": ""}], simular=True)
    assert not novos and len(rec) == 1


def test_publica_carrossel_com_siga(ambiente):
    comum.salvar_fila([post()])
    api = ApiFalsa()
    assert publicar.executar(api) == 0
    p = comum.carregar_fila()[0]
    assert p["status"] == "publicado" and p["media_id"] == "m1"
    assert api.urls == ["https://site.exemplo/slides/0001.jpg", "https://site.exemplo/slides/siga.jpg"]
    assert api.legenda == "l"


def test_nao_publica_antes_da_hora(ambiente):
    comum.salvar_fila([post(atras_min=-30)])
    api = ApiFalsa()
    publicar.executar(api)
    assert not api.publicados and comum.carregar_fila()[0]["status"] == "agendado"


def test_um_post_por_execucao_mais_antigo_primeiro(ambiente):
    comum.salvar_fila([post(1, 5), post(2, 60)])
    publicar.executar(ApiFalsa())
    st = {p["id"]: p["status"] for p in comum.carregar_fila()}
    assert st == {1: "agendado", 2: "publicado"}


def test_limite_diario(ambiente):
    feitos = [dict(post(i), status="publicado", publicado_em=comum.agora().isoformat()) for i in range(1, 6)]
    comum.salvar_fila(feitos + [post(6)])
    api = ApiFalsa()
    publicar.executar(api)
    assert not api.publicados


def test_erro_antes_de_publicar_tenta_de_novo_e_para(ambiente):
    comum.salvar_fila([post()])
    for esperado in ("agendado", "agendado", "erro"):
        assert publicar.executar(ApiFalsa(falha_item=True)) == 1
        assert comum.carregar_fila()[0]["status"] == esperado


def test_falha_ao_publicar_nunca_repete(ambiente):
    comum.salvar_fila([post()])
    assert publicar.executar(ApiFalsa(falha_pub=True)) == 1
    assert comum.carregar_fila()[0]["status"] == "verificar"
    api = ApiFalsa()
    publicar.executar(api)
    assert not api.publicados


def test_interrompido_vira_verificar(ambiente):
    comum.salvar_fila([post(status="publicando")])
    api = ApiFalsa()
    publicar.executar(api)
    assert comum.carregar_fila()[0]["status"] == "verificar" and not api.publicados


def test_conta_errada_nao_publica(ambiente):
    comum.salvar_fila([post()])
    api = ApiFalsa(conta="outra")
    assert publicar.executar(api) == 1
    assert not api.publicados


def test_varios_espacos_viram_linha_em_branco(ambiente):
    wb = Workbook(); wb.active.append(["Primeira parte      Segunda parte"])
    p = ambiente / "c.xlsx"; wb.save(p)
    frase = importar.ler_excel(p)[0]["frase"]
    assert frase == "Primeira parte\n\nSegunda parte"
    linhas, _, _ = arte.diagramar(frase)
    assert "" in linhas


def test_publica_reel_com_video(ambiente):
    comum.salvar_fila([dict(post(), tipo="reels", video="0001.mp4")])
    api = ApiFalsa()
    assert publicar.executar(api) == 0
    assert api.urls == ["https://site.exemplo/slides/0001.mp4"]
    assert api.publicados == ["reel"] and comum.carregar_fila()[0]["status"] == "publicado"


def test_tres_reels_e_dois_posts_por_dia(ambiente):
    novos, _, _ = importar.importar([{"frase": f"Frase {i}", "legenda": ""} for i in range(15)], simular=True)
    por_dia = {}
    for p in novos:
        por_dia.setdefault(p["quando"][:10], []).append(p["tipo"])
    cheios = [v for v in por_dia.values() if len(v) == 5]
    assert cheios and all(v.count("reels") == 3 and v.count("post") == 2 for v in cheios)
