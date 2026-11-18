"""Gera os arquivos com a lista de promoções: Excel (.xlsx), página HTML e CSV."""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .modelo import Oferta

COLUNAS = ["Produto", "Loja", "Preço (R$)", "Preço antigo (R$)", "Desconto %",
           "Média recente (R$)", "Menor recente (R$)", "Destaques", "Link", "Fonte"]


def _linha(o: Oferta) -> list:
    destaques = list(o.selos)
    if o.menor_preco_recente:
        destaques.insert(0, "Menor preço dos últimos ~40 dias")
    return [o.produto, o.loja, o.preco, o.preco_antigo, o.desconto_pct,
            o.media_40d, o.menor_40d, " | ".join(destaques), o.link, o.fonte]


def salvar_xlsx(caminho: Path, ofertas: list[Oferta], info: dict) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Promoções"
    ws.append(COLUNAS)
    for o in ofertas:
        ws.append(_linha(o))

    cab = PatternFill("solid", fgColor="1F4E78")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = cab
        c.alignment = Alignment(vertical="center")
    larguras = [70, 22, 13, 16, 12, 18, 18, 55, 18, 10]
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    destaque = PatternFill("solid", fgColor="E2F0D9")
    for r in range(2, ws.max_row + 1):
        for col in (3, 4, 6, 7):
            ws.cell(r, col).number_format = 'R$ #,##0.00'
        ws.cell(r, 5).number_format = '0.0"%"'
        link = ws.cell(r, 9)
        if link.value:
            link.hyperlink = link.value
            link.value = "Abrir oferta"
            link.font = Font(color="0563C1", underline="single")
        if (ws.cell(r, 5).value or 0) >= 10 or "Menor preço" in (ws.cell(r, 8).value or ""):
            for col in range(1, 9):
                ws.cell(r, col).fill = destaque
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    rs = wb.create_sheet("Resumo")
    rs.column_dimensions["A"].width = 28
    rs.column_dimensions["B"].width = 70
    for chave, valor in info.items():
        rs.append([chave, valor if not isinstance(valor, list) else "; ".join(valor) or "-"])
    rs.append([])
    rs.append(["Melhor preço por loja", ""])
    rs.cell(rs.max_row, 1).font = Font(bold=True)
    melhores: dict[str, Oferta] = {}
    for o in ofertas:
        if o.loja not in melhores or o.preco < melhores[o.loja].preco:
            melhores[o.loja] = o
    for loja, o in sorted(melhores.items(), key=lambda kv: kv[1].preco):
        rs.append([loja, f"R$ {o.preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" — {o.produto}"])
    for linha in rs.iter_rows(max_col=1):
        if linha[0].value in info:
            linha[0].font = Font(bold=True)
    wb.save(caminho)


def salvar_csv(caminho: Path, ofertas: list[Oferta]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUNAS)
        for o in ofertas:
            linha = _linha(o)
            w.writerow([f"{v:.2f}".replace(".", ",") if isinstance(v, float) else ("" if v is None else v) for v in linha])


def salvar_html(caminho: Path, ofertas: list[Oferta], info: dict) -> None:
    dados = [{
        "produto": o.produto, "loja": o.loja, "preco": o.preco, "antigo": o.preco_antigo,
        "desconto": o.desconto_pct, "media": o.media_40d, "menor": o.menor_preco_recente,
        "link": o.link, "img": o.imagem, "selos": o.selos, "fonte": o.fonte,
    } for o in ofertas]
    titulo = f"Promoções: {info['Produto buscado']}"
    resumo = " · ".join(f"<b>{html.escape(k)}:</b> {html.escape(v if isinstance(v, str) else '; '.join(v) or '-')}"
                        for k, v in info.items() if k != "Produto buscado")
    pagina = MODELO_HTML.replace("{{TITULO}}", html.escape(titulo)) \
                        .replace("{{RESUMO}}", resumo) \
                        .replace("{{DADOS}}", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
    caminho.write_text(pagina, encoding="utf-8")


def salvar_tudo(pasta: Path, consulta: str, ofertas: list[Oferta], info: dict,
                formatos: set[str]) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    base = "".join(c if c.isalnum() else "_" for c in consulta.lower()).strip("_")[:40] or "busca"
    base = f"{base}_{datetime.now():%Y-%m-%d_%H%M}"
    gerados = []
    if "xlsx" in formatos:
        gerados.append(pasta / f"{base}.xlsx"); salvar_xlsx(gerados[-1], ofertas, info)
    if "html" in formatos:
        gerados.append(pasta / f"{base}.html"); salvar_html(gerados[-1], ofertas, info)
    if "csv" in formatos:
        gerados.append(pasta / f"{base}.csv"); salvar_csv(gerados[-1], ofertas)
    return gerados


MODELO_HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITULO}}</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--txt:#1d2433;--sub:#5b6476;--borda:#e3e6ec;--verde:#127a3c;--verde-bg:#e3f5ea;--azul:#1f5fbf;--laranja:#b45309;--laranja-bg:#fdf0e1}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--txt:#e7eaf0;--sub:#9aa3b2;--borda:#2b3240;--verde:#5fd08b;--verde-bg:#16301f;--azul:#7fb0ff;--laranja:#f3b46b;--laranja-bg:#33250f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:24px 16px 8px;max-width:1100px;margin:auto}h1{margin:0 0 6px;font-size:24px}
.resumo{color:var(--sub);font-size:13px}.resumo b{color:var(--txt);font-weight:600}
.barra{position:sticky;top:0;background:var(--bg);padding:10px 16px;max-width:1100px;margin:auto;display:flex;gap:8px;flex-wrap:wrap;z-index:2;border-bottom:1px solid var(--borda)}
select,input{font:inherit;padding:7px 10px;border:1px solid var(--borda);border-radius:8px;background:var(--card);color:var(--txt)}
input{flex:1;min-width:160px}main{max-width:1100px;margin:auto;padding:12px 16px 40px;display:grid;gap:10px}
.item{display:grid;grid-template-columns:72px 1fr auto;gap:14px;align-items:center;background:var(--card);border:1px solid var(--borda);border-radius:12px;padding:12px}
.item img{width:72px;height:72px;object-fit:contain;background:#fff;border-radius:8px}
.nome{font-weight:600;margin-bottom:4px}.loja{color:var(--sub);font-size:13px}
.selos{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.selo{font-size:11.5px;padding:2px 7px;border-radius:99px;background:var(--bg);color:var(--sub);border:1px solid var(--borda)}
.selo.bom{background:var(--verde-bg);color:var(--verde);border-color:transparent;font-weight:600}
.selo.desc{background:var(--laranja-bg);color:var(--laranja);border-color:transparent;font-weight:600}
.preco{text-align:right;white-space:nowrap}.preco .v{font-size:20px;font-weight:700}.preco s{color:var(--sub);font-size:12.5px;display:block}
.preco a{display:inline-block;margin-top:6px;padding:6px 12px;border-radius:8px;background:var(--azul);color:#fff;text-decoration:none;font-size:13px;font-weight:600}
.vazio{text-align:center;color:var(--sub);padding:40px}
@media (max-width:620px){.item{grid-template-columns:56px 1fr}.item img{width:56px;height:56px}.preco{grid-column:1/-1;text-align:left;display:flex;align-items:center;gap:12px}.preco s{display:inline}.preco a{margin:0 0 0 auto}}
</style></head><body>
<header><h1>{{TITULO}}</h1><div class="resumo">{{RESUMO}}</div></header>
<div class="barra">
 <input id="q" placeholder="Filtrar por nome…">
 <select id="loja"><option value="">Todas as lojas</option></select>
 <select id="ord"><option value="preco">Menor preço</option><option value="desconto">Maior desconto</option><option value="preco_desc">Maior preço</option></select>
</div>
<main id="lista"></main>
<script>
const D={{DADOS}};
const brl=v=>v==null?"":v.toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sel=document.getElementById("loja");
[...new Set(D.map(o=>o.loja))].sort().forEach(l=>sel.add(new Option(l,l)));
function render(){
  const q=document.getElementById("q").value.toLowerCase(),l=sel.value,ord=document.getElementById("ord").value;
  let r=D.filter(o=>(!l||o.loja===l)&&(!q||o.produto.toLowerCase().includes(q)));
  r.sort(ord==="desconto"?(a,b)=>(b.desconto||0)-(a.desconto||0)||a.preco-b.preco:ord==="preco_desc"?(a,b)=>b.preco-a.preco:(a,b)=>a.preco-b.preco);
  document.getElementById("lista").innerHTML=r.length?r.map(o=>{
    const selos=[];
    if(o.menor)selos.push('<span class="selo bom">Menor preço dos últimos ~40 dias</span>');
    if(o.desconto)selos.push(`<span class="selo desc">${o.desconto.toLocaleString("pt-BR")}% abaixo ${o.antigo?"do preço antigo":"da média recente"}</span>`);
    o.selos.forEach(s=>selos.push(`<span class="selo">${esc(s)}</span>`));
    return `<div class="item">${o.img?`<img loading="lazy" src="${esc(o.img)}" alt="">`:"<div></div>"}
      <div><div class="nome">${esc(o.produto)}</div><div class="loja">${esc(o.loja)} · via ${esc(o.fonte)}</div><div class="selos">${selos.join("")}</div></div>
      <div class="preco">${o.antigo?`<s>${brl(o.antigo)}</s>`:o.media?`<s>média ${brl(o.media)}</s>`:""}<span class="v">${brl(o.preco)}</span><br><a href="${esc(o.link)}" target="_blank" rel="noopener">Ver oferta</a></div></div>`}).join(""):'<div class="vazio">Nenhuma oferta com esses filtros.</div>';
}
["q","loja","ord"].forEach(id=>document.getElementById(id).addEventListener("input",render));render();
</script></body></html>"""
