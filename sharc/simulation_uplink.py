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
            self.parameters, self.topology, random_number_gen,
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
            self.system.select_sta(random_number_gen, self.parameters.wifi)
            self.power_control_wifi()
            # Calculate intra wifi coupling loss 
            self.coupling_loss_wifi = self.calculate_intra_wifi_coupling_loss(
                self.system.sta, self.system.ap)
            self.calculate_sinr_wifi()
            

        self.connect_ue_to_bs()
        self.select_ue(random_number_gen)

        # Calculate coupling loss after beams are created
        self.coupling_loss_imt = self.calculate_intra_imt_coupling_loss(
            self.ue,
            self.bs,
        )
        self.scheduler()
        self.power_control()

        #self.calculate_sinr()
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
            [(ap, tx_power * np.ones(self.parameters.wifi.sta.k))
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
        Calcula o SINR de Uplink (nos APs) garantindo estrutura de vetores
        similar à simulação de Downlink.
        """
        ap_active = np.where(self.system.ap.active)[0]
        num_aps = self.system.ap.num_stations
        
        # 1. "Ajuste Downlink": Forçar que rx_interference seja um Array NumPy
        # Se não for array (ex: for None ou Dict), recria como array de zeros/piso de ruído
        # Garante que rx_power seja Array (preenche com valor muito baixo/piso)
        if not isinstance(self.system.ap.rx_power, np.ndarray):
            self.system.ap.rx_power = np.full(num_aps, -174.0)
        else:
            self.system.ap.rx_power.fill(-174.0)

        # Garante que rx_interference seja Array
        if not isinstance(self.system.ap.rx_interference, np.ndarray):
            self.system.ap.rx_interference = np.full(num_aps, -174.0)
        else:
            self.system.ap.rx_interference.fill(-174.0)

        # Garante matrizes de perda
        if not hasattr(self, 'coupling_loss_wifi'):
             self.coupling_loss_wifi = self.calculate_intra_wifi_coupling_loss(
                self.system.sta, self.system.ap)

        # Loop principal (Lógica idêntica ao Downlink, mas invertendo TX/RX)
        for ap in ap_active:
            # No Uplink, o link[ap] diz quais STAs estão enviando para este AP
            # O link retorna uma LISTA (ex: [0]), diferente do Downlink onde o índice direto funcionava
            stas_associated = self.system.link[ap]
            
            # --- A. Potência Recebida (Sinal Desejado) ---
            # Itera sobre a lista (correção do erro "unhashable type: list")
            for sta in stas_associated:
                # Verifica se o STA transmissor está ativo
                if sta in self.system.sta.tx_power:
                    # Rx = Tx - Perda
                    self.system.ap.rx_power[ap] = self.system.sta.tx_power[sta] - \
                        self.coupling_loss_wifi[sta, ap]
                    # Assume-se 1 STA transmitindo por vez (TDMA) ou soma de potências se MU-MIMO
                    break 

            # --- B. Cálculo da Interferência ---
            # Identifica STAs interferentes (todos ativos que NÃO são os meus associados)
            all_active_stas = list(self.system.sta.tx_power.keys())
            interfering_stas = [s for s in all_active_stas if s not in stas_associated]
            
            # Soma linear das interferências (mW)
            interference_linear = 0.0
            for stai in interfering_stas:
                # P_rx_interf = Tx_interf - Perda(Interf -> Meu AP)
                p_rx_dbm = self.system.sta.tx_power[stai] - self.coupling_loss_wifi[stai, ap]
                interference_linear += np.power(10, 0.1 * p_rx_dbm)

            # Converte de volta para dBm e salva no ARRAY do AP
            if interference_linear > 0:
                # Soma com o que já existia (caso haja acumulação prévia) ou substitui
                # A lógica do downlink usa soma logarítmica: 10log(10^(atual/10) + 10^(novo/10))
                # Aqui simplificamos pois já somamos tudo em 'interference_linear'
                self.system.ap.rx_interference[ap] = 10 * np.log10(interference_linear)

        # 2. "Ajuste Downlink": Garantir Largura de Banda como Array
        # Isso evita erro se bandwidth for um dict
        bw_val = self.system.ap.bandwidth
        if isinstance(bw_val, dict):
            bw_array = np.zeros(self.system.ap.num_stations)
            for k, v in bw_val.items():
                if k < len(bw_array): bw_array[k] = v
            bw_val = bw_array

        # 3. Cálculo Vetorial Final (Agora funciona pois tudo é Array)
        self.system.ap.thermal_noise = \
            10 * math.log10(BOLTZMANN_CONSTANT * self.parameters.wifi.noise_temperature * 1e3) + \
            10 * np.log10(bw_val * 1e6) + \
            self.system.ap.noise_figure

        self.system.ap.total_interference = \
            10 * np.log10(
                np.power(10, 0.1 * self.system.ap.rx_interference) +
                np.power(10, 0.1 * self.system.ap.thermal_noise),
            )

        self.system.ap.sinr = self.system.ap.rx_power - self.system.ap.total_interference
        self.system.ap.snr = self.system.ap.rx_power - self.system.ap.thermal_noise

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
            beams_bw = self.ue.bandwidth[self.link[bs]]
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore",
                                        category=RuntimeWarning,
                                        message="divide by zero encountered in log10")
                weights = self.calculate_bw_weights(
                    beams_bw,
                    self.bs.center_freq[bs],
                    float(self.param_system.bandwidth),
                    float(self.param_system.frequency),)

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
            self.coupling_loss_imt_system_adjacent_ap = \
                self.calculate_coupling_loss_system_imt(
                    self.system.ap,
                    self.bs,
                    is_co_channel=False,
                )
            self.coupling_loss_imt_system_adjacent_sta = \
                self.calculate_coupling_loss_system_imt(
                    self.system.sta,
                    self.bs,
                    is_co_channel=False,
                )

        bs_active = np.where(self.bs.active)[0]
        active_ap = np.where(self.system.ap.active)[0]
        active_sta = np.where(self.system.sta.active)[0]

        # Pré-cálculo da Densidade de Potência (dBm/MHz)
        # Power Density = Total Power (dBm) - 10*log10(Bandwidth MHz)
        dens_ap = self.parameters.wifi.ap.conducted_power - \
                  10 * np.log10(self.parameters.wifi.bandwidth)
        
        dens_sta = self.parameters.wifi.sta.conducted_power - \
                   10 * np.log10(self.parameters.wifi.bandwidth)

        for bs in bs_active:
            # Feixes ativos desta BS
            active_beams = [
                i for i in range(
                    bs * self.parameters.imt.ue.k,
                    (bs + 1) * self.parameters.imt.ue.k)]
            
            # Largura de banda de cada feixe (em MHz)
            # self.ue.bandwidth é um vetor, usamos self.link[bs] para pegar as UEs desta BS
            beams_bw_mhz = self.ue.bandwidth[self.link[bs]]
            
            # Pesos de sobreposição
            weights = self.calculate_bw_weights(
                beams_bw_mhz,
                self.bs.center_freq[bs], # Centro da freq de cada feixe
                float(self.param_system.bandwidth),
                float(self.param_system.frequency),
            )

            # --- CÁLCULO CO-CANAL ---
            in_band_interf_linear_total = np.zeros(len(active_beams))

            if self.co_channel and self.overlapping_bandwidth > 0:
                # 1. Interferência dos APs
                # P_rx (dBm) = Densidade_AP + 10log(Beam_BW_MHz) - Perda
                # CORREÇÃO: Removemos o * 1e6 e usamos densidade correta
                p_ap_dbm = dens_ap + \
                           10 * np.log10(beams_bw_mhz[:, np.newaxis]) + \
                           10 * np.log10(weights)[:, np.newaxis] - \
                           self.coupling_loss_imt_system_ap[active_beams, :][:, active_ap]
                
                # Soma linear (mW)
                in_band_interf_linear_total += np.sum(10**(0.1 * p_ap_dbm), axis=1)

                # 2. Interferência dos STAs
                p_sta_dbm = dens_sta + \
                            10 * np.log10(beams_bw_mhz[:, np.newaxis]) + \
                            10 * np.log10(weights)[:, np.newaxis] - \
                            self.coupling_loss_imt_system_sta[active_beams, :][:, active_sta]
                
                # Soma linear (mW)
                in_band_interf_linear_total += np.sum(10**(0.1 * p_sta_dbm), axis=1)

            # --- CÁLCULO OOB (Adjacente) ---
            oob_interf_linear_total = np.zeros(len(active_beams))
            
            if self.adjacent_channel:
                # Simplificação: Usando parâmetros genéricos do sistema para OOB
                # Idealmente calcularia tx_oob para AP e STA separadamente se as máscaras forem diferentes
                
                tx_oob = np.full(len(active_beams), -500.0)
                rx_oob = np.full(len(active_beams), -500.0)

                # RX OOB (ACS) - Lado do IMT BS
                if self.parameters.imt.adjacent_ch_reception == "ACS":
                    non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                    acs_dB = self.parameters.imt.bs.adjacent_ch_selectivity
                    # Usamos densidade do AP como pior caso ou referência
                    rx_oob[::] = dens_ap + 10 * np.log10(non_overlap_sys_bw) - acs_dB
                
                # TX OOB (ACLR/Mask) - Lado do WiFi
                if self.param_system.adjacent_ch_emissions == "ACLR":
                    non_overlap_imt_bw = beams_bw_mhz * (1. - weights)
                    aclr_dB = self.param_system.adjacent_ch_leak_ratio
                    # Usamos densidade do AP como referência
                    tx_oob[::] = dens_ap - aclr_dB + 10 * np.log10(non_overlap_imt_bw)
                
                # Aplicar Perdas para OOB
                # APs
                if self.param_system.adjacent_ch_emissions != "OFF":
                    tx_oob_ap = tx_oob[:, np.newaxis] - self.coupling_loss_imt_system_adjacent_ap[active_beams, :][:, active_ap]
                    oob_interf_linear_total += np.sum(10**(0.1 * tx_oob_ap), axis=1)
                
                if self.parameters.imt.adjacent_ch_reception != "OFF":
                    rx_oob_ap = rx_oob[:, np.newaxis] - self.coupling_loss_imt_system_ap[active_beams, :][:, active_ap]
                    oob_interf_linear_total += np.sum(10**(0.1 * rx_oob_ap), axis=1)

                # STAs (Repetir lógica OOB) - Simplificado somando na mesma variável
                if self.param_system.adjacent_ch_emissions != "OFF":
                    tx_oob_sta = tx_oob[:, np.newaxis] - self.coupling_loss_imt_system_adjacent_sta[active_beams, :][:, active_sta]
                    oob_interf_linear_total += np.sum(10**(0.1 * tx_oob_sta), axis=1)
                
                if self.parameters.imt.adjacent_ch_reception != "OFF":
                    rx_oob_sta = rx_oob[:, np.newaxis] - self.coupling_loss_imt_system_sta[active_beams, :][:, active_sta]
                    oob_interf_linear_total += np.sum(10**(0.1 * rx_oob_sta), axis=1)

            # --- SOMA FINAL E RESULTADO ---
            total_mW = in_band_interf_linear_total + oob_interf_linear_total
            
            # Converte para dBm (Vetor de tamanho [N_Beams])
            # CORREÇÃO: Removemos o '+ 30', pois 10*log10(mW) já é dBm
            ext_interference_dbm = np.full(len(active_beams), -174.0)
            valid_idx = total_mW > 0
            ext_interference_dbm[valid_idx] = 10 * np.log10(total_mW[valid_idx])

            # Atribui ao BS (ext_interference no Uplink é por feixe/setor)
            self.bs.ext_interference[bs] = ext_interference_dbm

            # Recalcula SINR e INR
            # SINR_Ext = S / (I_intra + I_ext + N)
            # I_total = I_intra + N (já calculado em calculate_sinr)
            # Precisamos somar linearmente I_ext
            
            i_total_linear = 10**(0.1 * self.bs.total_interference[bs]) # Intra + Noise
            i_ext_linear = 10**(0.1 * ext_interference_dbm)
            
            new_total_interference = 10 * np.log10(i_total_linear + i_ext_linear)
            
            self.bs.sinr_ext[bs] = self.bs.rx_power[bs] - new_total_interference

            # INR = I_ext - Noise
            self.bs.inr[bs] = ext_interference_dbm - self.bs.thermal_noise[bs]

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
                weights = self.calculate_bw_weights(
                    self.ue.bandwidth[ue],
                    self.ue.center_freq[ue],
                    self.param_system.bandwidth,
                    self.param_system.frequency,
                )

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
            self.coupling_loss_imt_system_adjacent_ap = \
                self.calculate_coupling_loss_system_imt(
                    self.system.ap,
                    self.ue,
                    is_co_channel=False,
                )
            self.coupling_loss_imt_system_adjacent_sta = \
                self.calculate_coupling_loss_system_imt(
                    self.system.sta,
                    self.ue,
                    is_co_channel=False,
                )

        bs_active = np.where(self.bs.active)[0]
        # Calculate for both AP and STA
        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]
        
        rx_interference_linear_ap = np.zeros(len(self.system.ap.active))
        rx_interference_linear_sta = np.zeros(len(self.system.sta.active))

        for bs in bs_active:
            ue = self.link[bs]
            # ... Calculation logic similar to calculate_external_interference but for both arrays ...
            
            # (Simplifying: Loop through UEs and accumulate interference to APs and STAs)
            # CO-CHANNEL
            if self.co_channel:
                 weights = self.calculate_bw_weights(
                    self.ue.bandwidth[ue],
                    self.ue.center_freq[ue],
                    self.param_system.bandwidth,
                    self.param_system.frequency,
                )
                 interference_ue_ap = self.ue.tx_power[ue] - self.coupling_loss_imt_system_ap[ue, ap_active]
                 rx_interference_linear_ap[ap_active] += np.sum(weights * 10**(0.1*interference_ue_ap), axis=0) # Sum over UEs? No, ue is single.
                 # Wait, loop is over BS, ue = self.link[bs] is a single UE index (scalar/int).
                 # So interference_ue_ap is [N_ap_active].
                 
                 interference_ue_sta = self.ue.tx_power[ue] - self.coupling_loss_imt_system_sta[ue, sta_active]
                 rx_interference_linear_sta[sta_active] += weights * 10**(0.1*interference_ue_sta)

            # ADJACENT CHANNEL
            if self.adjacent_channel:
                 # Calculate TX OOB (from UE)
                 # ... (Use same logic as in calculate_external_interference for tx_oob)
                 if self.parameters.imt.adjacent_ch_emissions == "SPECTRAL_MASK":
                      tx_oob = self.ue.spectral_mask.power_calc(self.param_system.frequency, self.system.bandwidth) \
                        - self.ue_power_diff[ue] + self.parameters.imt.ue.ohmic_loss
                 elif self.parameters.imt.adjacent_ch_emissions == "ACLR":
                      non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                      aclr_dB = self.parameters.imt.ue.adjacent_ch_leak_ratio
                      tx_oob = self.ue.tx_power[ue] - aclr_dB + 10 * np.log10(non_overlap_sys_bw / self.parameters.imt.bandwidth)
                 elif self.parameters.imt.adjacent_ch_emissions == "OFF":
                      tx_oob = -np.inf
                 
                 # RX OOB (at WiFi)
                 if self.param_system.adjacent_ch_reception == "ACS":
                      non_overlap_imt_bw = self.parameters.imt.bandwidth - self.overlapping_bandwidth
                      acs_dB = self.param_system.adjacent_ch_selectivity
                      rx_oob = self.ue.tx_power[ue] + 10 * np.log10(non_overlap_imt_bw / self.parameters.imt.bandwidth) - acs_dB
                 elif self.param_system.adjacent_ch_reception == "OFF":
                      rx_oob = -np.inf

                 # Apply Coupling Loss
                 # AP
                 tx_oob_ap = tx_oob - self.coupling_loss_imt_system_adjacent_ap[ue, ap_active]
                 if self.param_system.adjacent_ch_reception != "OFF":
                      rx_oob_ap = rx_oob - self.coupling_loss_imt_system_ap[ue, ap_active]
                 else:
                      rx_oob_ap = -np.inf
                 oob_lin_ap = 10**(0.1*tx_oob_ap) + 10**(0.1*rx_oob_ap)
                 rx_interference_linear_ap[ap_active] += oob_lin_ap

                 # STA
                 tx_oob_sta = tx_oob - self.coupling_loss_imt_system_adjacent_sta[ue, sta_active]
                 if self.param_system.adjacent_ch_reception != "OFF":
                      rx_oob_sta = rx_oob - self.coupling_loss_imt_system_sta[ue, sta_active]
                 else:
                      rx_oob_sta = -np.inf
                 oob_lin_sta = 10**(0.1*tx_oob_sta) + 10**(0.1*rx_oob_sta)
                 rx_interference_linear_sta[sta_active] += oob_lin_sta

        rx_interference_linear_total = np.concatenate(
            (rx_interference_linear_ap, rx_interference_linear_sta)
        )
        rx_interference_filtered = rx_interference_linear_total[rx_interference_linear_total > 0.0]   
        
        self.system.rx_interference = 10 * np.log10(rx_interference_filtered)
        
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
        self.results.system_ul_interf_power_per_mhz.extend(
            self.system.rx_interference.flatten() - 10 * math.log10(self.system.bandwidth),
        )

        ap_active = np.where(self.system.ap.active)[0]
        sta_active = np.where(self.system.sta.active)[0]
        
        # Collect WiFi Metrics (Uplink: at AP)
        for ap in ap_active:
            sta = self.system.link[ap]
            self.results.wifi_path_loss.extend(self.path_loss_wifi[sta, ap])
            self.results.wifi_coupling_loss.extend(self.coupling_loss_wifi[sta, ap])
            # Assuming antenna gain attributes populated in calculate methods if available
            # self.results.wifi_ap_antenna_gain.extend(self.ap_antenna_gain[sta, ap])

            sinr_val = self.system.ap.sinr[ap]
            self.results.wifi_ul_sinr.append(sinr_val)
            self.results.wifi_ul_snr.append(self.system.ap.snr[ap])

            # Calculate throughput for wifi
            wifi_tput = self.calculate_imt_tput(
                np.array([sinr_val]), 
                self.parameters.wifi.uplink.sinr_min,
                self.parameters.wifi.uplink.sinr_max,
                self.parameters.wifi.uplink.attenuation_factor,
            )
            self.results.wifi_ul_tput.extend(wifi_tput.tolist())

        # Collect IMT Metrics (Standard Uplink Collection)
        # Calling standard collect_results or repeating logic? 
        # Repeating relevant logic to ensure mixed results are captured if needed.
        # But mostly simpler to just call existing collection logic for IMT parts if separate.
        # However, to avoid code duplication, I will invoke the common parts or copy essential IMT logging here.
        
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
            self.results.imt_ul_inr.extend(self.bs.inr[bs].tolist())

        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)