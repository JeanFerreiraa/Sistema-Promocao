# Sistema de Promoções

Busca ofertas de um produto em lojas conhecidas, dentro da faixa de preço que você escolher, e gera um arquivo com a lista.

## Instalação (uma vez)

```powershell
pip install -r requirements.txt
```

## Como usar

**Modo perguntas:** dê dois cliques em `buscar.bat` (ou rode `python promocoes.py`). Ele pergunta o produto, o preço mínimo e o máximo e, se quiser, quais lojas.

**Linha de comando:**

```powershell
python promocoes.py "fone bluetooth" --min 100 --max 300
python promocoes.py "air fryer" --max 600 --lojas "amazon,magalu,casas bahia"
python promocoes.py "iphone 15 128gb" --min 3000 --max 5000 --ordenar desconto --abrir
```

| Opção | O que faz |
|---|---|
| `--min` / `--max` | faixa de preço em R$ |
| `--lojas` | só essas lojas (ex.: `amazon,magalu,americanas,casas bahia,kabum`) |
| `--todas-lojas` | inclui também lojas pouco conhecidas / vendedores pequenos |
| `--ordenar desconto` | ordena pelo maior desconto em vez do menor preço |
| `--paginas N` | quantas páginas de resultados ler (padrão 2) |
| `--detalhar N` | em quantos produtos comparar o preço loja a loja (padrão 15) |
| `--incluir-acessorios` | não descarta capas, películas, cabos etc. |
| `--formatos xlsx,html,csv` | arquivos a gerar (padrão `xlsx,html`) |
| `--abrir` | abre a página com os resultados no navegador |

## Resultado

Os arquivos ficam em `resultados/`, com o nome do produto e a data:

- **.xlsx (Excel)**: uma linha por oferta com produto, loja, preço, preço antigo, desconto, média e menor preço recentes, destaques e link clicável. A aba *Resumo* mostra o melhor preço de cada loja. Linhas em verde são as melhores promoções (10% ou mais de desconto, ou o menor preço dos últimos ~40 dias).
- **.html**: página com fotos, filtro por loja, busca por nome e ordenação.
- **.csv**: opcional, para importar em outros programas.

## De onde vêm os dados

- **Buscapé**: comparador que reúne ofertas de Amazon, Magazine Luiza, Casas Bahia, Americanas, Extra, Ponto, Fast Shop, KaBuM!, Carrefour e outras. Para cada produto o sistema lê a oferta de cada loja e o histórico de preço (~40 dias). Com isso ele mostra se o preço atual está mesmo abaixo do normal.
- **KaBuM!**: página pública de busca da loja, com preço antigo, preço à vista e campanhas.

O link "Abrir oferta" passa pelo Buscapé e cai na página do produto na loja.

O sistema faz poucas requisições, com pausa entre elas, como um navegador comum. Ele **não** tenta driblar bloqueios anti-robô. Se uma fonte recusar o acesso, ela é pulada e o aviso aparece na tela e na aba *Resumo*.

## Limitações

- Os preços mudam o tempo todo. Confira na loja antes de comprar (frete, cupom e vendedor).
- O "desconto" usa o preço antigo informado pela loja ou, se não houver, a média recente do Buscapé.
- Mercado Livre, e o acesso direto a Amazon, Magalu e Casas Bahia, bloqueiam programas. As ofertas dessas lojas vêm pelo Buscapé.
- Se um site mudar o layout, a fonte correspondente pode parar de funcionar até ser ajustada (`promo/buscape.py`, `promo/kabum.py`).
