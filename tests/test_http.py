"""Exercita o cliente real da API contra um servidor HTTP local."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

import publicar
import renovar_token


class Falso(BaseHTTPRequestHandler):
    log = []
    responder_erro = False

    def _r(self, codigo, corpo):
        b = json.dumps(corpo).encode()
        self.send_response(codigo); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        Falso.log.append(("GET", self.path, self.headers.get("Authorization"), {}))
        u = urlparse(self.path)
        if u.path.endswith("refresh_access_token"):
            if Falso.responder_erro:
                return self._r(400, {"error": {"message": "expirado"}})
            return self._r(200, {"access_token": "novo", "token_type": "bearer", "expires_in": 5184000})
        if u.path.endswith("/17841458850803002"):
            return self._r(200, {"id": "99", "username": "JuvenalCanalha"})
        return self._r(200, {"status_code": "FINISHED"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        corpo = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}
        Falso.log.append(("POST", self.path, self.headers.get("Authorization"), corpo))
        if Falso.responder_erro:
            return self._r(400, {"error": {"code": 9, "message": "limite"}})
        return self._r(200, {"id": f"id{len(Falso.log)}"})


@pytest.fixture
def servidor(monkeypatch):
    Falso.log = []; Falso.responder_erro = False
    s = HTTPServer(("127.0.0.1", 0), Falso)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}"
    monkeypatch.setattr(publicar, "API", f"{base}/v25.0")
    monkeypatch.setattr(renovar_token, "URL", f"{base}/refresh_access_token")
    yield base
    s.shutdown()


def test_fluxo_de_carrossel_real(servidor):
    api = publicar.Api("segredo")
    assert api.conta()["id"] == "99"
    a = api.item("99", "https://s/1.jpg"); b = api.item("99", "https://s/2.jpg")
    api.aguardar(a)
    c = api.carrossel("99", [a, b], "minha legenda")
    mid = api.publicar("99", c)
    assert mid
    posts = [l for l in Falso.log if l[0] == "POST"]
    assert posts[0][3] == {"image_url": "https://s/1.jpg", "is_carousel_item": "true"}
    assert posts[2][3] == {"media_type": "CAROUSEL", "children": f"{a},{b}", "caption": "minha legenda"}
    assert posts[3][3] == {"creation_id": c}
    assert posts[3][1] == "/v25.0/99/media_publish"
    assert all(l[2] == "Bearer segredo" and "segredo" not in l[1] for l in Falso.log)


def test_erro_nao_vaza_token(servidor):
    Falso.responder_erro = True
    with pytest.raises(publicar.ErroApi) as e:
        publicar.Api("segredo").item("99", "u")
    assert "limite" in str(e.value) and "segredo" not in str(e.value)


def test_renovacao(servidor):
    assert renovar_token.renovar("antigo") == ("novo", 5184000)
    q = parse_qs(urlparse(Falso.log[0][1]).query)
    assert q == {"grant_type": ["ig_refresh_token"], "access_token": ["antigo"]}


def test_renovacao_falha_sem_vazar(servidor):
    Falso.responder_erro = True
    with pytest.raises(RuntimeError) as e:
        renovar_token.renovar("antigo")
    assert "expirado" in str(e.value) and "antigo" not in str(e.value)
