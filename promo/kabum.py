"""Fonte KaBuM!: lê a página pública de busca da loja (preço atual, preço antigo, ofertas e cupons)."""
from __future__ import annotations

import json
import re
from typing import Callable
from urllib.parse import quote

from .modelo import Oferta, nome_loja, normalizar

BASE = "https://www.kabum.com.br"
NOME = "KaBuM!"


def _produtos(html: str) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    dados = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("data")
    if isinstance(dados, str):
        dados = json.loads(dados)
    return ((dados or {}).get("catalogServer") or {}).get("data") or []


def buscar(
    cliente,
    consulta: str,
    pmin: float | None,
    pmax: float | None,
    *,
    filtro: Callable[[str], bool] = lambda _t: True,
    log: Callable[[str], None] = print,
    **_ignorado,
) -> list[Oferta]:
    termo = "-".join(normalizar(consulta).split())
    produtos = _produtos(cliente.html(f"{BASE}/busca/{quote(termo)}"))
    ofertas = []
    for p in produtos:
        if not p.get("available") or not filtro(p.get("name", "")):
            continue
        campanha = p.get("offer") or {}
        preco = campanha.get("priceWithDiscount") or p.get("priceWithDiscount") or p.get("price")
        if not preco:
            continue
        preco = round(float(preco), 2)
        antigo = max(float(p.get("oldPrice") or 0), float(p.get("price") or 0))
        selos = ["Preço à vista (PIX)"]
        if campanha.get("name"):
            selos.append(f"Oferta: {campanha['name'].title()}")
        if (p.get("stamps") or {}).get("title"):
            selos.append(p["stamps"]["title"].title())
        flags = p.get("flags") or {}
        if flags.get("isFreeShipping"):
            selos.append("Frete grátis")
        if flags.get("isMarketplace"):
            selos.append("Vendedor parceiro (marketplace)")
        loja = "KaBuM!" if not flags.get("isMarketplace") else f"KaBuM! ({p.get('sellerName', 'parceiro')})"
        ofertas.append(Oferta(
            produto=p["name"],
            loja=nome_loja(loja) if not flags.get("isMarketplace") else loja,
            preco=preco,
            preco_antigo=round(antigo, 2) if antigo > preco else None,
            link=f"{BASE}/produto/{p['code']}/{p.get('friendlyName', '')}",
            fonte=NOME,
            imagem=p.get("thumbnail") or p.get("image") or "",
            selos=selos,
        ))
    log(f"  KaBuM!: {len(produtos)} produtos lidos, {len(ofertas)} relevantes")
    return ofertas
