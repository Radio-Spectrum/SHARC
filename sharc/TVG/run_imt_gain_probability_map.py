# -*- coding: utf-8 -*-

import numpy as np

from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from imt_gain_probability_map import generate_gain_ccdf_heatmap
from sharc.TVG.imt_gain_probability_map import (
    ImtGainProbabilityMap,
    BaseStationSet,
    VictimPoint,
)
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent

def build_bs_antenna_params() -> ParametersAntennaImt:
    p = ParametersAntennaImt()

    # -------- parâmetros que você passou --------
    p.normalization = False
    p.minimum_array_gain = -200
    p.adjacent_antenna_model = "BEAMFORMING"

    p.element_pattern = "M2101"
    p.element_max_g = 6.4
    p.element_phi_3db = 90
    p.element_theta_3db = 65
    p.element_am = 30
    p.element_sla_v = 30

    p.n_columns = 16
    p.n_rows = 8
    p.element_horiz_spacing = 0.5
    p.element_vert_spacing = 2.1
    p.multiplication_factor = 12
    p.downtilt = 6

    # subarray
    p.subarray.is_enabled = True
    p.subarray.n_rows = 3
    p.subarray.element_vert_spacing = 0.7
    p.subarray.eletrical_downtilt = 3.0

    return p


def main():
    # ------------------------------------------------------------------
    # Exemplo: substitua pelos BS reais do seu cenário SHARC
    # ------------------------------------------------------------------
    n_bs = 19
    rng = np.random.RandomState(42)

    bs_x = rng.uniform(-2000, 2000, n_bs)
    bs_y = rng.uniform(-2000, 2000, n_bs)
    bs_z = np.full(n_bs, 18.0)

    # azimutes de setor de exemplo
    bs_az = rng.choice([0.0, 120.0, 240.0], size=n_bs)
    bs_el = np.zeros(n_bs)

    bs_set = BaseStationSet(
        x_m=bs_x,
        y_m=bs_y,
        z_m=bs_z,
        azimuth_deg=bs_az,
        elevation_deg=bs_el,
        names=[f"BS_{i}" for i in range(n_bs)],
    )

    # vítima: exemplo
    victim = VictimPoint(
        x_m=3500.0,
        y_m=1000.0,
        z_m=30.0,
        name="Victim",
    )

    ant_param = build_bs_antenna_params()

    
    
    # gerar o heatmap CCDF do ganho
    generate_gain_ccdf_heatmap(ant_param, RUN_DIR)
    print("Done.")


if __name__ == "__main__":
    main()