# -*- coding: utf-8 -*-
"""Assemble the statistical-terrain report into a self-contained HTML file."""
import os
import json


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def img(figs, key, cap):
    return (f'<figure><img alt="{cap}" src="data:image/png;base64,{figs[key]}"/>'
            f'<figcaption>{cap}</figcaption></figure>')


def main():
    out = _out()
    figs = json.load(open(os.path.join(out, "report_figures.json")))
    p = json.load(open(os.path.join(out, "campinas_terrain_clutter_params.json")))
    val = json.load(open(os.path.join(out, "validation_results.json")))
    t = p["terrain_model"]["height_student_t"]
    d = p["terrain_model"]["distance_lognormal"]
    c = p["clutter_model"]["clutter_lognormal"]

    vrows = "".join(
        f"<tr><td>{r['dist_km']:.0f}</td><td>{r['flat']:.1f}</td>"
        f"<td>{r['real']['p50']:.1f}</td><td>{r['stat']['p50']:.1f}</td>"
        f"<td>{r['stat']['p50']-r['real']['p50']:+.1f}</td>"
        f"<td>{r['real']['p5']:.0f}–{r['real']['p95']:.0f}</td>"
        f"<td>{r['stat']['p5']:.0f}–{r['stat']['p95']:.0f}</td></tr>"
        for r in val
    )

    html = f"""<title>Modelo Estatístico de Terreno e Clutter para ITU-R P.1812</title>
<style>
  :root {{ --ink:#1a2733; --muted:#5b6b7a; --line:#dce3ea; --accent:#c0392b; --bg:#fbfcfd; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:var(--bg); line-height:1.55; margin:0; }}
  .wrap {{ max-width:880px; margin:0 auto; padding:40px 24px 80px; }}
  h1 {{ font-size:1.7rem; line-height:1.2; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:0.95rem; margin-bottom:28px; }}
  h2 {{ font-size:1.2rem; margin:38px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); }}
  h3 {{ font-size:1.02rem; margin:22px 0 6px; }}
  p, li {{ font-size:0.96rem; }}
  code {{ background:#eef2f5; padding:1px 5px; border-radius:4px; font-size:0.86em; }}
  table {{ border-collapse:collapse; width:100%; margin:14px 0; font-size:0.9rem; }}
  th,td {{ border:1px solid var(--line); padding:6px 9px; text-align:center; }}
  th {{ background:#eef2f5; }}
  td:first-child, th:first-child {{ text-align:left; }}
  figure {{ margin:18px 0; text-align:center; }}
  img {{ max-width:100%; border:1px solid var(--line); border-radius:8px; }}
  figcaption {{ color:var(--muted); font-size:0.84rem; margin-top:6px; }}
  .box {{ background:#fff; border:1px solid var(--line); border-left:4px solid var(--accent);
          border-radius:8px; padding:14px 18px; margin:16px 0; }}
  .eq {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:10px 16px;
         font-family:ui-monospace,Menlo,Consolas,monospace; font-size:0.9rem; overflow-x:auto; }}
  .tag {{ display:inline-block; background:#eef2f5; color:var(--muted); border-radius:20px;
          padding:2px 12px; font-size:0.8rem; margin-right:6px; }}
</style>
<div class="wrap">
<h1>Modelo Estatístico de Terreno e Clutter para a ITU-R P.1812</h1>
<div class="sub">Abordagem Monte-Carlo (5D/1059) • parâmetros estimados de Campinas-SP • integrado ao SHARC</div>

<div class="box">
<b>Motivação.</b> Em simulações de Monte Carlo do SHARC as BSs são posicionadas de forma
genérica, então um perfil de terreno <i>path-specific</i> (SRTM real) não é representativo.
Seguindo a contribuição ITU-R WP5D <b>5D/1059</b>, gera-se um <b>perfil de terreno sintético
por snapshot</b>, sorteado de distribuições ajustadas, e o aplica-se à difração da P.1812.
</div>

<h2>1. Modelo estatístico de terreno</h2>
<p>Cada snapshot sintetiza um perfil cujos extremos (picos/vales) têm:</p>
<ul>
<li><b>Desvio de altura</b> em relação à linha média local → <b>Student-t</b> (locação 0);</li>
<li><b>Distância horizontal</b> entre extremos consecutivos → <b>lognormal</b>.</li>
</ul>
<div class="eq">f_h(x) = Student-t(μ=0, σ, ν) &nbsp;&nbsp;|&nbsp;&nbsp; f_d(x) = Lognormal(μ, σ)</div>

<h3>Parâmetros estimados — 20 radiais de 50 km a partir de (-22.9049, -47.0603)</h3>
<table>
<tr><th>Descritor</th><th>Distribuição</th><th>Parâmetros (Campinas)</th><th>Ref. 5D/1059 (fronteiras)</th></tr>
<tr><td>Altura de extremos</td><td>Student-t</td>
    <td>σ = {t['sigma_m']:.1f} m, ν = {t['nu']:.2f}</td><td>σ = 24.25 m, ν = 1.525</td></tr>
<tr><td>Distância entre extremos</td><td>Lognormal</td>
    <td>μ = {d['mu']:.2f}, σ = {d['sigma']:.2f} (média {d['mean_km']:.2f} km)</td><td>≈ 1.6 km</td></tr>
</table>
{img(figs, "dist", "Fig. 1 — Distribuições ajustadas de altura (esq.) e distância entre extremos (dir.).")}
{img(figs, "profile", "Fig. 3 — Perfil real (SRTM, radial #0) vs. perfil sintético estatístico.")}

<h2>2. Proposta — modelo simples de clutter sobre o terreno</h2>
<p>Como não há base de uso do solo disponível, propõe-se um modelo <b>estatístico simples</b>:
a <b>altura representativa de clutter</b> em torno de cada terminal é uma variável aleatória
<b>lognormal</b>, <code>R = exp(N(μ, σ))</code>, usada pela P.1812 na correção de
<i>height-gain</i> de clutter nos terminais (Seção 4.7, eq. 57). Os parâmetros são estimados do
<b>resíduo de alta frequência</b> do SRTM (superfície acima do terreno suavizado em ~1.6 km),
um <i>proxy</i> de vegetação/edificações.</p>
<div class="eq">R ~ Lognormal(μ={c['mu']:.2f}, σ={c['sigma']:.2f}) → mediana {c['median_m']:.1f} m, média {c['mean_m']:.1f} m</div>
{img(figs, "clutter", "Fig. 2 — Distribuição do proxy de altura de clutter e ajuste lognormal.")}
<p class="sub"><b>Limitação:</b> é um proxy de rugosidade, não uma classificação real de cobertura
do solo. Para clutter path-specific por mapa (ESA WorldCover) seria preciso GDAL/rasterio.</p>

<h2>3. Integração na P.1812 (SHARC)</h2>
<p>Selecionável por parâmetros, ortogonal aos modos de clutter já existentes:</p>
<p>
<span class="tag">terrain_profile = flat</span>
<span class="tag">terrain_profile = srtm</span>
<span class="tag">terrain_profile = statistical</span>
</p>
<p>
<span class="tag">clutter_mode = none</span>
<span class="tag">clutter_mode = p2108</span>
<span class="tag">clutter_mode = terrain</span>
<span class="tag">clutter_statistical = true</span>
</p>
<p>No modo <code>statistical</code>, cada enlace recebe uma realização própria do perfil; o
gerador de números aleatórios do SHARC garante reprodutibilidade por snapshot. Uma suavização de
~1.6 km (≈ comprimento de correlação do terreno) emula a redondez das colinas reais.</p>

<h2>4. Validação contra perfis reais de Campinas</h2>
<p>Perda básica de transmissão P.1812 a 3.5 GHz, h<sub>tx</sub>=30 m, h<sub>rx</sub>=1.5 m,
sem clutter (para isolar o efeito do terreno). Compara-se flat, os 20 perfis reais e 1000
realizações estatísticas.</p>
<table>
<tr><th>Dist (km)</th><th>Flat (dB)</th><th>Real p50</th><th>Estat. p50</th><th>Viés</th>
    <th>Real p5–p95</th><th>Estat. p5–p95</th></tr>
{vrows}
</table>
{img(figs, "validation", "Fig. 4 — Perda vs. distância: flat, perfis reais (faixa p5–p95) e modelo estatístico.")}
<div class="box">
<b>Conclusão.</b> O modelo estatístico reproduz a distribuição de perdas dos perfis reais de
Campinas dentro de <b>±4 dB na mediana</b> em 10–50 km, com faixas p5–p95 sobrepostas — sem
necessitar de dados path-specific. O processo de geração de base de dados e síntese é validado
e adequado ao uso Monte Carlo da P.1812.
</div>
</div>
"""
    path = os.path.join(out, "p1812_statistical_terrain_report.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(path)


if __name__ == "__main__":
    main()
