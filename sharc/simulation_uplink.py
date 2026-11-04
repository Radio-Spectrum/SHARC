# -*- coding: utf-8 -*-
"""
Created on Fri Apr  7 17:02:35 2017

@author: edgar
"""

import numpy as np
import math
import warnings

from sharc.simulation import Simulation
from sharc.parameters.parameters import Parameters
from sharc.station_factory import StationFactory
from sharc.parameters.constants import BOLTZMANN_CONSTANT

warn = warnings.warn


class SimulationUplink(Simulation):
    """
    Implements the flowchart of simulation downlink method
    """

    def __init__(self, parameters: Parameters, parameter_file: str):
        super().__init__(parameters, parameter_file)

    def snapshot(self, *args, **kwargs):
        """
        Execute a simulation snapshot for the uplink scenario.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments. Should include 'write_to_file', 'snapshot_number', and 'seed'.
        """
        write_to_file = kwargs["write_to_file"]
        snapshot_number = kwargs["snapshot_number"]
        seed = kwargs["seed"]

        random_number_gen = np.random.RandomState(seed)

        # In case of hotspots, base stations coordinates have to be calculated
        # on every snapshot. Anyway, let topology decide whether to calculate
        # or not
        num_stations_before = self.topology.num_base_stations

        self.topology.calculate_coordinates(random_number_gen)

        if num_stations_before != self.topology.num_base_stations:
            self.initialize_topology_dependant_variables()

        # Create the base stations (remember that it takes into account the
        # network load factor)
        self.bs = StationFactory.generate_imt_base_stations(
            self.parameters.imt,
            # TODO: remove this:
            self.parameters.imt.bs.antenna.array,
            self.topology, random_number_gen,
        )

        # Create the other system (FSS, HAPS, etc...)
        self.system = StationFactory.generate_system(
            self.parameters, self.system_topology, random_number_gen,
            geometry_converter=self.geometry_converter
        )

        # Create IMT user equipments
        self.ue = StationFactory.generate_imt_ue(
            self.parameters.imt,
            # TODO: remove this:
            self.parameters.imt.ue.antenna.array,
            self.topology, random_number_gen,
        )
        # self.plot_scenario()

        if self.parameters.general.system == "WIFI":
            self.system.connect_wifi_sta_to_ap(self.parameters.wifi)
            self.system.run_csma_ca_scheduling(random_number_gen)
            #self.system.select_sta(random_number_gen)
            self.power_control_wifi()
            # Calculate intra wifi coupling loss 
            self.coupling_loss_wifi = self.calculate_intra_wifi_coupling_loss(
                self.system.sta, self.system.ap)
            self.calculate_sinr_wifi()
            

        self.connect_ue_to_bs()
        self.select_ue(random_number_gen)
        self.scheduler()
        self.power_control()
        
        # Calculate coupling loss after beams are created
        self.coupling_loss_imt = self.calculate_intra_imt_coupling_loss(
            self.ue,
            self.bs,
        )
        self.calculate_sinr()


        if self.parameters.general.system == "WIFI":
            self.calculate_sinr_wifi()
            self.calculate_external_interference_wifi()
            self.calculate_sinr_ext_wifi()
            self.collect_results_wifi(write_to_file, snapshot_number)
        else:
            self.calculate_external_interference()
            self.calculate_sinr_ext()
            self.collect_results(write_to_file, snapshot_number)

        

    def power_control(self):
        """
        Apply uplink power control algorithm
        """
        if self.parameters.imt.ue.tx_power_control == "OFF":
            ue_active = np.where(self.ue.active)[0]
            self.ue.tx_power[ue_active] = self.parameters.imt.ue.p_cmax * \
                np.ones(len(ue_active))
        else:
            bs_active = np.where(self.bs.active)[0]
            for bs in bs_active:
                ue = self.link[bs]
                p_cmax = self.parameters.imt.ue.p_cmax
                m_pusch = self.num_rb_per_ue
                p_o_pusch = self.parameters.imt.ue.p_o_pusch
                alpha = self.parameters.imt.ue.alpha
                ue_power_dynamic_range = self.parameters.imt.ue.power_dynamic_range
                cl = self.coupling_loss_imt[bs, ue]
                self.ue.tx_power[ue] = np.minimum(
                    p_cmax, 10 * np.log10(m_pusch) + p_o_pusch + alpha * cl,
                )
                # apply the power dymanic range
                self.ue.tx_power[ue] = np.maximum(
                    self.ue.tx_power[ue], p_cmax - ue_power_dynamic_range,
                )
        if self.adjacent_channel:
            self.ue_power_diff = self.parameters.imt.ue.p_cmax - self.ue.tx_power
    
    def power_control_wifi(self):
        """
        Apply downlink power control algorithm for WiFi
        """
        # Currently, the maximum transmit power of the access point is equaly
        # divided among the selected STAs
        total_power = self.parameters.wifi.ap.conducted_power \
            + self.ap_power_gain
        tx_power = total_power - 10 * math.log10(self.parameters.wifi.sta.k)
        # calculate transmit powers to have a structure such as

        ap_active = np.where(self.system.ap.active)[0]
        self.system.ap.tx_power = dict(
            [(ap, tx_power)
             for ap in ap_active],
        )
        # Update the spectral mask
        self.system.ap.spectral_mask.set_mask(p_tx=total_power)

        total_power = self.parameters.wifi.sta.conducted_power \
            + self.sta_power_gain
        sta_active = np.where(self.system.sta.active)[0]
        self.system.sta.tx_power = dict(
            [(sta, total_power )
             for sta in sta_active],)
        # Update the spectral mask
        self.system.sta.spectral_mask.set_mask(p_tx=total_power)

    def calculate_sinr(self):
        """
        Calculates the uplink SINR for each BS.
        """
        # calculate uplink received power for each active BS
        bs_active = np.where(self.bs.active)[0]
        for bs in bs_active:
            ue = self.link[bs]

            self.bs.rx_power[bs] = self.ue.tx_power[ue] - \
                self.coupling_loss_imt[bs, ue]
            # create a list of BSs that serve the interfering UEs
            bs_interf = [b for b in bs_active if b not in [bs]]

            # calculate intra system interference
            for bi in bs_interf:
                ui = self.link[bi]
                interference = self.ue.tx_power[ui] - \
                    self.coupling_loss_imt[bs, ui]
                self.bs.rx_interference[bs] = 10 * np.log10(
                    np.power(10, 0.1 * self.bs.rx_interference[bs]) +
                    np.power(10, 0.1 * interference),
                )

            # calculate N
            # thermal noise in dBm
            self.bs.thermal_noise[bs] = \
                10 * np.log10(BOLTZMANN_CONSTANT * self.parameters.imt.noise_temperature * 1e3) + \
                10 * np.log10(self.bs.bandwidth[bs] * 1e6) + \
                self.bs.noise_figure[bs]

            # calculate I+N
            self.bs.total_interference[bs] = \
                10 * np.log10(
                    np.power(10, 0.1 * self.bs.rx_interference[bs]) +
                    np.power(10, 0.1 * self.bs.thermal_noise[bs]),
            )

            # calculate SNR and SINR
            self.bs.sinr[bs] = self.bs.rx_power[bs] - \
                self.bs.total_interference[bs]
            self.bs.snr[bs] = self.bs.rx_power[bs] - self.bs.thermal_noise[bs]
    
    def calculate_sinr_wifi(self):
        """
        Calcula o SINR interno para o sistema WiFi (STAs e APs), 
        """
        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]

        sta_rx_interference = np.zeros(self.system.sta.num_stations)
        ap_rx_interference = np.zeros(self.system.ap.num_stations)

        #AP -> STA
        for ap in ap_active:
            linked_stas = sta_active
            if len(linked_stas) == 0:
                continue
            linked_stas = np.array(
                [s for s in np.atleast_1d(linked_stas) if s in sta_active],
            )
            if len(linked_stas) == 0:
                continue
            self.system.sta.rx_power[linked_stas] = self.system.ap.tx_power[ap] - \
                self.coupling_loss_wifi[ap, linked_stas]

            ap_interfer = [a for a in ap_active if a not in [ap]]
            if len(ap_interfer) == 0:
                continue
            for ai in ap_interfer:
                interference = self.system.ap.tx_power[ai] - \
                               self.coupling_loss_wifi[ai, linked_stas]

                sta_rx_interference[linked_stas] = 10 * np.log10(
                    np.power(10, 0.1 * sta_rx_interference[linked_stas]) +
                    np.power(10, 0.1 * interference)
                )
        #STA -> AP
        coupling_loss_sta_ap = self.coupling_loss_wifi.T 

        for ap in ap_active:
            linked_stas = self.system.link[ap]
            if len(linked_stas) == 0:
                continue

            # Considera apenas as STAs que estão de fato ativas/selecionadas
            # neste snapshot (select_sta pode ter restringido sta.active a um
            # subconjunto das STAs originalmente vinculadas ao AP).
            linked_stas = np.array(
                [s for s in np.atleast_1d(linked_stas) if s in sta_active],
            )
            if len(linked_stas) == 0:
                continue

            # 1. Extrai as potências de TX do dicionário e converte para um array NumPy
            tx_powers_sta = np.array([self.system.sta.tx_power[sta] for sta in linked_stas])

            # 2. Calcula a potência recebida de cada STA (em dBm)
            rx_powers_dbm = tx_powers_sta - coupling_loss_sta_ap[linked_stas, ap]

            # 3. Soma as potências linearmente e converte de volta para dBm.
            # Isso consolida o sinal e evita o ValueError na matriz rx_power do AP
            # quando há múltiplas STAs vinculadas ao mesmo AP.
            rx_powers_lin = np.sum(10 ** (0.1 * rx_powers_dbm))
            self.system.ap.rx_power[ap] = 10 * np.log10(rx_powers_lin)

            sta_interferers = [s for s in sta_active if s not in linked_stas]
            if len(sta_interferers) == 0:
                continue
        #AP -> AP
        self.coupling_loss_ap_ap = self.calculate_intra_wifi_coupling_loss(self.system.ap, self.system.ap)
        for ap_victim in ap_active:
            ap_interferers = [a for a in ap_active if a != ap_victim]
            for ai in ap_interferers:
                interference = self.system.ap.tx_power[ai] - \
                               self.coupling_loss_ap_ap[ai, ap_victim]
                
                ap_rx_interference[ap_victim] = 10 * np.log10(
                    np.power(10, 0.1 * ap_rx_interference[ap_victim]) +
                    np.power(10, 0.1 * interference)
                )
        #STA -> STA
        self.coupling_loss_sta_sta = self.calculate_intra_wifi_coupling_loss(self.system.sta, self.system.sta)
        for sta_victim in sta_active:
            sta_interferers = [s for s in sta_active if s != sta_victim]
            for si in sta_interferers:
                interference = self.system.sta.tx_power[si] - \
                               self.coupling_loss_sta_sta[si, sta_victim]

                sta_rx_interference[sta_victim] = 10 * np.log10(
                    np.power(10, 0.1 * sta_rx_interference[sta_victim]) +
                    np.power(10, 0.1 * interference)
                )
        

        self.system.ap.intra_interference[ap_active] = ap_rx_interference[ap_active]
        self.system.sta.intra_interference[sta_active] = sta_rx_interference[sta_active]

        self.system.thermal_noise = \
            10 * np.log10(BOLTZMANN_CONSTANT * self.param_system.noise_temperature * 1e3) + \
            10 * np.log10(self.param_system.bandwidth * 1e6) 


        self.system.ap.total_interference = 10 * np.log10(
            10 ** (0.1 * self.system.ap.rx_interference[ap_active]) +
            10 ** (0.1 * self.system.thermal_noise)
        )
        self.system.sta.total_interference = 10 * np.log10(
            10 ** (0.1 * self.system.sta.rx_interference[sta_active]) +
            10 ** (0.1 * self.system.thermal_noise)
        )
        self.system.ap.snr[ap_active] = self.system.ap.rx_power[ap_active] - self.system.thermal_noise
        self.system.sta.snr[sta_active] = self.system.sta.rx_power[sta_active] - self.system.thermal_noise  
        self.system.ap.sinr[ap_active] = self.system.ap.rx_power[ap_active] - self.system.ap.total_interference
        self.system.sta.sinr[sta_active] = self.system.sta.rx_power[sta_active] - self.system.sta.total_interference

    def calculate_sinr_ext(self):
        """
        Calculates the uplink SINR for each BS taking into account the
        interference that is generated by the other system into IMT system.
        """

        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_emissions != "OFF"
        ):
            self.coupling_loss_imt_system = self.calculate_coupling_loss_system_imt(
                self.system,
                self.bs,
                is_co_channel=True,
            )

        if self.adjacent_channel:
            self.coupling_loss_imt_system_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system,
                    self.bs,
                    is_co_channel=False,
                )

        bs_active = np.where(self.bs.active)[0]
        sys_active = np.where(self.system.active)[0]

        for bs in bs_active:
            active_beams = [
                i for i in range(
                    bs * self.parameters.imt.ue.k,
                    (bs + 1) * self.parameters.imt.ue.k)]
            # Get the weight factor for the system overlaping bandwidth in each beam tx band
            ue = self.link[bs]
            beams_bw = self.ue.bandwidth[ue]
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore",
                                        category=RuntimeWarning,
                                        message="divide by zero encountered in log10")
                # Pesos de sobreposição (mesma lógica do downlink em
                # calculate_sinr_ext_wifi: overlap de banda entre cada
                # feixe/UE e a banda do sistema).
                ue_min_f = self.ue.center_freq[ue] - self.ue.bandwidth[ue] / 2
                ue_max_f = self.ue.center_freq[ue] + self.ue.bandwidth[ue] / 2

                sys_min_f = float(self.param_system.frequency) - float(self.param_system.bandwidth) / 2
                sys_max_f = float(self.param_system.frequency) + float(self.param_system.bandwidth) / 2

                overlap_bw = np.minimum(ue_max_f, sys_max_f) - np.maximum(ue_min_f, sys_min_f)

                weights = np.clip(overlap_bw / float(self.param_system.bandwidth), 0.0, 1.0)

            in_band_interf_lin = np.array([0.0])
            if self.co_channel:
                # TODO: test this in integration testing
                # Inteferer transmit power in dBm over the overlapping band (MHz)
                # [dB]
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore",
                                            category=RuntimeWarning,
                                            message="divide by zero encountered in log10")
                    in_band_interf = self.param_system.tx_power_density + \
                        10 * np.log10(beams_bw[:, np.newaxis] * 1e6) + \
                        10 * np.log10(weights)[:, np.newaxis] - \
                        self.coupling_loss_imt_system[active_beams, :][:, sys_active]
                    in_band_interf_lin = 10 ** (in_band_interf / 10)

            oob_interf_lin = 0
            if self.adjacent_channel:
                # emissions outside of tx bandwidth and inside of rx bw
                # due to oob emissions on tx side
                tx_oob = np.resize(-500., len(active_beams))

                # emissions outside of rx bw and inside of tx bw
                # due to non ideal filtering on rx side
                rx_oob = np.resize(-500., len(active_beams))

                # NOTE: M.2101 states that:
                # "The ACIR value should be calculated based on per UE allocated number of resource blocks"
                if self.parameters.imt.adjacent_ch_reception == "ACS":
                    non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                    if self.overlapping_bandwidth > 0:
                        if not hasattr(self, "_acs_warned"):
                            warn(
                                "You're trying to use ACS on a partially overlapping band "
                                "with UEs.\n\tVerify the code implements the behavior you expect!!"
                            )
                            self._acs_warned = True
                    acs_dB = self.parameters.imt.bs.adjacent_ch_selectivity
                    rx_oob[::] = self.param_system.tx_power_density + 10 * np.log10(non_overlap_sys_bw * 1e6) - acs_dB
                elif self.parameters.imt.adjacent_ch_reception == "OFF":
                    pass
                elif self.parameters.imt.adjacent_ch_reception is False:
                    pass
                else:
                    raise ValueError(
                        f"No implementation for parameters.imt.adjacent_ch_reception == {
                            self.parameters.imt.adjacent_ch_reception}")

                # for tx oob we accept ACLR and spectral mask
                if self.param_system.adjacent_ch_emissions == "SPECTRAL_MASK":
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore",
                                                category=RuntimeWarning,
                                                message="divide by zero encountered in log10")
                        for i, center_freq, bw in zip(
                                range(len(self.bs.center_freq[bs])), self.bs.center_freq[bs], beams_bw):
                            # mask returns dBm
                            # so we convert to [dB]
                            tx_oob[i] = self.system.spectral_mask.power_calc(
                                center_freq,
                                bw
                            ) - 30
                elif self.param_system.adjacent_ch_emissions == "ACLR":
                    # consider ACLR only over non co-channel RBs
                    # This should diminish some of the ACLR interference
                    # in a way that make sense
                    non_overlap_imt_bw = beams_bw * (1. - weights)
                    # NOTE: approximated equal to IMT bw
                    measurement_bw = self.param_system.bandwidth
                    aclr_dB = self.param_system.adjacent_ch_leak_ratio
                    if self.parameters.imt.bandwidth - self.overlapping_bandwidth > measurement_bw:
                        # NOTE: ACLR defines total leaked power over a fixed measurement bandwidth.
                        # If the victim bandwidth is wider, you’re assuming the same leakage
                        # profile extends beyond the ACLR-defined region, which may overestimate interference
                        # FIXME: if the victim bw fully contains tx bw, then
                        # EACH region should be <= measurement_bw
                        warn(
                            "Using System ACLR into IMT, but ACLR measurement bw is "
                            f"{measurement_bw} while the IMT bw is bigger ({self.parameters.imt.bandwidth}).\n"
                            "Are you sure you intend to apply the same ACLR to the entire IMT bw?"
                        )

                    # [dB]
                    tx_oob[::] = self.param_system.tx_power_density + \
                        10 * np.log10(1e6) -  \
                        aclr_dB + 10 * np.log10(
                            non_overlap_imt_bw)
                elif self.param_system.adjacent_ch_emissions == "OFF":
                    pass
                else:
                    raise ValueError(
                        f"No implementation for param_system.adjacent_ch_emissions == {
                            self.param_system.adjacent_ch_emissions}")

                if self.param_system.adjacent_ch_emissions != "OFF":
                    # oob for system is inband for IMT
                    tx_oob = tx_oob[:, np.newaxis] - self.coupling_loss_imt_system[active_beams, :][:, sys_active]

                # oob for IMT
                rx_oob = rx_oob[:, np.newaxis] - self.coupling_loss_imt_system_adjacent[active_beams, :][:, sys_active]

                # Out of band power
                # sum linearly power leaked into band and power received in the
                # adjacent band

                # linear [W]:
                oob_interf_lin = 10 ** (0.1 * tx_oob) + 10 ** (0.1 * rx_oob)

            # [dBm]
            ext_interference = 10 * np.log10(in_band_interf_lin + oob_interf_lin) + 30

            # Sum all the interferers from each active system transmitters for each bs
            self.bs.ext_interference[bs] = 10 * np.log10(
                np.sum(np.power(10, 0.1 * ext_interference), axis=1))

            self.bs.sinr_ext[bs] = self.bs.rx_power[bs] \
                - (10 * np.log10(np.power(10, 0.1 * self.bs.total_interference[bs]) +
                                 np.power(10, 0.1 * self.bs.ext_interference[bs],),))

            self.bs.inr[bs] = self.bs.ext_interference[bs] - \
                self.bs.thermal_noise[bs]
    

    def calculate_sinr_ext_wifi(self):
        """
        Calculates the uplink SINR and INR for each BS taking into account the
        interference that is generated by WIFI (AP and STA) into IMT system.

        Segue a mesma lógica usada em SimulationDownlink.calculate_sinr_ext_wifi:
        as parcelas de interferência (em banda e fora de banda) são somadas no
        domínio LINEAR (mW) e convertidas para dBm uma única vez, ao final.
        Como as potências do WiFi (self.system.ap.tx_power / sta.tx_power) já
        estão em dBm (vêm de conducted_power + ganhos), NÃO se aplica nenhum
        deslocamento de +30 dB (esse deslocamento só faz sentido quando a
        grandeza de origem está em dBW, como em calculate_sinr_ext, que lida
        com tx_power_density de outros sistemas como FSS/HAPS).
        """
        # 1. Perdas de acoplamento co-canal (WiFi -> IMT BS)
        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_emissions != "OFF"
        ):
            # Matriz [N_Beams, N_APs]
            self.coupling_loss_imt_system_ap = self.calculate_coupling_loss_system_imt(
                self.system.ap,
                self.bs,
                is_co_channel=True,
            )
            # Matriz [N_Beams, N_STAs]
            self.coupling_loss_imt_system_sta = self.calculate_coupling_loss_system_imt(
                self.system.sta,
                self.bs,
                is_co_channel=True,
            )

        # Perdas de acoplamento em canal adjacente (emissões fora de banda do
        # WiFi + recepção não ideal da BS), mesma lógica do downlink.
        if self.adjacent_channel:
            self.coupling_loss_imt_system_ap_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system.ap,
                    self.bs,
                    is_co_channel=False,
                )
            self.coupling_loss_imt_system_sta_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system.sta,
                    self.bs,
                    is_co_channel=False,
                )

        bs_active = np.where(self.bs.active)[0]
        active_ap = np.where(self.system.ap.active)[0]
        active_sta = np.where(self.system.sta.active)[0]

        # self.system.ap.tx_power / sta.tx_power são dicts (montados em
        # power_control_wifi); extraímos os valores uma única vez, na mesma
        # ordem de active_ap/active_sta, igual ao downlink.
        tx_power_ap_arr = np.array([self.system.ap.tx_power[ap] for ap in active_ap])
        tx_power_sta_arr = np.array([self.system.sta.tx_power[sta] for sta in active_sta])

        for bs in bs_active:
            # Feixes ativos desta BS
            active_beams = [
                i for i in range(
                    bs * self.parameters.imt.ue.k,
                    (bs + 1) * self.parameters.imt.ue.k)]

            # self.ue.bandwidth é um vetor, usamos self.link[bs] para pegar as UEs desta BS
            ue = self.link[bs]

            # Pesos de sobreposição: fração da banda do sistema WIFI que cai
            # dentro da banda de cada feixe/UE (mesma lógica do downlink).
            ue_min_f = self.ue.center_freq[ue] - self.ue.bandwidth[ue] / 2
            ue_max_f = self.ue.center_freq[ue] + self.ue.bandwidth[ue] / 2

            sys_min_f = float(self.param_system.frequency) - float(self.param_system.bandwidth) / 2
            sys_max_f = float(self.param_system.frequency) + float(self.param_system.bandwidth) / 2

            overlap_bw = np.minimum(ue_max_f, sys_max_f) - np.maximum(ue_min_f, sys_min_f)

            weights = np.clip(overlap_bw / float(self.param_system.bandwidth), 0.0, 1.0)

            # --- Interferência em banda (co-canal), já em mW (linear) ---
            # Acumuladores em mW (LINEAR): 0 = sem interferência. Não usar -500 aqui,
            # pois esses valores são somados no domínio linear.
            in_band_interf_power = np.zeros(len(ue))
            if self.co_channel and self.overlapping_bandwidth > 0:
                interf_ap_lin = np.sum(10 ** (0.1 * (
                        tx_power_ap_arr +
                        10 * np.log10(weights)[:, np.newaxis] -
                        self.coupling_loss_imt_system_ap[active_beams, :][:, active_ap]
                    )), axis=1)

                interf_sta_lin = np.sum(10 ** (0.1 * (
                        tx_power_sta_arr +
                        10 * np.log10(weights)[:, np.newaxis] -
                        self.coupling_loss_imt_system_sta[active_beams, :][:, active_sta]
                    )), axis=1)

                # Soma das potências (APs + STAs) em mW
                in_band_interf_power = interf_ap_lin + interf_sta_lin

            # --- Interferência fora de banda (canal adjacente), já em mW (linear) ---
            oob_power_lin = np.zeros(len(ue))  # mW (linear); 0 se não houver canal adjacente

            if self.adjacent_channel:
                # fração da banda do WIFI que NÃO se sobrepõe à banda de cada feixe
                non_overlap_weight = np.clip(1.0 - weights, 0.0, 1.0)

                # --- Lado Tx: emissões fora de banda do AP/STA vazando para
                # dentro da banda do feixe (governado por
                # param_system.adjacent_ch_emissions) ---
                tx_oob_ap_lin = np.zeros(len(ue))
                tx_oob_sta_lin = np.zeros(len(ue))
                if self.param_system.adjacent_ch_emissions == "SPECTRAL_MASK":
                    for i in range(len(ue)):
                        uex = ue[i]
                        beam_idx = active_beams[i]
                        cf = self.ue.center_freq[uex]
                        bw = self.ue.bandwidth[uex]

                        ap_oob_dbm = self.system.ap.spectral_mask.power_calc(cf, bw)
                        tx_oob_ap_lin[i] = np.sum(10 ** (0.1 * (
                            ap_oob_dbm - self.coupling_loss_imt_system_ap_adjacent[beam_idx, active_ap]
                        )))

                        sta_oob_dbm = self.system.sta.spectral_mask.power_calc(cf, bw)
                        tx_oob_sta_lin[i] = np.sum(10 ** (0.1 * (
                            sta_oob_dbm - self.coupling_loss_imt_system_sta_adjacent[beam_idx, active_sta]
                        )))
                elif self.param_system.adjacent_ch_emissions == "ACLR":
                    measurement_bw = self.param_system.bandwidth
                    aclr_dB = self.param_system.adjacent_ch_leak_ratio
                    # porção da banda do próprio feixe que não se sobrepõe à banda do WIFI
                    non_overlap_imt_bw = self.ue.bandwidth[ue] * non_overlap_weight

                    ap_tx_oob_dbm = tx_power_ap_arr[np.newaxis, :] - aclr_dB + \
                        10 * np.log10(non_overlap_imt_bw / measurement_bw)[:, np.newaxis]
                    tx_oob_ap_lin = np.sum(10 ** (0.1 * (
                        ap_tx_oob_dbm - self.coupling_loss_imt_system_ap_adjacent[active_beams, :][:, active_ap]
                    )), axis=1)

                    sta_tx_oob_dbm = tx_power_sta_arr[np.newaxis, :] - aclr_dB + \
                        10 * np.log10(non_overlap_imt_bw / measurement_bw)[:, np.newaxis]
                    tx_oob_sta_lin = np.sum(10 ** (0.1 * (
                        sta_tx_oob_dbm - self.coupling_loss_imt_system_sta_adjacent[active_beams, :][:, active_sta]
                    )), axis=1)
                elif self.param_system.adjacent_ch_emissions == "OFF":
                    pass
                else:
                    raise ValueError(
                        f"No implementation for param_system.adjacent_ch_emissions == {
                            self.param_system.adjacent_ch_emissions}")

                # --- Lado Rx: filtro de recepção não ideal da BS (ACS)
                # captando potência em banda do AP/STA fora da região de overlap ---
                rx_oob_ap_lin = np.zeros(len(ue))
                rx_oob_sta_lin = np.zeros(len(ue))
                if self.parameters.imt.adjacent_ch_reception == "ACS":
                    # ACS do lado receptor é o da BS (vítima é a BS no uplink),
                    # análogo ao usado em calculate_sinr_ext para o caso genérico.
                    acs_dB = self.parameters.imt.bs.adjacent_ch_selectivity
                    non_overlap_sys_bw = float(self.param_system.bandwidth) * non_overlap_weight

                    ap_rx_oob_dbm = tx_power_ap_arr[np.newaxis, :] + \
                        10 * np.log10(non_overlap_sys_bw)[:, np.newaxis] - acs_dB
                    rx_oob_ap_lin = np.sum(10 ** (0.1 * (
                        ap_rx_oob_dbm - self.coupling_loss_imt_system_ap_adjacent[active_beams, :][:, active_ap]
                    )), axis=1)

                    sta_rx_oob_dbm = tx_power_sta_arr[np.newaxis, :] + \
                        10 * np.log10(non_overlap_sys_bw)[:, np.newaxis] - acs_dB
                    rx_oob_sta_lin = np.sum(10 ** (0.1 * (
                        sta_rx_oob_dbm - self.coupling_loss_imt_system_sta_adjacent[active_beams, :][:, active_sta]
                    )), axis=1)
                elif self.parameters.imt.adjacent_ch_reception == "OFF":
                    pass
                else:
                    raise ValueError(
                        f"No implementation for parameters.imt.adjacent_ch_reception == {
                            self.parameters.imt.adjacent_ch_reception}")

                # já em mW (linear); NÃO reconverter com 10**(0.1*x) abaixo,
                # pois isso já foi feito em cada parcela (_lin) acima.
                oob_power_lin = tx_oob_ap_lin + tx_oob_sta_lin + rx_oob_ap_lin + rx_oob_sta_lin

            bs_ext_int = in_band_interf_power + oob_power_lin
            self.bs.ext_interference[bs] = 10 * np.log10(bs_ext_int)

            #print(np.array(self.bs.rx_interference))
            bs_rx_interf_arr = np.array(list(self.bs.rx_interference.values()))
            intra_bs_mw = np.power(10, 0.1 * bs_rx_interf_arr).flatten()

            bs_ext_interf_arr = np.array(list(self.bs.ext_interference.values()))
            total_interf_bs_mw = intra_bs_mw + np.power(10, 0.1 * bs_ext_interf_arr.flatten())
            
            self.bs.interf_power_total = 10 * np.log10(total_interf_bs_mw)

            # Recalcula SINR Externo: S / (I_intra + I_ext + N)
            i_intra_noise_lin = 10 ** (0.1 * self.bs.total_interference[bs])
            i_ext_lin = 10 ** (0.1 * self.bs.ext_interference[bs])

            self.bs.sinr_ext[bs] = self.bs.rx_power[bs] - 10 * np.log10(i_intra_noise_lin + i_ext_lin)

            # Calculate INR in dB.
            # A vítima aqui é a BS (não a UE), então usamos a banda e a figura
            # de ruído da PRÓPRIA BS (self.bs.bandwidth[bs] / self.bs.noise_figure[bs]),
            # exatamente como em calculate_sinr(). Indexar self.ue.bandwidth
            # com 'bs' pegaria a banda de uma UE não relacionada a esta BS.
            self.bs.thermal_noise[bs] = \
                10 * np.log10(BOLTZMANN_CONSTANT * self.parameters.imt.noise_temperature * 1e3) + \
                10 * np.log10(self.bs.bandwidth[bs] * 1e6) + self.bs.noise_figure[bs]

            # INR = I_externa - Ruído Térmico
            self.bs.inr[bs] = self.bs.ext_interference[bs] - self.bs.thermal_noise[bs]

    def calculate_external_interference(self):
        """
        Calculates interference that IMT system generates on other system
        """

        if self.co_channel or (
            # then rx receives emission inside the tx band, so it is co-channel with IMT
            self.adjacent_channel and self.param_system.adjacent_ch_reception != "OFF"
        ):
            self.coupling_loss_imt_system = self.calculate_coupling_loss_system_imt(
                self.system, self.ue, is_co_channel=True, )
        if self.adjacent_channel:
            self.coupling_loss_imt_system_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system,
                    self.ue,
                    is_co_channel=False,
                )

        # applying a bandwidth scaling factor since UE transmits on a portion
        # of the satellite's bandwidth
        # calculate interference only from active UE's
        rx_interference = 0

        bs_active = np.where(self.bs.active)[0]
        sys_active = np.where(self.system.active)[0]
        for bs in bs_active:
            ue = self.link[bs]

            if self.co_channel:
                # TODO: test this in integration testing
                # Pesos de sobreposição (mesma lógica do downlink em
                # calculate_sinr_ext_wifi: overlap de banda entre cada UE e
                # a banda do sistema).
                ue_min_f = self.ue.center_freq[ue] - self.ue.bandwidth[ue] / 2
                ue_max_f = self.ue.center_freq[ue] + self.ue.bandwidth[ue] / 2

                sys_min_f = float(self.param_system.frequency) - float(self.param_system.bandwidth) / 2
                sys_max_f = float(self.param_system.frequency) + float(self.param_system.bandwidth) / 2

                overlap_bw = np.minimum(ue_max_f, sys_max_f) - np.maximum(ue_min_f, sys_min_f)

                weights = np.clip(overlap_bw / float(self.param_system.bandwidth), 0.0, 1.0)

                interference_ue = self.ue.tx_power[ue] - \
                    self.coupling_loss_imt_system[ue, sys_active]
                rx_interference += np.sum(
                    weights * np.power(
                        10,
                        0.1 * interference_ue,
                    ),
                )

            if self.adjacent_channel:
                # These are in dB. Turn to zero linear.
                tx_oob = -np.inf
                rx_oob = -np.inf
                # Calculate how much power is emitted in the adjacent channel:
                if self.parameters.imt.adjacent_ch_emissions == "SPECTRAL_MASK":
                    # The unwanted emission is calculated in terms of TRP (after
                    # antenna). In SHARC implementation, ohmic losses are already
                    # included in coupling loss. Then, care has to be taken;
                    # otherwise ohmic loss will be included twice.
                    # TODO?: what is ue_power_diff
                    tx_oob = self.ue.spectral_mask.power_calc(self.param_system.frequency, self.system.bandwidth) \
                        - self.ue_power_diff[ue] \
                        + self.parameters.imt.ue.ohmic_loss

                elif self.parameters.imt.adjacent_ch_emissions == "ACLR":
                    non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                    # NOTE: approximated equal to IMT bw
                    measurement_bw = self.parameters.imt.bandwidth
                    aclr_dB = self.parameters.imt.ue.adjacent_ch_leak_ratio

                    if non_overlap_sys_bw > measurement_bw:
                        # NOTE: ACLR defines total leaked power over a fixed measurement bandwidth.
                        # If the victim bandwidth is wider, you’re assuming the same leakage
                        # profile extends beyond the ACLR-defined region, which may overestimate interference
                        # FIXME: if the victim bw fully contains tx bw, then
                        # EACH region should be <= measurement_bw
                        warn(
                            "Using IMT ACLR into system, but ACLR measurement bw is "
                            f"{measurement_bw} while the system bw is bigger ({non_overlap_sys_bw}).\n"
                            "Are you sure you intend to apply ACLR to the entire system bw?"
                        )

                    # tx_oob_in_measurement = (tx_pow_lin / aclr)
                    # => approx. PSD = (tx_pow_lin / aclr) / measurement_bw
                    # approximated received tx_oob = PSD * non_overlap_sys_bw
                    # NOTE: we don't get total power, but power per beam
                    # because later broadcast will sum this tx_oob `k` times
                    tx_oob = self.ue.tx_power[ue] - aclr_dB + 10 * np.log10(
                        non_overlap_sys_bw / measurement_bw
                    )
                elif self.parameters.imt.adjacent_ch_emissions == "OFF":
                    pass
                else:
                    raise ValueError(
                        f"No implementation for self.parameters.imt.adjacent_ch_emissions == {self.parameters.imt.adjacent_ch_emissions}"
                    )

                # Calculate how much power is received in the adjacent channel
                if self.param_system.adjacent_ch_reception == "ACS":
                    non_overlap_imt_bw = self.parameters.imt.bandwidth - self.overlapping_bandwidth
                    tx_bw = self.parameters.imt.bandwidth
                    acs_dB = self.param_system.adjacent_ch_selectivity

                    # NOTE: only the power not overlapping is attenuated by ACS
                    # PSD = tx_pow_lin / tx_bw
                    # tx_pow_adj_lin = PSD * non_overlap_imt_bw
                    # rx_oob = tx_pow_adj_lin / acs
                    rx_oob = self.ue.tx_power[ue] + 10 * np.log10(
                        non_overlap_imt_bw / tx_bw
                    ) - acs_dB
                elif self.param_system.adjacent_ch_reception == "OFF":
                    if self.parameters.imt.adjacent_ch_emissions == "OFF":
                        raise ValueError("parameters.imt.adjacent_ch_emissions and parameters.imt.adjacent_ch_reception"
                                         " cannot be both set to \"OFF\"")
                    pass
                else:
                    raise ValueError(
                        f"No implementation for self.param_system.adjacent_ch_reception == {self.param_system.adjacent_ch_reception}"
                    )

                # Out of band power
                tx_oob -= self.coupling_loss_imt_system_adjacent[ue, sys_active]

                if self.param_system.adjacent_ch_reception != "OFF":
                    rx_oob -= self.coupling_loss_imt_system[ue, sys_active]
                # Out of band power
                # sum linearly power leaked into band and power received in the adjacent band
                oob_power_lin = 10 ** (0.1 * tx_oob) + 10 ** (0.1 * rx_oob)

                rx_interference += np.sum(
                    oob_power_lin
                )

        self.system.rx_interference = 10 * np.log10(rx_interference)
        # calculate N
        self.system.thermal_noise = \
            10 * np.log10(
                BOLTZMANN_CONSTANT *
                self.system.noise_temperature * 1e3,
            ) + \
            10 * math.log10(self.param_system.bandwidth * 1e6)

        # calculate INR at the system
        self.system.inr = np.array(
            [self.system.rx_interference - self.system.thermal_noise],
        )

        # Calculate PFD at the system
        # TODO: generalize this a bit more if needed
        if hasattr(
                self.system.antenna[0],
                "effective_area") and self.system.num_stations == 1:
            self.system.pfd = 10 * \
                np.log10(
                    10**(self.system.rx_interference / 10) /
                    self.system.antenna[0].effective_area,
                )

    def calculate_external_interference_wifi(self):
        """
        Calculates interference that IMT system (UEs) generates on WIFI (AP and STA)

        Canal adjacente implementado seguindo a mesma lógica de
        calculate_external_interference (versão genérica/não-WiFi neste mesmo
        arquivo): emissão fora de banda da UE (Tx, via SPECTRAL_MASK ou ACLR)
        somada à recepção não ideal do WIFI (Rx, via ACS), tudo no domínio
        linear (mW) por UE/feixe, e depois somado em AP/STA separadamente.
        """
        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_reception != "OFF"
        ):
            self.coupling_loss_imt_system_ap = self.calculate_coupling_loss_system_imt(
                self.system.ap, self.ue, is_co_channel=True, )
            self.coupling_loss_imt_system_sta = self.calculate_coupling_loss_system_imt(
                self.system.sta, self.ue, is_co_channel=True, )

        # Perdas de acoplamento em canal adjacente (emissão OOB da UE +
        # recepção não ideal do WIFI), mesma lógica de
        # calculate_external_interference.
        if self.adjacent_channel:
            self.coupling_loss_imt_system_ap_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system.ap, self.ue, is_co_channel=False, )
            self.coupling_loss_imt_system_sta_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system.sta, self.ue, is_co_channel=False, )

        bs_active = np.where(self.bs.active)[0]
        # Calculate for both AP and STA
        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]

        rx_interference_linear_ap = np.zeros(self.system.ap.num_stations)
        rx_interference_linear_sta = np.zeros(self.system.sta.num_stations)

        for bs in bs_active:
            # UEs (feixes) servidos por esta BS neste snapshot
            ue = self.link[bs]
            if len(ue) == 0:
                continue

            # Pesos de sobreposição (mesma lógica usada no downlink em
            # calculate_sinr_ext_wifi: overlap de banda entre cada UE e
            # a banda do sistema WIFI). Usado tanto pelo co-canal quanto
            # pelo ACLR/ACS do canal adjacente.
            weights = self.calculate_bw_weights(
                self.ue.bandwidth[ue],
                self.ue.center_freq[ue],
                self.param_system.bandwidth,
                self.param_system.frequency,
            )

            if self.co_channel:
                # Potência de cada UE (dB) já ponderada pela fração de banda
                # que efetivamente se sobrepõe à banda do WIFI.
                tx_power_ue = self.ue.tx_power[ue] + 10 * np.log10(weights)

                # UE -> AP: matriz [N_ue_desta_bs, N_ap_active]
                interference_ue_ap = tx_power_ue[:, np.newaxis] - \
                    self.coupling_loss_imt_system_ap[np.ix_(ue, ap_active)]
                rx_interference_linear_ap[ap_active] += np.sum(
                    10 ** (0.1 * interference_ue_ap), axis=0,
                )

                # UE -> STA: matriz [N_ue_desta_bs, N_sta_active]
                interference_ue_sta = tx_power_ue[:, np.newaxis] - \
                    self.coupling_loss_imt_system_sta[np.ix_(ue, sta_active)]
                rx_interference_linear_sta[sta_active] += np.sum(
                    10 ** (0.1 * interference_ue_sta), axis=0,
                )

            if self.adjacent_channel:
                # fração da banda do WIFI que NÃO se sobrepõe à banda de cada UE
                non_overlap_weight = np.clip(1.0 - weights, 0.0, 1.0)

                # --- Lado Tx: emissão fora de banda de cada UE, mesma lógica
                # de calculate_external_interference ---
                if self.parameters.imt.adjacent_ch_emissions == "SPECTRAL_MASK":
                    # self.ue_power_diff[ue] é um array -> broadcast garante
                    # que tx_oob já sai com shape (len(ue),).
                    tx_oob = self.ue.spectral_mask.power_calc(
                        self.param_system.frequency, self.system.bandwidth,
                    ) - self.ue_power_diff[ue] + self.parameters.imt.ue.ohmic_loss
                elif self.parameters.imt.adjacent_ch_emissions == "ACLR":
                    non_overlap_sys_bw = float(self.param_system.bandwidth) * non_overlap_weight
                    measurement_bw = self.parameters.imt.bandwidth
                    aclr_dB = self.parameters.imt.ue.adjacent_ch_leak_ratio

                    tx_oob = self.ue.tx_power[ue] - aclr_dB + 10 * np.log10(
                        non_overlap_sys_bw / measurement_bw,
                    )
                elif self.parameters.imt.adjacent_ch_emissions == "OFF":
                    tx_oob = np.full(len(ue), -np.inf)
                else:
                    raise ValueError(
                        f"No implementation for parameters.imt.adjacent_ch_emissions == {
                            self.parameters.imt.adjacent_ch_emissions}")

                # --- Lado Rx: filtro de recepção não ideal do WIFI (ACS) ---
                if self.param_system.adjacent_ch_reception == "ACS":
                    non_overlap_imt_bw = self.ue.bandwidth[ue] * non_overlap_weight
                    acs_dB = self.param_system.adjacent_ch_selectivity

                    rx_oob = self.ue.tx_power[ue] + 10 * np.log10(
                        non_overlap_imt_bw / self.ue.bandwidth[ue],
                    ) - acs_dB
                elif self.param_system.adjacent_ch_reception == "OFF":
                    if self.parameters.imt.adjacent_ch_emissions == "OFF":
                        raise ValueError(
                            "parameters.imt.adjacent_ch_emissions and "
                            "param_system.adjacent_ch_reception cannot be both \"OFF\"")
                    rx_oob = np.full(len(ue), -np.inf)
                else:
                    raise ValueError(
                        f"No implementation for param_system.adjacent_ch_reception == {
                            self.param_system.adjacent_ch_reception}")

                # Vazamento Tx da UE, acoplado via perda de canal adjacente,
                # chegando no AP e na STA
                tx_oob_ap = tx_oob[:, np.newaxis] - \
                    self.coupling_loss_imt_system_ap_adjacent[np.ix_(ue, ap_active)]
                tx_oob_sta = tx_oob[:, np.newaxis] - \
                    self.coupling_loss_imt_system_sta_adjacent[np.ix_(ue, sta_active)]

                # Potência em banda da UE captada pelo receptor imperfeito
                # (ACS) do AP/STA -> usa a perda de acoplamento CO-CANAL
                if self.param_system.adjacent_ch_reception != "OFF":
                    rx_oob_ap = rx_oob[:, np.newaxis] - \
                        self.coupling_loss_imt_system_ap[np.ix_(ue, ap_active)]
                    rx_oob_sta = rx_oob[:, np.newaxis] - \
                        self.coupling_loss_imt_system_sta[np.ix_(ue, sta_active)]
                else:
                    rx_oob_ap = np.full_like(tx_oob_ap, -np.inf)
                    rx_oob_sta = np.full_like(tx_oob_sta, -np.inf)

                # Soma linear das duas parcelas (vazamento Tx + recepção Rx)
                rx_interference_linear_ap[ap_active] += np.sum(
                    10 ** (0.1 * tx_oob_ap) + 10 ** (0.1 * rx_oob_ap), axis=0,
                )
                rx_interference_linear_sta[sta_active] += np.sum(
                    10 ** (0.1 * tx_oob_sta) + 10 ** (0.1 * rx_oob_sta), axis=0,
                )

        self.system.ap.ext_interference[ap_active] = 10 * np.log10(rx_interference_linear_ap[ap_active])
        self.system.sta.ext_interference[sta_active] = 10 * np.log10(rx_interference_linear_sta[sta_active])

        #calculate total interference at the system
        intra_ap_mw = np.power(10, 0.1 * self.system.ap.rx_interference).flatten()
        intra_sta_mw = np.power(10, 0.1 * self.system.sta.rx_interference).flatten()

        total_interf_ap_mw = intra_ap_mw
        total_interf_sta_mw = intra_sta_mw

        total_interf_ap_mw[ap_active] += rx_interference_linear_ap[ap_active]
        total_interf_sta_mw[sta_active] += rx_interference_linear_sta[sta_active]

        self.system.ap.interf_power_total[ap_active] = 10 * np.log10(total_interf_ap_mw[ap_active])
        self.system.sta.interf_power_total[sta_active] = 10 * np.log10(total_interf_sta_mw[sta_active])

        # calculate N (and INR)
        self.system.thermal_noise = \
            10 * np.log10(
                BOLTZMANN_CONSTANT *
                self.system.noise_temperature * 1e3,
            ) + \
            10 * math.log10(self.param_system.bandwidth * 1e6)


        self.system.ap.inr = (
                    self.system.ap.ext_interference - self.system.thermal_noise
                )
        self.system.sta.inr = (
            self.system.sta.ext_interference - self.system.thermal_noise
        )

        self.system.inr = np.concatenate((self.system.ap.inr.flatten(), self.system.sta.inr.flatten()))

    def collect_results(self, write_to_file: bool, snapshot_number: int):
        """
        Collect and store results for the current uplink simulation snapshot.

        Args:
            write_to_file (bool): Whether to write results to file.
            snapshot_number (int): The current snapshot number.
        """
        if not self.parameters.imt.interfered_with and np.any(self.bs.active):
            self.results.system_inr.extend(self.system.inr.flatten())
            self.results.system_ul_interf_power.extend(
                self.system.rx_interference.flatten()
            )
            self.results.system_ul_interf_power_per_mhz.extend(
                [self.system.rx_interference - 10 * math.log10(self.system.bandwidth)],
            )
            # TODO: generalize this a bit more if needed
            if hasattr(
                    self.system.antenna[0],
                    "effective_area") and self.system.num_stations == 1:
                self.results.system_pfd.extend([self.system.pfd])

        sys_active = np.where(self.system.active)[0]
        bs_active = np.where(self.bs.active)[0]
        for bs in bs_active:
            ue = self.link[bs]
            self.results.imt_path_loss.extend(self.path_loss_imt[bs, ue])
            self.results.imt_coupling_loss.extend(
                self.coupling_loss_imt[bs, ue],
            )

            self.results.imt_bs_antenna_gain.extend(
                self.imt_bs_antenna_gain[bs, ue],
            )
            self.results.imt_ue_antenna_gain.extend(
                self.imt_ue_antenna_gain[bs, ue],
            )

            tput = self.calculate_imt_tput(
                self.bs.sinr[bs],
                self.parameters.imt.uplink.sinr_min,
                self.parameters.imt.uplink.sinr_max,
                self.parameters.imt.uplink.attenuation_factor,
            )
            self.results.imt_ul_tput.extend(tput.tolist())

            if self.parameters.imt.interfered_with:
                tput_ext = self.calculate_imt_tput(
                    self.bs.sinr_ext[bs],
                    self.parameters.imt.uplink.sinr_min,
                    self.parameters.imt.uplink.sinr_max,
                    self.parameters.imt.uplink.attenuation_factor,
                )
                self.results.imt_ul_tput_ext.extend(tput_ext.tolist())
                self.results.imt_ul_sinr_ext.extend(
                    self.bs.sinr_ext[bs].tolist(),
                )
                self.results.imt_ul_inr.extend(self.bs.inr[bs].tolist())

                active_beams = np.array([
                    i for i in range(
                        bs * self.parameters.imt.ue.k, (bs + 1) * self.parameters.imt.ue.k,
                    )
                ])
                self.results.system_imt_antenna_gain.extend(
                    self.system_imt_antenna_gain[np.ix_(sys_active, active_beams)].flatten(),
                )
                self.results.imt_system_antenna_gain.extend(
                    self.imt_system_antenna_gain[np.ix_(sys_active, active_beams)].flatten(),
                )
                if len(self.imt_system_antenna_gain_adjacent):
                    self.results.imt_system_antenna_gain_adjacent.extend(
                        self.imt_system_antenna_gain_adjacent[np.ix_(sys_active, active_beams)].flatten(),)
                self.results.imt_system_path_loss.extend(
                    self.imt_system_path_loss[np.ix_(sys_active, active_beams)].flatten(),
                )
                if self.param_system.channel_model == "HDFSS":
                    self.results.imt_system_build_entry_loss.extend(
                        self.imt_system_build_entry_loss[np.ix_(sys_active, active_beams)],
                    )
                    self.results.imt_system_diffraction_loss.extend(
                        self.imt_system_diffraction_loss[np.ix_(sys_active, active_beams)],
                    )
            else:  # IMT is the interferer
                self.results.system_imt_antenna_gain.extend(
                    self.system_imt_antenna_gain[np.ix_(sys_active, ue)].flatten(),
                )
                if len(self.imt_system_antenna_gain):
                    self.results.imt_system_antenna_gain.extend(
                        self.imt_system_antenna_gain[np.ix_(sys_active, ue)].flatten(),
                    )
                if len(self.imt_system_antenna_gain_adjacent):
                    self.results.imt_system_antenna_gain_adjacent.extend(
                        self.imt_system_antenna_gain_adjacent[np.ix_(sys_active, ue)].flatten(),
                    )
                self.results.imt_system_path_loss.extend(
                    self.imt_system_path_loss[np.ix_(sys_active, ue)].flatten(),
                )
                if self.param_system.channel_model == "HDFSS":
                    self.results.imt_system_build_entry_loss.extend(
                        self.imt_system_build_entry_loss[np.ix_(sys_active, ue)],
                    )
                    self.results.imt_system_diffraction_loss.extend(
                        self.imt_system_diffraction_loss[np.ix_(sys_active, ue)],
                    )

            self.results.imt_ul_tx_power.extend(self.ue.tx_power[ue].tolist())
            imt_ul_tx_power_density = 10 * np.log10(
                np.power(10, 0.1 * self.ue.tx_power[ue]) / (
                    self.num_rb_per_ue * self.parameters.imt.rb_bandwidth * 1e6
                ),
            )
            self.results.imt_ul_tx_power_density.extend(
                imt_ul_tx_power_density.tolist(),
            )
            self.results.imt_ul_sinr.extend(self.bs.sinr[bs].tolist())
            self.results.imt_ul_snr.extend(self.bs.snr[bs].tolist())
            self.results.imt_ul_ext_interf_power.extend(
                self.bs.ext_interference[bs].tolist(),
            )
            self.results.imt_ul_inr.extend(
                            self.bs.inr[bs].tolist(),
            )

        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)
    
    def collect_results_wifi(self, write_to_file: bool, snapshot_number: int):
        """
        Collect and store results for the current uplink simulation snapshot when using WiFi.
        """

        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]

        self.results.system_ul_interf_power.extend(self.system.ap.ext_interference[ap_active])
        self.results.system_ul_interf_power.extend(self.system.sta.ext_interference[sta_active])
        self.results.system_intra_ul_interf_power.extend(self.system.ap.intra_interference[ap_active])
        self.results.system_intra_ul_interf_power.extend(self.system.sta.intra_interference[sta_active])
        self.results.system_interf_power_total.extend(self.system.ap.interf_power_total[ap_active])
        self.results.system_interf_power_total.extend(self.system.sta.interf_power_total[sta_active])
        self.results.system_ul_sinr.extend(self.system.ap.sinr[ap_active])
        self.results.system_ul_sinr.extend(self.system.sta.sinr[sta_active])
        self.results.system_ul_snr.extend(self.system.ap.snr[ap_active])
        self.results.system_ul_snr.extend(self.system.sta.snr[sta_active])
        self.results.system_inr.extend(self.system.ap.inr[ap_active])
        self.results.system_inr.extend(self.system.sta.inr[sta_active])

        for sinr in self.results.system_ul_sinr:
            tput = self.calculate_wifi_tput(sinr)
            self.results.system_ul_tput.append(float(tput))

        for ap in ap_active:
            sta = self.system.link[ap]
            
            # Perda de percurso e ganhos de antena
            self.results.system_path_loss.extend(self.path_loss_wifi[ap, sta])

            path_loss_ap_ap = self.path_loss_ap_ap[ap, ap_active]
            path_loss_sta_sta = self.path_loss_sta_sta[sta, sta_active]

            self.results.system_path_loss.extend(path_loss_ap_ap[np.isfinite(path_loss_ap_ap)])
            self.results.system_path_loss.extend(path_loss_sta_sta[np.isfinite(path_loss_sta_sta)])

            self.results.system_ap_antenna_gain.extend(self.ap_antenna_gain[ap, sta])
            self.results.system_sta_antenna_gain.extend(self.sta_antenna_gain[ap, sta])
            

        '''self.results.system_ul_interf_power_per_mhz.extend(
                        self.results.system_ul_interf_power.flatten() - 10 * math.log10(self.system.bandwidth),
                        )
        '''
        bs_active = np.where(self.bs.active)[0]

        for bs in bs_active:
            ue = self.link[bs]

            self.results.imt_path_loss.extend(
                self.path_loss_imt[bs, ue],
            )
            self.results.imt_coupling_loss.extend(
                self.coupling_loss_imt[bs, ue],
            )

            self.results.imt_bs_antenna_gain.extend(
                self.imt_bs_antenna_gain[bs, ue],
            )
            self.results.imt_ue_antenna_gain.extend(
                self.imt_ue_antenna_gain[bs, ue],
            )

            tput = self.calculate_imt_tput(
                self.bs.sinr[bs],
                self.parameters.imt.uplink.sinr_min,
                self.parameters.imt.uplink.sinr_max,
                self.parameters.imt.uplink.attenuation_factor,
            )
            self.results.imt_ul_tput.extend(
                tput.tolist(),
            )

            self.results.imt_ul_inr.extend(
                self.bs.inr[bs].tolist(),
            )

            self.results.ap_imt_antenna_gain.extend(
                self.ap_imt_antenna_gain[
                    ap_active[:, np.newaxis],
                    ue,
                ].flatten(),
            )

            self.results.sta_imt_antenna_gain.extend(
                self.sta_imt_antenna_gain[
                    sta_active[:, np.newaxis],
                    ue,
                ].flatten(),
            )

            if len(self.imt_ap_antenna_gain):
                self.results.imt_ap_antenna_gain.extend(
                    self.imt_ap_antenna_gain[
                        ap_active[:, np.newaxis],
                        ue,
                    ].flatten(),
                )

            if len(self.imt_sta_antenna_gain):
                self.results.imt_sta_antenna_gain.extend(
                    self.imt_sta_antenna_gain[
                        sta_active[:, np.newaxis],
                        ue,
                    ].flatten(),
                )

            self.results.imt_system_path_loss.extend(
                self.imt_ap_path_loss[
                    ap_active[:, np.newaxis],
                    ue,
                ].flatten(),
            )

            self.results.imt_system_path_loss.extend(
                self.imt_sta_path_loss[
                    sta_active[:, np.newaxis],
                    ue,
                ].flatten(),
            )

            if self.param_system.channel_model == "HDFSS":
                self.results.imt_system_build_entry_loss.extend(
                    self.imt_system_build_entry_loss[:, bs],
                )
                self.results.imt_system_diffraction_loss.extend(
                    self.imt_system_diffraction_loss[:, bs],
                )

            self.results.imt_ul_ext_interf_power.extend(
                self.bs.ext_interference[bs].tolist(),
            )

            self.results.imt_ul_intra_interf_power.extend(
                self.bs.rx_interference[bs].tolist(),
            )


            self.results.imt_ul_tx_power.extend(
                self.ue.tx_power[ue].tolist(),
            )

            self.results.imt_ul_sinr.extend(
                self.bs.sinr[bs].tolist(),
            )

            self.results.imt_ul_snr.extend(
                self.bs.snr[bs].tolist(),
            )


        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)