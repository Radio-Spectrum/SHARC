"""Monta report/margens_ra_guarulhos.html a partir de template.html + results.json (gerado por aggregate.py)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(H, "template.html"), encoding="utf-8").read()
data = open(os.path.join(H, "results.json"), encoding="utf-8").read()
out = os.path.join(H, "margens_ra_guarulhos.html")
open(out, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", data))
print("ok ->", out, round(os.path.getsize(out) / 1e6, 1), "MB")
