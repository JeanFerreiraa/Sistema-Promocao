"""Acesso HTTP simples e educado: um navegador comum, poucas requisições, pausa entre elas.

O sistema NÃO tenta driblar bloqueios anti-robô. Se uma loja recusar o acesso,
ela é apenas pulada e o motivo aparece no relatório.
"""
from __future__ import annotations

import threading
import time

import requests

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
}

PAUSA_MINIMA = 0.6  # segundos entre requisições ao mesmo site


class FonteIndisponivel(Exception):
    pass


class Cliente:
    def __init__(self, timeout: int = 25):
        self.sessao = requests.Session()
        self.sessao.headers.update(CABECALHOS)
        self.timeout = timeout
        self._ultimo: dict[str, float] = {}
        self._trava = threading.Lock()

    def _esperar_vez(self, host: str) -> None:
        with self._trava:
            agora = time.monotonic()
            proximo = max(agora, self._ultimo.get(host, 0) + PAUSA_MINIMA)
            self._ultimo[host] = proximo
        if proximo > agora:
            time.sleep(proximo - agora)

    def html(self, url: str) -> str:
        host = url.split("/")[2]
        ultimo_erro = ""
        for tentativa in range(2):
            self._esperar_vez(host)
            try:
                r = self.sessao.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                ultimo_erro = f"falha de conexão ({e.__class__.__name__})"
                continue
            if r.status_code == 200:
                return r.content.decode("utf-8", errors="replace")
            if r.status_code in (403, 429):
                raise FonteIndisponivel(f"{host} recusou o acesso (HTTP {r.status_code})")
            ultimo_erro = f"HTTP {r.status_code}"
            time.sleep(1.5 * (tentativa + 1))
        raise FonteIndisponivel(f"{host}: {ultimo_erro}")
