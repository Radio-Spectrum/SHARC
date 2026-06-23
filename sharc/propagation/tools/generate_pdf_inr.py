# -*- coding: utf-8 -*-
"""PDF report: I/N CCDF and protection distance for the FS ES (Campinas)."""
import os
import io
import json
import base64

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

A4 = (8.27, 11.69)


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _img(path):
    return plt.imread(io.BytesIO(base64.b64decode(json.load(open(path))["img"])), format="png")


def _text(fig, y, blocks):
    for kind, txt in blocks:
        if kind == "h2":
            y -= 0.010
            fig.text(0.08, y, txt, fontsize=11.5, fontweight="bold", va="top", color="#16a085")
            fig.lines.append(plt.Line2D([0.08, 0.92], [y - 0.008, y - 0.008],
                             transform=fig.transFigure, color="#dce3ea", lw=1))
            y -= 0.026
        else:
            t = fig.text(0.08, y, txt, fontsize=9.4, va="top", wrap=True)
            t._get_wrap_line_width = lambda: 560
            y -= 0.019 * (1 + len(txt) // 92) + 0.012
    return y


def main():
    out = _out()
    ccdf = _img(os.path.join(out, "ccdf_inr_b64.json"))
    sweep = _img(os.path.join(out, "protection_distance_b64.json"))
    sw = json.load(open(os.path.join(out, "protection_distance.json")))
    prot = sw["protection_distance_km"]
    pdf_path = os.path.join(out, "Relatorio_Analise_IN_FS_ES.pdf")

    rows = "  ".join(f"{int(d)}km:{p:.1f}%" for d, p in
                     zip(sw["distances_km"], sw["exceed_pct"]))

    with PdfPages(pdf_path) as pdf:
        # Page 1 - CCDF
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "Analise de I/N - estacao terrena FS (Campinas)",
                 fontsize=14, fontweight="bold", va="top")
        _text(fig, 0.935, [
            ("h2", "1. CCDF do I/N (ES a 5 km do centro IMT)"),
            ("body", "Distribuicao complementar P(I/N > abscissa) das 500 amostras, eixo y em "
                     "log10 de porcentagem. Cenario: 8 GHz, P.1812 com terreno e clutter "
                     "estatisticos (Campinas), p=1% do tempo, 50% das localizacoes."),
        ])
        axi = fig.add_axes([0.06, 0.30, 0.88, 0.50]); axi.axis("off"); axi.imshow(ccdf)
        _text(fig, 0.27, [
            ("body", "Criterio de protecao: I/N nao deve exceder -10 dB em mais de 20% dos "
                     "eventos. Resultado (apos corrigir o bug de off-axis da antena da ES): "
                     "I/N > -10 dB em 100% -> CRITERIO VIOLADO a 5 km (mediana do I/N = "
                     "+41,8 dB; minimo +19,1 dB)."),
        ])
        pdf.savefig(fig); plt.close(fig)

        # Page 2 - protection distance
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "2. Distancia de protecao", fontsize=14, fontweight="bold", va="top")
        _text(fig, 0.935, [
            ("body", "Varredura da distancia da ES ao centro do cluster IMT (300 snapshots por "
                     "ponto); para cada distancia mede-se P(I/N > -10 dB). A distancia de "
                     "protecao e onde essa excedencia cai ao criterio de 20%."),
        ])
        axi = fig.add_axes([0.06, 0.34, 0.88, 0.48]); axi.axis("off"); axi.imshow(sweep)
        _text(fig, 0.30, [
            ("body", f"Excedencia por distancia: {rows}."),
            ("body", f"Distancia de protecao (I/N > -10 dB em <= 20% dos eventos): "
                     f"aproximadamente {prot:.0f} km. Abaixo dela o criterio e violado; "
                     f"acima, atendido. Note o efeito do bug: com o off-axis errado a "
                     f"distancia era ~11 km; corrigido, sobe para ~{prot:.0f} km (a ES de 36 dBi "
                     f"apontada ao cluster ve as BS proximas ao centro com ganho de feixe "
                     f"principal). Cenario de pior caso (boresight da ES sobre a IMT)."),
        ])
        pdf.savefig(fig); plt.close(fig)

        d = pdf.infodict()
        d["Title"] = "Analise de I/N e Distancia de Protecao - FS ES Campinas"
        d["Author"] = "SHARC / jbraga"

    print(pdf_path)


if __name__ == "__main__":
    main()
