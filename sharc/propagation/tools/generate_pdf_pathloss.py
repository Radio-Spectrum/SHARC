# -*- coding: utf-8 -*-
"""PDF report of the PL50 propagation-model comparison (LoS and obstructed paths)."""
import os
import io
import json
import base64

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

A4 = (8.27, 11.69)
LABELS = [
    ("fspl", "Espaco livre (FSPL)"),
    ("hata", "Okumura-Hata / COST-231 (extrap. 6 GHz)"),
    ("p452", "ITU-R P.452 (smooth earth)"),
    ("p452_clut", "ITU-R P.452 + clutter P.2108"),
    ("p1812_flat", "ITU-R P.1812 (smooth earth)"),
    ("p1812_srtm", "ITU-R P.1812 (terreno especifico SRTM)"),
    ("p1812_stat", "ITU-R P.1812 (terreno estatistico)"),
    ("p1812_statc", "ITU-R P.1812 (terreno estat. + clutter)"),
]


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _img(path):
    return plt.imread(io.BytesIO(base64.b64decode(json.load(open(path))["img"])), format="png")


def _blocks(fig, y, blocks):
    for kind, txt in blocks:
        if kind == "h2":
            y -= 0.010
            fig.text(0.08, y, txt, fontsize=11.5, fontweight="bold", va="top", color="#16a085")
            fig.lines.append(plt.Line2D([0.08, 0.92], [y - 0.008, y - 0.008],
                             transform=fig.transFigure, color="#dce3ea", lw=1))
            y -= 0.028
        elif kind == "mono":
            n = txt.count("\n") + 1
            fig.text(0.10, y, txt, fontsize=8.3, va="top", family="monospace",
                     bbox=dict(boxstyle="round", fc="#f3f5f7", ec="#dce3ea"))
            y -= 0.019 * n + 0.024
        else:
            t = fig.text(0.08, y, txt, fontsize=9.3, va="top", wrap=True)
            t._get_wrap_line_width = lambda: 560
            y -= 0.019 * (1 + len(txt) // 92) + 0.012
    return y


def main():
    out = _out()
    los = np.load(os.path.join(out, "path_loss_comparison.npz"))
    obs = np.load(os.path.join(out, "path_loss_comparison_obstruido.npz"))
    los_img = _img(os.path.join(out, "path_loss_comparison_b64.json"))
    obs_img = _img(os.path.join(out, "path_loss_comparison_obstruido_b64.json"))
    pdf_path = os.path.join(out, "Relatorio_Comparacao_Modelos_PL50.pdf")

    rows = [[lbl, f"{los[k][-1]:.1f}", f"{obs[k][-1]:.1f}"] for k, lbl in LABELS]

    with PdfPages(pdf_path) as pdf:
        # Page 1 - scenario, method, table
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "Comparacao de modelos de propagacao - PL50 (Campinas-SP)",
                 fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.935, [
            ("h2", "Cenario"),
            ("mono", "Tx: 20 m, 6 GHz, isotropica, EIRP 30 dBm\n"
                     "Rx: 10 m, isotropica\n"
                     "Tx = (-22.931034, -47.096705)\n"
                     "PL50: p = 50% do tempo; estatistico = mediana sobre realizacoes"),
            ("h2", "Modelos comparados"),
            ("body", "Espaco livre; Okumura-Hata/COST-231 (extrapolado a 6 GHz, fora da "
                     "validade 1,5-2 GHz); ITU-R P.452 (smooth earth) e P.452 + clutter P.2108; "
                     "ITU-R P.1812 com terreno smooth, terreno especifico (SRTM), terreno "
                     "estatistico (ajuste a 1 km) e terreno estatistico + clutter dependente da "
                     "distancia (Tx no centro, Rx afastando-se)."),
            ("h2", "PL50 no Rx (dois percursos)"),
        ])
        ax = fig.add_axes([0.08, 0.40, 0.84, 0.30]); ax.axis("off")
        tb = ax.table(cellText=rows,
                      colLabels=["Modelo", "LoS 6,53 km (dB)", "Obstruido 10 km (dB)"],
                      loc="center", cellLoc="center")
        tb.auto_set_font_size(False); tb.set_fontsize(8.4); tb.scale(1, 1.5)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor("#dce3ea")
            if r == 0:
                cell.set_facecolor("#eef2f5"); cell.set_text_props(fontweight="bold")
        _blocks(fig, 0.36, [
            ("h2", "Leitura"),
            ("body", "P.452+P.2108 e o clutter estatistico das duas pontas (perda sempre "
                     "positiva, ~+30 dB). O terreno especifico (SRTM) reflete o caminho real: "
                     "no percurso LoS coincide com o espaco livre (~124 dB); no obstruido sobe a "
                     "180 dB (colina de +94 m). O terreno estatistico entrega o valor tipico "
                     "regional (~157-163 dB), independente do azimute - adequado a Monte Carlo."),
        ])
        pdf.savefig(fig); plt.close(fig)

        # Page 2 - LoS
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "Percurso 1 - Linha de visada (Rx a 6,53 km)",
                 fontsize=13.5, fontweight="bold", va="top")
        axi = fig.add_axes([0.06, 0.42, 0.88, 0.48]); axi.axis("off"); axi.imshow(los_img)
        _blocks(fig, 0.38, [
            ("body", "Terreno desce de 677 para 625 m (folga +10 m): LoS. Por isso P.1812 "
                     "smooth = SRTM = espaco livre ~124 dB. O terreno estatistico (~157 dB) e o "
                     "P.452+P.2108 (~159 dB) ficam acima por representarem ambiente "
                     "urbano/ondulado tipico. Note que o terreno estatistico + clutter (height-"
                     "gain nos terminais altos) pode reduzir levemente a perda vs so terreno, "
                     "pois eleva o terminal ao topo do clutter."),
        ])
        pdf.savefig(fig); plt.close(fig)

        # Page 3 - obstructed
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "Percurso 2 - Obstruido (Rx a 10 km, az 100, colina +94 m)",
                 fontsize=13.5, fontweight="bold", va="top")
        axi = fig.add_axes([0.06, 0.42, 0.88, 0.48]); axi.axis("off"); axi.imshow(obs_img)
        _blocks(fig, 0.38, [
            ("body", "Uma colina sobe +94 m acima do raio direto. Agora o terreno especifico "
                     "(SRTM) = 180 dB supera ate o estatistico (163 dB): este caminho e pior que "
                     "a mediana regional. Os modelos smooth (FSPL/P.452/P.1812) ignoram o relevo "
                     "(~128 dB). Conclusao: o especifico cruza o estatistico em sentidos opostos "
                     "conforme o percurso real, enquanto o estatistico da sempre o valor tipico."),
        ])
        pdf.savefig(fig); plt.close(fig)

        d = pdf.infodict()
        d["Title"] = "Comparacao de Modelos de Propagacao PL50 - Campinas-SP"
        d["Author"] = "SHARC / jbraga"

    print(pdf_path)


if __name__ == "__main__":
    main()
