# -*- coding: utf-8 -*-
"""Build the PDF report of the statistical terrain & clutter models (matplotlib only).

Covers the method, the terrain sampling-step choice (1 km) and the estimated
parameters, plus the cross-comparison with 5D/1059, the P.1812 loss validation
and the distance-dependent clutter model.
"""
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


def _img_b64(path):
    return plt.imread(io.BytesIO(base64.b64decode(json.load(open(path))["img"])), format="png")


def _table(fig, rect, col_labels, rows, fs=8.5):
    ax = fig.add_axes(rect); ax.axis("off")
    tb = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="center")
    tb.auto_set_font_size(False); tb.set_fontsize(fs); tb.scale(1, 1.35)
    for (r, c), cell in tb.get_celld().items():
        cell.set_edgecolor("#dce3ea")
        if r == 0:
            cell.set_facecolor("#eef2f5"); cell.set_text_props(fontweight="bold")
    return ax


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
            fig.text(0.10, y, txt, fontsize=8.2, va="top", family="monospace",
                     bbox=dict(boxstyle="round", fc="#f3f5f7", ec="#dce3ea"))
            y -= 0.019 * n + 0.024
        else:
            t = fig.text(0.08, y, txt, fontsize=9.3, va="top", wrap=True)
            t._get_wrap_line_width = lambda: 560
            y -= 0.019 * (1 + len(txt) // 92) + 0.012
    return y


def main():
    out = _out()
    val = json.load(open(os.path.join(out, "validation_results.json")))
    cmp_img = _img_b64(os.path.join(out, "compare_terrain_b64.json"))
    pdfs_img = plt.imread(os.path.join(out, "clutter_pdfs.png"))
    fit_img = _img_b64(os.path.join(out, "clutter_landuse_b64.json"))
    pdf_path = os.path.join(out, "Relatorio_Modelo_Estatistico_Terreno_Clutter.pdf")

    with PdfPages(pdf_path) as pdf:
        # ---- Page 1: title + terrain model + parameters ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "Modelo estatistico de terreno e clutter para a ITU-R P.1812",
                 fontsize=14.5, fontweight="bold", va="top")
        fig.text(0.08, 0.94, "Calibracao com dados reais (SRTM e ESA WorldCover) - regiao de Campinas-SP",
                 fontsize=9.5, va="top", color="#5b6b7a")
        _blocks(fig, 0.90, [
            ("body", "Em simulacoes de Monte Carlo as BS/UE sao genericas, entao um terreno "
                     "path-specific nao e representativo. Seguindo a contribuicao ITU-R WP5D "
                     "5D/1059, gera-se um perfil de terreno SINTETICO por snapshot a partir de "
                     "distribuicoes ajustadas, e a altura de clutter e sorteada de um modelo "
                     "dependente da distancia. Dados reais sao usados apenas off-line; a "
                     "simulacao usa os parametros ajustados."),
            ("h2", "1. Modelo estatistico de terreno"),
            ("body", "Por snapshot, o perfil e sintetizado de duas distribuicoes: o desvio de "
                     "altura dos extremos (pico/vale) em relacao a linha media local segue uma "
                     "Student-t (locacao 0); a distancia entre extremos consecutivos segue uma "
                     "lognormal. O perfil e suavizado em ~1,6 km (escala de correlacao) para "
                     "emular a redondez do relevo real."),
            ("mono", "altura:   t( mu=0, sigma, nu )\n"
                     "distancia: Lognormal( mu, sigma )  [km]\n"
                     "perfil sintetizado -> suavizacao 1,6 km -> P.1812 (difracao)"),
            ("h2", "Parametros estimados (Campinas-SP, amostragem de terreno = 1 km)"),
            ("mono", "Altura (Student-t):   sigma = 39,04 m   nu = 4,197\n"
                     "Distancia (lognormal): mu = 0,4268   sigma = 0,5237\n"
                     "  -> moda 1,17 km | mediana 1,53 km | media 1,76 km\n"
                     "Suavizacao do perfil:  1,6 km"),
        ])
        pdf.savefig(fig); plt.close(fig)

        # ---- Page 2: sampling choice + comparison figure ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "2. Escolha da amostragem do terreno", fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.93, [
            ("body", "O passo de amostragem do perfil controla a escala dos extremos detectados. "
                     "A 100 m, ondulacoes sub-quilometricas (quase ruido do SRTM) sao contadas "
                     "como extremos, subestimando o espacamento. A 1 km, os extremos passam a ser "
                     "feicoes de relevo, alinhando-se a metodologia do 5D/1059 (segmentos de 10 km). "
                     "Adotou-se 1 km como padrao."),
        ])
        _table(fig, [0.08, 0.66, 0.84, 0.17],
               ["Passo", "Altura sigma (m)", "Altura nu", "Distancia moda/mediana/media (km)"],
               [["100 m", "36,27", "2,93", "0,31 / 0,52 / 0,68"],
                ["500 m", "35,88", "3,15", "0,66 / 0,94 / 1,12"],
                ["1000 m (adotado)", "39,04", "4,20", "1,16 / 1,53 / 1,76"],
                ["5D/1059 (fronteiras)", "24,25", "1,52", "1,43 / 2,89 / 4,11"]])
        axi = fig.add_axes([0.05, 0.07, 0.90, 0.50]); axi.axis("off"); axi.imshow(cmp_img)
        fig.text(0.5, 0.06, "PDFs ajustadas (deles vs Campinas) e histogramas de Campinas.",
                 fontsize=8, ha="center", color="#5b6b7a")
        pdf.savefig(fig); plt.close(fig)

        # ---- Page 3: terrain validation ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "3. Validacao do terreno estatistico", fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.93, [
            ("body", "Perda basica P.1812 a 3,5 GHz (hTx=30 m, hRx=1,5 m, sem clutter) comparando "
                     "terreno plano, 1000 realizacoes do terreno estatistico e os 20 perfis reais "
                     "de Campinas (SRTM, amostrados a 100 m = difracao verdadeira). A mediana do "
                     "modelo fica dentro de +-4 dB da mediana real em 10-50 km, com faixas p5-p95 "
                     "sobrepostas: o modelo estatistico reproduz a distribuicao de perdas reais."),
        ])
        _table(fig, [0.08, 0.55, 0.84, 0.22],
               ["Dist (km)", "Plano (dB)", "Real p50", "Estat. p50", "Vies",
                "Real p5-p95", "Estat. p5-p95"],
               [[f"{r['dist_km']:.0f}", f"{r['flat']:.1f}", f"{r['real']['p50']:.1f}",
                 f"{r['stat']['p50']:.1f}", f"{r['stat']['p50']-r['real']['p50']:+.1f}",
                 f"{r['real']['p5']:.0f}-{r['real']['p95']:.0f}",
                 f"{r['stat']['p5']:.0f}-{r['stat']['p95']:.0f}"] for r in val], fs=8)
        pdf.savefig(fig); plt.close(fig)

        # ---- Page 4: clutter model + PDFs ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "4. Modelo de clutter dependente da distancia", fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.93, [
            ("body", "A altura representativa de clutter R(m) a uma distancia d(km) do centro do "
                     "cluster IMT e uma tendencia deterministica vezes um espalhamento lognormal:"),
            ("mono", "f(d)     = C + (A - C) * exp(-d / d0)\n"
                     "mu_ln(d) = ln f(d) - sigma^2/2     (alvo = media)\n"
                     "R(d)     = exp( N( mu_ln(d), sigma ) )   [m]"),
            ("h2", "Parametros (ajuste a MEDIA, uso do solo real, R^2 = 0,98)"),
            ("mono", "A=22,68 m  C=7,90 m  d0=5,97 km  sigma=1,238  target=mean"),
        ])
        axi = fig.add_axes([0.06, 0.30, 0.88, 0.34]); axi.axis("off"); axi.imshow(pdfs_img)
        fig.text(0.5, 0.29, "PDFs de clutter a 300 m / 3 km / 30 km (media vermelho, mediana azul).",
                 fontsize=8, ha="center", color="#5b6b7a")
        _table(fig, [0.20, 0.10, 0.60, 0.14],
               ["Distancia", "Media (m)", "Mediana (m)"],
               [["300 m", "21,96", "10,20"], ["3 km", "16,84", "7,83"], ["30 km", "8,00", "3,72"]])
        pdf.savefig(fig); plt.close(fig)

        # ---- Page 5: clutter estimation (land use) ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "5. Estimacao do clutter por uso do solo real", fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.93, [
            ("body", "Fonte: ESA WorldCover v200 (2021), 10 m, tile S24W048. Os 20 radiais de 50 km "
                     "sao amostrados; cada classe e mapeada para uma altura representativa; a media "
                     "por faixa de 5 km e ajustada por f(d)=C+(A-C)exp(-d/d0). O centro e 78% "
                     "Built-up, decaindo para arvore/campo/agricola no anel rural."),
        ])
        _table(fig, [0.30, 0.62, 0.40, 0.20],
               ["Classe", "Altura (m)"],
               [["Tree cover", "15"], ["Built-up", "20"], ["Grassland", "1"],
                ["Cropland", "2"], ["Shrubland", "3"], ["Water/Bare", "0"]], fs=8.5)
        axi = fig.add_axes([0.07, 0.10, 0.86, 0.46]); axi.axis("off"); axi.imshow(fit_img)
        fig.text(0.5, 0.09, "Clutter por uso do solo real vs. distancia (ajuste exp. com piso).",
                 fontsize=8, ha="center", color="#5b6b7a")
        pdf.savefig(fig); plt.close(fig)

        # ---- Page 6: reproduction + usage + limitations ----
        fig = plt.figure(figsize=A4)
        fig.text(0.08, 0.965, "6. Reproducao, uso e limitacoes", fontsize=14, fontweight="bold", va="top")
        _blocks(fig, 0.93, [
            ("h2", "Comandos de reproducao"),
            ("mono", "python -m sharc.propagation.tools.estimate_terrain_params_campinas\n"
                     "python -m sharc.propagation.tools.estimate_clutter_landuse_campinas\n"
                     "python -m sharc.propagation.tools.compare_terrain_models\n"
                     "python -m sharc.propagation.tools.validate_statistical_terrain"),
            ("h2", "Configuracao (YAML)"),
            ("mono", "param_p1812:\n"
                     "  terrain_profile: statistical\n"
                     "  stat_height_sigma_m: 39.04\n  stat_height_nu: 4.197\n"
                     "  stat_dist_mu: 0.4268\n  stat_dist_sigma: 0.5237\n"
                     "  stat_smoothing_km: 1.6\n"
                     "  clutter_mode: terrain\n  clutter_statistical: true\n"
                     "  stat_clutter_trend_A: 22.68\n  stat_clutter_trend_C: 7.90\n"
                     "  stat_clutter_trend_d0_km: 5.97\n  stat_clutter_sigma: 1.238"),
            ("h2", "Limitacoes"),
            ("body", "(i) O espacamento dos extremos depende do passo de amostragem; usou-se 1 km "
                     "para comparabilidade com o 5D/1059. (ii) No nucleo urbano o clutter real e "
                     "assimetrico a esquerda (mediana > media); o lognormal reproduz a MEDIA, mas "
                     "a mediana central fica subestimada. Fidelidade total exigiria mistura por classe."),
        ])
        pdf.savefig(fig); plt.close(fig)

        d = pdf.infodict()
        d["Title"] = "Modelo Estatistico de Terreno e Clutter P.1812 - Campinas-SP"
        d["Author"] = "SHARC / jbraga"

    print(pdf_path)


if __name__ == "__main__":
    main()
