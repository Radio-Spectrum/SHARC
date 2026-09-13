"""Monta margens_ra_guarulhos.html: template.html + results.json (aggregate.py) + Plotly embutido.

O Plotly (pacote cartesian, ~1.6 MB) fica dentro do HTML para a pagina abrir sem CDN, inclusive
em visualizadores que bloqueiam scripts externos (celular, painel lateral). Se o arquivo
plotly-cartesian.min.js nao existir na pasta, e baixado do cdnjs uma vez.
"""
import os
import urllib.request

H = os.path.dirname(os.path.abspath(__file__))
PLOTLY_VERSION = "2.35.0"
PLOTLY_FILE = os.path.join(H, "plotly-cartesian.min.js")
PLOTLY_URL = f"https://cdnjs.cloudflare.com/ajax/libs/plotly.js/{PLOTLY_VERSION}/plotly-cartesian.min.js"

if not os.path.exists(PLOTLY_FILE):
    print("baixando", PLOTLY_URL)
    urllib.request.urlretrieve(PLOTLY_URL, PLOTLY_FILE)

tpl = open(os.path.join(H, "template.html"), encoding="utf-8").read()
data = open(os.path.join(H, "results.json"), encoding="utf-8").read()
contrib = open(os.path.join(H, "contrib.json"), encoding="utf-8").read()   # contribution_map.py
plotly = open(PLOTLY_FILE, encoding="utf-8").read()
# o bundle contem U+FFFD literal em strings/regex; troca pelo escape JS equivalente
# (o publicador de artifacts rejeita o caractere literal)
plotly = plotly.replace(chr(0xFFFD), chr(92) + "ufffd")   # U+FFFD literal -> escape JS �
assert "</script" not in plotly.lower()
out = os.path.join(H, "margens_ra_guarulhos.html")
open(out, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", data).replace("/*__CONTRIB__*/", contrib).replace("/*__PLOTLY__*/", plotly))
print("ok ->", out, round(os.path.getsize(out) / 1e6, 1), "MB")
