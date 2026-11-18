"""Busca promoções de um produto em lojas conhecidas dentro de uma faixa de preço.

Uso rápido:
    python promocoes.py                                   (modo perguntas)
    python promocoes.py "fone bluetooth" --min 100 --max 300
    python promocoes.py "air fryer" --max 500 --lojas amazon,magalu,casas bahia
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from promo import buscape, kabum
from promo.exportar import salvar_tudo
from promo.modelo import Oferta, loja_conhecida, normalizar, preco_br, relevante
from promo.rede import Cliente, FonteIndisponivel

FONTES = {"buscape": buscape, "kabum": kabum}
PASTA_PADRAO = Path(__file__).resolve().parent / "resultados"


def _moeda(v: float | None) -> str:
    if v is None:
        return "-"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _perguntar_valor(texto: str) -> float | None:
    while True:
        r = input(texto).strip()
        if not r:
            return None
        v = preco_br(r)
        if v is not None:
            return v
        print("  Valor inválido. Exemplo: 150 ou 1.299,90 (ou Enter para não limitar)")


def modo_interativo() -> argparse.Namespace:
    print("=== Busca de Promoções ===")
    produto = ""
    while not produto:
        produto = input("Qual produto você quer? ").strip()
    pmin = _perguntar_valor("Preço mínimo (R$, Enter = sem mínimo): ")
    pmax = _perguntar_valor("Preço máximo (R$, Enter = sem máximo): ")
    lojas = input("Só algumas lojas? (ex: amazon, magalu — Enter = todas as conhecidas): ").strip()
    return argparse.Namespace(produto=produto, min=pmin, max=pmax, lojas=lojas, todas_lojas=False,
                              paginas=2, detalhar=15, incluir_acessorios=False, ordenar="preco",
                              limite=150, formatos="xlsx,html", saida=str(PASTA_PADRAO), abrir=True)


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Busca promoções em lojas conhecidas (Amazon, Magalu, Casas Bahia, Americanas, KaBuM! ...)")
    p.add_argument("produto", nargs="?", help='produto a buscar, ex: "iphone 15 128gb"')
    p.add_argument("--min", type=float, help="preço mínimo em R$")
    p.add_argument("--max", type=float, help="preço máximo em R$")
    p.add_argument("--lojas", default="", help='só estas lojas, separadas por vírgula (ex: "amazon,magalu,casas bahia")')
    p.add_argument("--todas-lojas", action="store_true", help="inclui também lojas pouco conhecidas")
    p.add_argument("--paginas", type=int, default=2, help="páginas de resultados do Buscapé (padrão 2)")
    p.add_argument("--detalhar", type=int, default=15, help="quantos produtos comparar loja a loja (padrão 15)")
    p.add_argument("--incluir-acessorios", action="store_true", help="não descarta capas, películas, cabos etc.")
    p.add_argument("--ordenar", choices=["preco", "desconto"], default="preco")
    p.add_argument("--limite", type=int, default=150, help="máximo de ofertas no arquivo (padrão 150)")
    p.add_argument("--formatos", default="xlsx,html", help="xlsx, html e/ou csv (padrão xlsx,html)")
    p.add_argument("--saida", default=str(PASTA_PADRAO), help="pasta dos arquivos gerados")
    p.add_argument("--abrir", action="store_true", help="abre a página HTML ao terminar")
    a = p.parse_args()
    if not a.produto:
        return modo_interativo()
    return a


def _filtro_lojas(texto: str) -> set[str]:
    return {loja_conhecida(x) or normalizar(x) for x in texto.split(",") if x.strip()}


def buscar(a: argparse.Namespace, log=print) -> tuple[list[Oferta], dict]:
    if a.min is not None and a.max is not None and a.min > a.max:
        a.min, a.max = a.max, a.min
    cliente = Cliente()
    filtro = (lambda t: True) if a.incluir_acessorios else (lambda t: relevante(t, a.produto))
    print(f"\nBuscando \"{a.produto}\" entre {_moeda(a.min) if a.min else 'R$ 0'} e {_moeda(a.max) if a.max else 'sem limite'}...")

    falhas: list[str] = []

    def rodar(nome):
        try:
            return FONTES[nome].buscar(cliente, a.produto, a.min, a.max, paginas=a.paginas,
                                       detalhar=a.detalhar, filtro=filtro, log=log)
        except FonteIndisponivel as e:
            falhas.append(f"{nome}: {e}")
        except Exception as e:  # uma fonte com problema não derruba as outras
            falhas.append(f"{nome}: erro inesperado ({e.__class__.__name__}: {e})")
        return []

    with ThreadPoolExecutor(max_workers=len(FONTES)) as ex:
        brutas = [o for lista in ex.map(rodar, FONTES) for o in lista]

    lojas_escolhidas = _filtro_lojas(a.lojas)
    vistas: dict[tuple, Oferta] = {}
    for o in brutas:
        if (a.min is not None and o.preco < a.min) or (a.max is not None and o.preco > a.max):
            continue
        if not a.incluir_acessorios and not relevante(o.produto, a.produto):
            continue
        conhecida = loja_conhecida(o.loja)
        if not a.todas_lojas and not conhecida:
            continue
        if lojas_escolhidas and (conhecida or normalizar(o.loja)) not in lojas_escolhidas:
            continue
        chave = (normalizar(o.produto)[:70], normalizar(o.loja))
        if chave not in vistas or o.preco < vistas[chave].preco:
            vistas[chave] = o

    ofertas = list(vistas.values())
    if a.ordenar == "desconto":
        ofertas.sort(key=lambda o: (-(o.desconto_pct or 0), o.preco))
    else:
        ofertas.sort(key=lambda o: o.preco)
    ofertas = ofertas[: a.limite]

    info = {
        "Produto buscado": a.produto,
        "Faixa de preço": f"{_moeda(a.min) if a.min else 'R$ 0'} a {_moeda(a.max) if a.max else 'sem limite'}",
        "Data da busca": f"{datetime.now():%d/%m/%Y %H:%M}",
        "Ofertas encontradas": str(len(ofertas)),
        "Lojas": sorted({o.loja for o in ofertas}),
        "Fontes com problema": falhas,
    }
    return ofertas, info


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = argumentos()
    ofertas, info = buscar(a)

    for f in info["Fontes com problema"]:
        print(f"  Aviso: {f}")
    if not ofertas:
        print("\nNenhuma oferta encontrada nessa faixa de preço. Tente ampliar a faixa ou simplificar o nome do produto.")
        return 1

    print(f"\n{len(ofertas)} ofertas em {len(info['Lojas'])} lojas. As 10 mais baratas:\n")
    for o in ofertas[:10]:
        extra = f"  ({o.desconto_pct:g}% abaixo)" if o.desconto_pct else ""
        print(f"  {_moeda(o.preco):>13}  {o.loja[:18]:<18}  {o.produto[:70]}{extra}")

    formatos = {f.strip().lower() for f in a.formatos.split(",")}
    arquivos = salvar_tudo(Path(a.saida), a.produto, ofertas, info, formatos)
    print("\nArquivos gerados:")
    for f in arquivos:
        print(f"  {f}")
    if a.abrir:
        html = next((f for f in arquivos if f.suffix == ".html"), None)
        if html and os.name == "nt":
            os.startfile(html)  # noqa: S606 - abre no navegador padrão
    return 0


if __name__ == "__main__":
    sys.exit(main())
