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
import sys

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
        self.calculate_external_interference_wifi()
        self.calculate_sinr_ext_wifi()

        self.collect_results_wifi(write_to_file, snapshot_number)

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

        #AP -> STA
        for ap in ap_active:
            linked_stas = self.system.link[ap]
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

                self.system.sta.rx_interference[linked_stas] = 10 * np.log10(
                    np.power(10, 0.1 * self.system.sta.rx_interference[linked_stas]) +
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
                
                self.system.ap.rx_interference[ap_victim] = 10 * np.log10(
                    np.power(10, 0.1 * self.system.ap.rx_interference[ap_victim]) +
                    np.power(10, 0.1 * interference)
                )
        #STA -> STA
        self.coupling_loss_sta_sta = self.calculate_intra_wifi_coupling_loss(self.system.sta, self.system.sta)
        for sta_victim in sta_active:
            sta_interferers = [s for s in sta_active if s != sta_victim]
            for si in sta_interferers:
                interference = self.system.sta.tx_power[si] - \
                               self.coupling_loss_sta_sta[si, sta_victim]

                self.system.sta.rx_interference[sta_victim] = 10 * np.log10(
                    np.power(10, 0.1 * self.system.sta.rx_interference[sta_victim]) +
                    np.power(10, 0.1 * interference)
                )
        

        self.system.intra_interference = np.concatenate((
            self.system.ap.rx_interference.flatten(),
            self.system.sta.rx_interference.flatten()
        ))

        self.system.thermal_noise = \
            10 * np.log10(BOLTZMANN_CONSTANT * self.param_system.noise_temperature * 1e3) + \
            10 * np.log10(self.param_system.bandwidth * 1e6) 


        self.system.ap.total_interference = 10 * np.log10(
            10 ** (0.1 * self.system.ap.rx_interference) +
            10 ** (0.1 * self.system.thermal_noise)
        )
        self.system.sta.total_interference = 10 * np.log10(
            10 ** (0.1 * self.system.sta.rx_interference) +
            10 ** (0.1 * self.system.thermal_noise)
        )
        self.system.ap.snr = self.system.ap.rx_power - self.system.ap.thermal_noise[:, np.newaxis]
        self.system.sta.snr = self.system.sta.rx_power - self.system.sta.thermal_noise  
        self.system.ap.sinr = self.system.ap.rx_power - self.system.ap.total_interference
        self.system.sta.sinr = self.system.sta.rx_power - self.system.sta.total_interference

        self.system.sinr = np.concatenate((self.system.ap.sinr.flatten(), self.system.sta.sinr.flatten()))
        self.system.snr = np.concatenate((self.system.ap.snr.flatten(), self.system.sta.snr.flatten()))

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
        """
        # 1. Calcular Perdas de Acoplamento (WiFi -> IMT BS)
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

        if self.adjacent_channel:
            sys.stderr.write(
                "The current simulation logic only supports 'co_channel' interference.\n"
                "Adjacent channel interference is not yet supported in this block.\n", )
            sys.exit(1)

        bs_active = np.where(self.bs.active)[0]
        active_ap = np.where(self.system.ap.active)[0]
        active_sta = np.where(self.system.sta.active)[0]

        for bs in bs_active:
            # Feixes ativos desta BS
            active_beams = [
                i for i in range(
                    bs * self.parameters.imt.ue.k,
                    (bs + 1) * self.parameters.imt.ue.k)]
            
            # Largura de banda de cada feixe (em MHz)
            # self.ue.bandwidth é um vetor, usamos self.link[bs] para pegar as UEs desta BS
            ue = self.link[bs]
            beams_bw_mhz = self.ue.bandwidth[ue]

            # Pesos de sobreposição (mesma lógica usada no downlink em
            # calculate_sinr_ext_wifi: overlap de banda entre cada feixe/UE
            # e a banda do sistema WIFI).
            ue_min_f = self.ue.center_freq[ue] - self.ue.bandwidth[ue] / 2
            ue_max_f = self.ue.center_freq[ue] + self.ue.bandwidth[ue] / 2

            sys_min_f = float(self.param_system.frequency) - float(self.param_system.bandwidth) / 2
            sys_max_f = float(self.param_system.frequency) + float(self.param_system.bandwidth) / 2

            overlap_bw = np.minimum(ue_max_f, sys_max_f) - np.maximum(ue_min_f, sys_min_f)

            weights = np.clip(overlap_bw / float(self.param_system.bandwidth), 0.0, 1.0)

            in_band_interf_power = np.full(len(active_beams), -500.0)
            if self.co_channel and self.overlapping_bandwidth > 0:
                # 1. Interferência dos APs
                # P_rx (dBm) = Densidade_AP + 10log(Beam_BW_MHz) - Perda
                # CORREÇÃO: Removemos o * 1e6 e usamos densidade correta
                # self.system.ap.tx_power / sta.tx_power são dicts (montados em
                # power_control_wifi), então extraímos os valores na mesma
                # ordem de active_ap/active_sta antes de indexar.
                tx_power_ap_arr = np.array([self.system.ap.tx_power[ap] for ap in active_ap])
                tx_power_sta_arr = np.array([self.system.sta.tx_power[sta] for sta in active_sta])

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
                
                total_interf_lin = interf_ap_lin + interf_sta_lin
                valid_idx = total_interf_lin > 0
                in_band_interf_power[valid_idx] = 10 * np.log10(total_interf_lin[valid_idx])
            
            oob_power = np.resize(-500., (len(active_beams), 1))
            
            total_ext_mw = 10 ** (0.1 * in_band_interf_power) + 10 ** (0.1 * oob_power)
            ext_interf_dbm = 10 * np.log10(total_ext_mw) + 30
            
            self.bs.ext_interference[bs] = ext_interf_dbm

            # Recalcula SINR Externo: S / (I_intra + I_ext + N)
            i_intra_noise_lin = 10 ** (0.1 * self.bs.total_interference[bs])
            i_ext_lin = 10 ** (0.1 * ext_interf_dbm)
            

            self.bs.sinr_ext[bs] = self.bs.rx_power[bs] - 10 * np.log10(i_intra_noise_lin + i_ext_lin)

            # Calculate INR in dB
            self.bs.thermal_noise[bs] = \
                10 * np.log10(BOLTZMANN_CONSTANT * self.parameters.imt.noise_temperature * 1e3) + \
                10 * np.log10(self.ue.bandwidth[bs] * 1e6) + self.parameters.imt.bs.noise_figure

            # INR = I_externa - Ruído Térmico
            self.bs.inr[bs] = ext_interf_dbm - self.bs.thermal_noise[bs]

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
        """
        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_reception != "OFF"
        ):
            self.coupling_loss_imt_system_ap = self.calculate_coupling_loss_system_imt(
                self.system.ap, self.ue, is_co_channel=True, )
            self.coupling_loss_imt_system_sta = self.calculate_coupling_loss_system_imt(
                self.system.sta, self.ue, is_co_channel=True, )

        if self.adjacent_channel:
            sys.stderr.write(
                "The current simulation logic only supports 'co_channel' interference.\n"
                "Adjacent channel interference is not yet supported in this block.\n", )
            sys.exit(1)

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

            if self.co_channel:
                # Pesos de sobreposição (mesma lógica usada no downlink em
                # calculate_sinr_ext_wifi: overlap de banda entre cada UE e
                # a banda do sistema WIFI).
                ue_min_f = self.ue.center_freq[ue] - self.ue.bandwidth[ue] / 2
                ue_max_f = self.ue.center_freq[ue] + self.ue.bandwidth[ue] / 2

                sys_min_f = float(self.param_system.frequency) - float(self.param_system.bandwidth) / 2
                sys_max_f = float(self.param_system.frequency) + float(self.param_system.bandwidth) / 2

                overlap_bw = np.minimum(ue_max_f, sys_max_f) - np.maximum(ue_min_f, sys_min_f)

                weights = np.clip(overlap_bw / float(self.param_system.bandwidth), 0.0, 1.0)

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

        self.system.ap.ext_interference = 10 * np.log10(rx_interference_linear_ap)
        self.system.sta.ext_interference = 10 * np.log10(rx_interference_linear_sta)

        self.system.ext_interference = np.concatenate((self.system.ap.ext_interference.flatten(), self.system.sta.ext_interference.flatten()))

        intra_ap_mw = np.power(10, 0.1 * self.system.ap.rx_interference).flatten()
        intra_sta_mw = np.power(10, 0.1 * self.system.sta.rx_interference).flatten()

        total_interf_ap_mw = intra_ap_mw
        total_interf_sta_mw = intra_sta_mw

        total_interf_ap_mw[ap_active] += rx_interference_linear_ap[ap_active]
        total_interf_sta_mw[sta_active] += rx_interference_linear_sta[sta_active]

        self.system.rx_interference = np.concatenate((
            10 * np.log10(total_interf_ap_mw), 
            10 * np.log10(total_interf_sta_mw)
        ))

        # calculate N (and INR)
        self.system.thermal_noise = \
            10 * np.log10(
                BOLTZMANN_CONSTANT *
                self.system.noise_temperature * 1e3,
            ) + \
            10 * math.log10(self.param_system.bandwidth * 1e6)

        self.system.inr = np.array(
            [self.system.rx_interference - self.system.thermal_noise],
        )

    def collect_results(self, write_to_file: bool, snapshot_number: int):
        """
        Collect and store results for the current uplink simulation snapshot.

        Args:
            write_to_file (bool): Whether to write results to file.
            snapshot_number (int): The current snapshot number.
        """
        if not self.parameters.imt.interfered_with and np.any(self.bs.active):
            self.results.system_inr.extend(self.system.inr.tolist())
            self.results.system_ul_interf_power.extend(
                [self.system.rx_interference],
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

        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)
    
    def collect_results_wifi(self, write_to_file: bool, snapshot_number: int):
        """
        Collect and store results for the current uplink simulation snapshot when using WiFi.
        """

        self.results.wifi_ul_inr.extend(self.system.inr.flatten())
        self.results.system_ul_interf_power.extend(
            self.system.rx_interference.flatten(),
        )

        self.results.system_intra_ul_interf_power.extend(
            self.system.intra_interference.flatten(),
        )
        self.results.system_ext_ul_interf_power.extend(
            self.system.ext_interference.flatten(),
        )

        self.results.system_ul_interf_power_per_mhz.extend(
            self.system.rx_interference.flatten() - 10 * math.log10(self.system.bandwidth),
        )

        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]

        offset_sta_start = self.system.ap.sinr.size
        # Cria cópia para não alterar a simulação em andamento
        global_sinr_clean = np.array(self.system.sinr, copy=True)
        global_snr_clean  = np.array(self.system.snr, copy=True)

        # Aplica Teto (Hardware Limit: 45 dB)
        global_sinr_clean = np.clip(global_sinr_clean, a_min=None, a_max=45.0)
        global_snr_clean  = np.clip(global_snr_clean,  a_min=None, a_max=45.0)

        # Aplica Piso (Remover Mortos/Erros: -120 dB)
        global_sinr_clean[global_sinr_clean < -120] = -120.0
        global_snr_clean[global_snr_clean < -120]   = -120.0
        
        # Collect WiFi Metrics (Uplink: at AP)
        for ap in ap_active:
            sta_indices = np.atleast_1d(self.system.link[ap]).astype(int)
            sta = self.system.link[ap]
            # Coleta resultados básicos do WiFi
            self.results.wifi_path_loss.extend(self.path_loss_wifi[ap, sta])
            self.results.wifi_coupling_loss.extend(self.coupling_loss_wifi[ap, sta])
            self.results.wifi_ap_antenna_gain.extend(self.ap_antenna_gain[ap, sta])
            self.results.wifi_sta_antenna_gain.extend(self.sta_antenna_gain[ap, sta])

            # NOTA: bloco de val_ul_sinr/val_dl_sinr baseado em offset_sta_start
            # foi desativado aqui, igual ao downlink - self.system.sinr/.snr só
            # têm o tamanho do número de APs+STAs ATIVOS no snapshot, não do
            # índice bruto da STA (sta_indices), o que causava IndexError.
            '''val_ul_sinr = global_sinr_clean[ap]
            val_ul_sinr = np.repeat(val_ul_sinr, len(sta_indices))
            
            val_ul_snr  = global_snr_clean[ap]
            val_ul_snr  = np.repeat(val_ul_snr, len(sta_indices))

            # 3. DOWNLINK (STA) - RECUPERAÇÃO COM OFFSET
            # Agora funciona: array([0, 5]) + 100 = array([100, 105])
            # IMPORTANTE: Use 'sta_indices' aqui, NÃO use 'sta'
            val_dl_sinr = global_sinr_clean[offset_sta_start + sta_indices]
            val_dl_snr  = global_snr_clean[offset_sta_start + sta_indices]

            # 4. CONCATENAÇÃO
            # Junta o que a STA ouviu com o que o AP ouviu
            link_sinr = np.concatenate((val_dl_sinr, val_ul_sinr))
            link_snr  = np.concatenate((val_dl_snr, val_ul_snr))

            # 5. SALVA NOS RESULTADOS
            self.results.wifi_dl_sinr.extend(link_sinr.tolist())
            self.results.wifi_dl_snr.extend(link_snr.tolist())'''
        
            #Calculate throughput for wifi
            wifi_tput = self.calculate_imt_tput(
                self.system.sta.sinr[sta],
                self.parameters.wifi.downlink.sinr_min,
                self.parameters.wifi.downlink.sinr_max,
                self.parameters.wifi.downlink.attenuation_factor,
            )
            self.results.wifi_dl_tput.extend(wifi_tput.tolist())
        
        bs_active = np.where(self.bs.active)[0]
        for bs in bs_active:
            ue = self.link[bs]
            self.results.imt_path_loss.extend(self.path_loss_imt[bs, ue])
            self.results.imt_coupling_loss.extend(
                self.coupling_loss_imt[bs, ue],
            )
            
            tput = self.calculate_imt_tput(
                self.bs.sinr[bs],
                self.parameters.imt.uplink.sinr_min,
                self.parameters.imt.uplink.sinr_max,
                self.parameters.imt.uplink.attenuation_factor,
            )
            self.results.imt_ul_tput.extend(tput.tolist())
            self.results.imt_ul_sinr.extend(self.bs.sinr[bs].tolist())
            self.results.imt_ul_inr.extend(self.bs.inr[bs].tolist()[0])
            self.results.imt_ul_ext_interf_power.extend(self.bs.ext_interference[bs].tolist()[0])

        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)