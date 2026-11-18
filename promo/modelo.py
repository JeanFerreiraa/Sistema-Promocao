"""Modelo de dados (Oferta) e funções utilitárias compartilhadas pelas fontes."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Oferta:
    produto: str
    loja: str
    preco: float
    link: str
    fonte: str
    preco_antigo: float | None = None      # preço "de" informado pela loja
    media_40d: float | None = None         # média de preço nos últimos dias (histórico Buscapé)
    menor_40d: float | None = None         # menor preço nos últimos dias (histórico Buscapé)
    imagem: str = ""
    selos: list[str] = field(default_factory=list)

    @property
    def desconto_pct(self) -> float | None:
        """Desconto em % sobre o preço antigo da loja ou, na falta dele, sobre a média recente."""
        ref = self.preco_antigo if self.preco_antigo and self.preco_antigo > self.preco else self.media_40d
        if not ref or ref <= self.preco:
            return None
        return round((1 - self.preco / ref) * 100, 1)

    @property
    def menor_preco_recente(self) -> bool:
        return bool(self.menor_40d) and self.preco <= self.menor_40d * 1.005


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos."""
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def preco_br(texto: str) -> float | None:
    """Converte 'R$ 1.714,18' em 1714.18."""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?", (texto or "").replace("\xa0", " "))
    if not m:
        return None
    inteiro = m.group(1).replace(".", "")
    return float(f"{inteiro}.{m.group(2) or '0'}")


# ---------------------------------------------------------------------------
# Lojas conhecidas: nome normalizado (como aparece nas fontes) -> nome exibido
# ---------------------------------------------------------------------------
LOJAS_CONHECIDAS = {
    "amazon": "Amazon",
    "americanas": "Americanas",
    "casas bahia": "Casas Bahia",
    "magazine luiza": "Magazine Luiza",
    "magalu": "Magazine Luiza",
    "extra": "Extra",
    "ponto": "Ponto (Ponto Frio)",
    "pontofrio": "Ponto (Ponto Frio)",
    "ponto frio": "Ponto (Ponto Frio)",
    "kabum!": "KaBuM!",
    "kabum": "KaBuM!",
    "fast shop": "Fast Shop",
    "carrefour": "Carrefour",
    "submarino": "Submarino",
    "shoptime": "Shoptime",
    "mercado livre": "Mercado Livre",
    "webcontinental": "Webcontinental",
    "girafa": "Girafa",
    "samsung": "Samsung",
    "apple": "Apple",
    "dell": "Dell",
    "lenovo": "Lenovo",
    "motorola": "Motorola",
    "lg": "LG",
    "electrolux": "Electrolux",
    "brastemp": "Brastemp",
    "consul": "Consul",
    "leroy merlin": "Leroy Merlin",
    "centauro": "Centauro",
    "netshoes": "Netshoes",
    "nike": "Nike",
    "adidas": "Adidas",
    "zattini": "Zattini",
    "renner": "Renner",
    "riachuelo": "Riachuelo",
    "c&a": "C&A",
    "drogasil": "Drogasil",
    "droga raia": "Droga Raia",
    "pague menos": "Pague Menos",
    "sephora": "Sephora",
    "o boticario": "O Boticário",
    "natura": "Natura",
    "beleza na web": "Beleza na Web",
    "epoca cosmeticos": "Época Cosméticos",
    "madeiramadeira": "MadeiraMadeira",
    "mobly": "Mobly",
    "tok&stok": "Tok&Stok",
    "camicado": "Camicado",
    "havan": "Havan",
    "pichau": "Pichau",
    "terabyteshop": "Terabyte",
    "terabyte": "Terabyte",
    "nagem": "Nagem",
    "colombo": "Colombo",
    "lojas colombo": "Colombo",
    "polishop": "Polishop",
    "multilaser": "Multilaser",
    "positivo": "Positivo",
    "atacadao": "Atacadão",
    "assai": "Assaí",
    "ri happy": "Ri Happy",
    "petz": "Petz",
    "cobasi": "Cobasi",
    "decathlon": "Decathlon",
    "livraria leitura": "Leitura",
    "saraiva": "Saraiva",
    "estante virtual": "Estante Virtual",
    "worten": "Worten",
    "efacil": "eFácil",
    "gazin": "Gazin",
    "lojas cem": "Lojas Cem",
    "angeloni": "Angeloni",
    "angeloni.": "Angeloni",
}


def loja_conhecida(nome: str) -> str | None:
    """Retorna o nome padronizado da loja se for uma loja conhecida, senão None."""
    n = normalizar(nome).removeprefix("via ").strip()
    if n in LOJAS_CONHECIDAS:
        return LOJAS_CONHECIDAS[n]
    # tolera variações como "Amazon.com.br", "Magazine Luiza - Marketplace"
    for chave, exibido in LOJAS_CONHECIDAS.items():
        if len(chave) >= 4 and re.match(rf"{re.escape(chave)}\b", n):
            return exibido
    return None


def nome_loja(nome: str) -> str:
    return loja_conhecida(nome) or (nome or "").removeprefix("Via ").strip()


# ---------------------------------------------------------------------------
# Relevância: evita que "iphone 15" traga capinhas e películas
# ---------------------------------------------------------------------------
ACESSORIOS = {
    "capa", "capinha", "case", "pelicula", "protetor", "suporte", "adesivo", "skin",
    "bolsa", "estojo", "cabo", "carregador", "adaptador", "refil", "compativel", "pulseira",
    "para",
}
PALAVRAS_IGNORADAS = {"de", "da", "do", "das", "dos", "e", "com", "sem", "para", "o", "a", "em"}


def _palavras(texto: str) -> list[str]:
    # junta "128 GB" -> "128gb" para comparar modelos/capacidades
    t = re.sub(r"(\d)\s+([a-z])", r"\1\2", normalizar(texto))
    return re.findall(r"[\w+]+", t)


def relevante(titulo: str, consulta: str, incluir_acessorios: bool = False) -> bool:
    """O título contém todos os termos da busca e não é um acessório do produto."""
    palavras = _palavras(titulo)
    conjunto = set(palavras)
    termos_consulta = _palavras(consulta)
    for w in termos_consulta:
        if w in PALAVRAS_IGNORADAS:
            continue
        if any(ch.isdigit() for ch in w):  # "15", "128gb": tem que bater exatamente
            if w not in conjunto:
                return False
        elif not any(p.startswith(w) or (len(p) >= 4 and w.startswith(p)) for p in conjunto):
            return False
    if not incluir_acessorios:
        # "Capa para iPhone 15", "Película ..." -> acessório no começo do título
        if any(p in ACESSORIOS and p not in termos_consulta for p in palavras[:3]):
            return False
    return True
