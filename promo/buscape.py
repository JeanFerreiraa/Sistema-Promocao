"""Fonte Buscapé: comparador que reúne ofertas de Amazon, Magazine Luiza, Casas Bahia,
Americanas, Extra, Fast Shop, KaBuM! e muitas outras lojas, com histórico de preço."""
from __future__ import annotations

import json
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import quote

from bs4 import BeautifulSoup

from .modelo import Oferta, nome_loja, preco_br
from .rede import Cliente, FonteIndisponivel

BASE = "https://www.buscape.com.br"
NOME = "Buscapé"


def _url_busca(consulta: str, pmin: float | None, pmax: float | None, pagina: int) -> str:
    url = f"{BASE}/search?q={quote(consulta)}&sortBy=price_asc"
    if pmin is not None or pmax is not None:
        url += "&refinements%5B0%5D%5Bid%5D=price"
        if pmin is not None:
            url += f"&refinements%5B0%5D%5Branges%5D%5Bmin%5D={pmin:g}"
        if pmax is not None:
            url += f"&refinements%5B0%5D%5Branges%5D%5Bmax%5D={pmax:g}"
    if pagina > 1:
        url += f"&page={pagina}"
    return url


def _ler_cards(html: str) -> list[dict]:
    sopa = BeautifulSoup(html, "html.parser")
    cards = []
    for a in sopa.select('a[data-testid="product-card::card"]'):
        nome = a.select_one('[data-testid="product-card::name"]')
        preco = a.select_one('[data-testid="product-card::price"]')
        if not nome or not preco:
            continue
        loja = a.select_one('[class*="BestOfferMerchant"]')
        tags = [t.get_text(" ", strip=True) for t in a.select('[data-testid="orq-badge"]')]
        cashback = a.select_one('[data-testid="product-card::cashback"]')
        img = a.select_one("img")
        cards.append({
            "caminho": a["href"].split("?")[0],
            "nome": nome.get_text(" ", strip=True),
            "preco": preco_br(preco.get_text()),
            "loja": loja.get_text(" ", strip=True) if loja else "",
            "selos": [t for t in tags if t] + ([cashback.get_text(" ", strip=True)] if cashback else []),
            "imagem": (img.get("src") or "") if img else "",
        })
    return [c for c in cards if c["preco"]]


def _estado(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    return json.loads(m.group(1)).get("props", {}).get("initialReduxState", {})


def _oferta_do_card(card: dict) -> Oferta:
    return Oferta(
        produto=card["nome"], loja=nome_loja(card["loja"]), preco=card["preco"],
        link=BASE + card["caminho"], fonte=NOME, imagem=card["imagem"], selos=list(card["selos"]),
    )


def _ofertas_do_produto(cliente: Cliente, card: dict) -> list[Oferta]:
    """Abre a página do produto e devolve a oferta de cada loja + histórico de preço."""
    estado = _estado(cliente.html(BASE + card["caminho"]))
    lista = (estado.get("offers") or {}).get("offerList") or []
    if not lista:
        return [_oferta_do_card(card)]

    produto = ((estado.get("products") or {}).get("product") or {}).get("product") or {}
    media = menor = None
    historico = ((estado.get("priceHistory") or {}).get("priceHistory") or {})
    dias = [d["price"] for h in historico.values() for d in (h.get("days") or []) if d.get("price")]
    if len(dias) >= 7:
        media, menor = round(statistics.mean(dias), 2), round(min(dias), 2)

    ofertas = []
    for o in lista:
        if not o.get("price"):
            continue
        selos = []
        if o.get("sellerIsMarketplace"):
            selos.append("Vendedor parceiro (marketplace)")
        if o.get("loweringPercentage"):
            selos.append(f"Preço caiu {o['loweringPercentage']:g}%")
        if o.get("numParcels") and o.get("parcelValue"):
            selos.append(f"{o['numParcels']}x de R$ {o['parcelValue']:.2f}".replace(".", ","))
        ofertas.append(Oferta(
            produto=produto.get("name") or card["nome"],
            loja=nome_loja(o.get("sellerName", "")),
            preco=round(float(o["price"]), 2),
            link=f"{BASE}/lead?oid={o['id']}&channel=1",
            fonte=NOME,
            media_40d=media,
            menor_40d=menor,
            imagem=o.get("imageUrl") or card["imagem"],
            selos=selos + [s for s in card["selos"] if "Oferta do dia" in s],
        ))
    return ofertas


def buscar(
    cliente: Cliente,
    consulta: str,
    pmin: float | None,
    pmax: float | None,
    *,
    paginas: int = 2,
    detalhar: int = 15,
    filtro: Callable[[str], bool] = lambda _t: True,
    log: Callable[[str], None] = print,
) -> list[Oferta]:
    cards: dict[str, dict] = {}
    for pagina in range(1, paginas + 1):
        try:
            novos = _ler_cards(cliente.html(_url_busca(consulta, pmin, pmax, pagina)))
        except FonteIndisponivel:
            if pagina == 1:
                raise
            break
        if not novos:
            break
        for c in novos:
            cards.setdefault(c["caminho"], c)
    escolhidos = sorted((c for c in cards.values() if filtro(c["nome"])), key=lambda c: c["preco"])
    log(f"  Buscapé: {len(cards)} produtos encontrados, {len(escolhidos)} relevantes")

    a_detalhar, resto = escolhidos[:detalhar], escolhidos[detalhar:]
    ofertas: list[Oferta] = [_oferta_do_card(c) for c in resto]

    def detalhe(card: dict) -> list[Oferta]:
        try:
            return _ofertas_do_produto(cliente, card)
        except Exception:  # página do produto falhou: usa o que veio na busca
            return [_oferta_do_card(card)]

    if a_detalhar:
        log(f"  Buscapé: comparando lojas em {len(a_detalhar)} produtos...")
        with ThreadPoolExecutor(max_workers=3) as ex:
            for lista in ex.map(detalhe, a_detalhar):
                ofertas.extend(lista)
    return ofertas
