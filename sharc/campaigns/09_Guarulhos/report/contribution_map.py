"""
Mapa deterministico de contribuicao por BS para a interferencia no RA (envelope superior).

Aviao parado em (0, 0, h); BS a 20 m em (x, y). Setor com azimute apontado para o
aviao, feixe varrido na faixa de steering vertical e tomado o pior caso, arranjo
8x8 com subarranjo (parametros do YAML de referencia de cada banda), downtilt 6 graus,
P.528 mediano (p = 50%), padrao fora de banda do RA (0 dBi no hemisferio inferior),
perda de polarizacao 3 dB e filtro do RA. Por simetria o resultado depende so da
distancia horizontal d e da altitude h.

Saida: contrib.json com, por banda e altitude:
  - perfil radial c(d) em dBm/MHz por BS (todos os K feixes alinhados = potencia conduzida)
  - decomposicao (P.528, ganho do arranjo)
  - fracao acumulada da interferencia agregada (densidade uniforme) dentro do raio R
  - reducao do agregado (dB) ao remover um disco de raio R ou um corredor de meia-largura L
    ao longo do eixo de aproximacao (aviao sobre o eixo)
  - agregado do envelope para 10 BS/km2 (para comparar com o Monte Carlo)
"""
import os, json, math
import numpy as np
from sharc.parameters.parameters import Parameters
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt
from sharc.propagation.propagation_p528 import PropagationP528

H = os.path.dirname(os.path.abspath(__file__))
INPUT = r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\input"
YAML = {"3.65": "input_air_approach_array_8_8000m_h20_dt6.yaml", "6.475": "6G_input_air_approach_array_8_8000m_h20_dt6.yaml"}
RA_FILTER = {"3.65": -4.85, "6.475": -13.4}
ALTS_M = [round(math.tan(math.radians(3.0)) * s, 2) for s in [1000, 1500, 2000, 3000, 4000, 6000, 8000, 12000, 16000, 24000, 32000]]   # 11 pontos da rampa
STEER_THETA = np.linspace(90.0, 100.0, 11)          # faixa vertical de steering (graus, 90 = horizonte)
D_KM = np.concatenate([np.arange(0.05, 2.0, 0.05), np.arange(2.0, 45.01, 0.25)])   # rede limitada a 45 km de raio
GRID_KM, GRID_STEP = 45.0, 0.15                     # grade 2D para disco/corredor
FT = 3.28084


def load(band):
    p = Parameters(); p.set_file_name(os.path.join(INPUT, YAML[band])); p.read_params()
    return p


def bs_gain_toward_aircraft(p, d_km, h_ac_m):
    """Ganho (dBi) do arranjo da BS na direcao do aviao, setor apontado para ele, pior steering."""
    par = p.imt.bs.antenna.array.get_antenna_parameters()
    h_bs = p.imt.bs.height
    d_m = d_km * 1e3
    dz = h_ac_m - h_bs
    dist = np.hypot(d_m, dz)
    theta_ac = np.degrees(np.arccos(dz / dist))       # do eixo z; aviao acima -> < 90
    phi_ac = np.zeros_like(d_m)                       # setor apontado para o aviao
    ant = AntennaBeamformingImt(par, 0.0, -par.downtilt)   # azimute 0 = direcao do aviao
    for th in STEER_THETA:
        ant.add_beam(0.0, float(th))
    gains = np.full((len(STEER_THETA), d_m.size), np.nan)
    for k in range(len(STEER_THETA)):
        gains[k] = ant.calculate_gain(phi_vec=phi_ac, theta_vec=theta_ac, beams_l=np.full(d_m.size, k))
    return gains.max(axis=0), gains, theta_ac, dist


def p528_loss(p, d_km, h_ac_m, band, dist_3d_m):
    """P.528 mediano. Alem do horizonte-radio (d > dML) o kernel do repositorio tem um termo de
    troposcatter que devolve perda negativa (bug conhecido, sem efeito na campanha porque nenhuma
    BS simulada fica alem do horizonte). Aqui, para d > dML, usa-se espaco livre + difracao de
    Terra lisa (reta de difracao do proprio P.528), que e o ramo fisicamente dominante nessa regiao."""
    from sharc.propagation import propagation_p528 as P
    prop = PropagationP528(np.random.RandomState(1))
    f = float(p.imt.frequency)
    n = d_km.size
    L = prop.get_loss(dist_3d_m.reshape(n, 1), np.full((n, 1), f), np.full((n, 1), h_ac_m / 1e3),
                      np.full((n, 1), p.imt.bs.height / 1e3), np.zeros((n, 1), dtype=bool), 1,
                      np.full((n, 1), 50.0)).ravel()
    fa = np.array([f]); hb = np.array([p.imt.bs.height / 1e3]); ha = np.array([h_ac_m / 1e3])
    dr1, _, _, _, Aa1, r1 = prop._terminal_params(np.minimum(hb, ha), fa)
    dr2, _, _, _, Aa2, r2 = prop._terminal_params(np.maximum(hb, ha), fa)
    dML = float(dr1 + dr2)
    d3 = dML + 0.5 * (P.AEFF_KM ** 2 / fa) ** (1 / 3); d4 = dML + 1.5 * (P.AEFF_KM ** 2 / fa) ** (1 / 3)
    Ad3 = prop._smooth_earth_diffraction(fa, d3, dr1, dr2, 1); Ad4 = prop._smooth_earth_diffraction(fa, d4, dr1, dr2, 1)
    Md = float((Ad4 - Ad3) / (d4 - d3)); Ad0 = float(Ad4 - Md * d4)
    beyond = d_km > dML
    if beyond.any():
        dk = d_km[beyond]
        r_fsl = float(r1 + r2) + 2.0 * (dk - dML)
        L[beyond] = P._fspl_dB(f, np.maximum(r_fsl, dk)) + float(Aa1 + Aa2) + np.maximum(Md * dk + Ad0, 0.0)
    return L, dML


def radial_profile(p, band, h_ac_m):
    g_max, g_all, theta_ac, dist = bs_gain_toward_aircraft(p, D_KM, h_ac_m)
    L, dML = p528_loss(p, D_KM, h_ac_m, band, dist)
    ptx_mhz = p.imt.bs.conducted_power - 10 * math.log10(p.imt.bandwidth)   # todos os feixes alinhados
    pol = p.single_space_station.polarization_loss
    c = ptx_mhz + g_max + 0.0 - L - pol + RA_FILTER[band]                   # RA: 0 dBi abaixo do horizonte
    return dict(d_km=D_KM.tolist(), c_dbm_mhz=np.round(c, 2).tolist(), loss_db=np.round(L, 2).tolist(),
                gain_bs_dbi=np.round(g_max, 2).tolist(), theta_deg=np.round(theta_ac, 2).tolist(),
                ptx_dbm_mhz=round(ptx_mhz, 2), pol_loss_db=pol, filter_db=RA_FILTER[band], dml_km=round(dML, 1))


def cumulative_and_zones(profile, rho_bs_km2=10.0):
    d = np.array(profile["d_km"]); c_lin = 10 ** (np.array(profile["c_dbm_mhz"]) / 10)
    # agregado continuo com densidade uniforme (envelope): I = rho * int c(d) 2 pi d dd
    ring = 2 * np.pi * d * np.gradient(d)
    agg_lin = rho_bs_km2 * np.sum(c_lin * ring)
    cum = np.cumsum(c_lin * ring) / np.sum(c_lin * ring)
    # grade 2D para disco e corredor (aviao na origem, eixo de aproximacao = eixo x)
    ax = np.arange(-GRID_KM, GRID_KM + 1e-9, GRID_STEP)
    X, Y = np.meshgrid(ax, ax)
    Dg = np.hypot(X, Y)
    Cg = 10 ** (np.interp(Dg, d, np.array(profile["c_dbm_mhz"]), left=profile["c_dbm_mhz"][0], right=-500) / 10)
    total = Cg.sum()
    radii = [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20]
    red_disc = [round(-10 * math.log10(max(1e-12, 1 - Cg[Dg <= r].sum() / total)), 2) for r in radii]
    half_widths = [0.25, 0.5, 1, 2, 3, 5, 7.5, 10]
    red_corr = [round(-10 * math.log10(max(1e-12, 1 - Cg[np.abs(Y) <= w].sum() / total)), 2) for w in half_widths]
    return dict(agg_dbm_mhz_rho10=round(10 * math.log10(agg_lin), 2), cum_fraction=np.round(cum, 4).tolist(),
                radii_km=radii, reduction_disc_db=red_disc, half_widths_km=half_widths, reduction_corridor_db=red_corr)


def grid_geometry(p):
    """Sitios macro (7 clusters x 19) da topologia hotspot, pista e linha de aproximacao (km, referencial da simulacao)."""
    from sharc.topology.topology_macrocell import TopologyMacrocell
    isd = p.imt.topology.hotspot.intersite_distance
    macro = TopologyMacrocell(isd, p.imt.topology.hotspot.num_clusters)
    macro.calculate_coordinates()
    pts = np.unique(np.round(np.column_stack([macro.x, macro.y]) / 1e3, 4), axis=0)
    approach_s_km = [1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32]
    return dict(isd_km=isd / 1e3, sites_km=pts.tolist(), runway_center_km=[-2.0, 10.0], runway_length_km=3.0,
                approach_axis_y_km=10.0, approach_sign=-1, approach_s_km=approach_s_km,
                aircraft_xy_km={str(h): [-2.0 - h / math.tan(math.radians(3.0)) / 1e3, 10.0] for h in ALTS_M})


def main():
    out = {"meta": dict(alts_m=ALTS_M, alts_ft=[round(a * FT) for a in ALTS_M], steer_theta=STEER_THETA.tolist(),
                        p528_time_pct=50, ra_gain_dbi=0.0, note="setor apontado para o aviao, pior steering, todos os feixes alinhados, carga 1, rede de raio 45 km", net_radius_km=45.0),
           "bands": {}}
    for band in YAML:
        p = load(band)
        if "grid" not in out:
            out["grid"] = grid_geometry(p)
            print(f"grade: {len(out['grid']['sites_km'])} sitios, ISD {out['grid']['isd_km']:.3f} km")
        out["bands"][band] = {"conducted_power_dbm": p.imt.bs.conducted_power, "downtilt": p.imt.bs.antenna.array.downtilt,
                              "bs_height_m": p.imt.bs.height, "alts": {}}
        for h in ALTS_M:
            prof = radial_profile(p, band, h)
            prof.update(cumulative_and_zones(prof))
            out["bands"][band]["alts"][str(h)] = prof
            i_pk = int(np.argmax(prof["c_dbm_mhz"]))
            print(f"{band} GHz  h={h*FT:5.0f} ft | pico {prof['c_dbm_mhz'][i_pk]:6.1f} dBm/MHz a {prof['d_km'][i_pk]:5.2f} km | "
                  f"embaixo {prof['c_dbm_mhz'][0]:6.1f} | 10 km {np.interp(10, prof['d_km'], prof['c_dbm_mhz']):6.1f} | "
                  f"agregado envelope rho=10: {prof['agg_dbm_mhz_rho10']:6.1f} dBm/MHz | 50% da energia dentro de "
                  f"{np.interp(0.5, prof['cum_fraction'], prof['d_km']):4.1f} km, 90% em {np.interp(0.9, prof['cum_fraction'], prof['d_km']):4.1f} km | "
                  f"corredor +-2 km: -{prof['reduction_corridor_db'][3]} dB | disco 5 km: -{prof['reduction_disc_db'][4]} dB")
    with open(os.path.join(H, "contrib.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print("-> contrib.json", round(os.path.getsize(os.path.join(H, "contrib.json")) / 1e3), "kB")


if __name__ == "__main__":
    main()
