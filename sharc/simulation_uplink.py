# -*- coding: utf-8 -*-
"""
Created on Fri Apr  7 17:02:35 2017

@author: edgar
"""

import numpy as np
import math

from sharc.simulation import Simulation
from sharc.parameters.parameters import Parameters
from sharc.station_factory import StationFactory
from sharc.parameters.constants import BOLTZMANN_CONSTANT

testasnoasa = 0

class SimulationUplink(Simulation):
    """
    Implements the flowchart of simulation downlink method
    """

    def __init__(self, parameters: Parameters, parameter_file: str):
        super().__init__(parameters, parameter_file)

    def snapshot(self, *args, **kwargs):
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
            self.parameters.imt.ue.antenna.array,
            self.topology, random_number_gen,
        )
        # self.plot_scenario()

        # from sharc.satellite.scripts.plot_3d_param_file import plot_globe_with_borders
        # import plotly.graph_objects as go

        # fig = plot_globe_with_borders(True, self.geometry_converter)

        # fig.add_trace(go.Scatter3d(
        #     x=self.bs.x / 1,
        #     y=self.bs.y / 1,
        #     z=self.bs.z / 1,
        #     mode='markers',
        #     marker=dict(size=2, color='black', opacity=0.5),
        #     showlegend=False
        # ))
        # fig.add_trace(go.Scatter3d(
        #     x=self.ue.x / 1,
        #     y=self.ue.y / 1,
        #     z=self.ue.z / 1,
        #     mode='markers',
        #     marker=dict(size=2, color='blue', opacity=0.5),
        #     showlegend=False
        # ))
        # fig.add_trace(go.Scatter3d(
        #     x=self.system.x[self.system.active] / 1,
        #     y=self.system.y[self.system.active] / 1,
        #     z=self.system.z[self.system.active] / 1,
        #     mode='markers',
        #     marker=dict(size=8, color='red', opacity=0.5),
        #     showlegend=False
        # ))
        # global testasnoasa
        # fig.update_layout(
        #     scene=dict(
        #         zaxis=dict(
        #             range=(-1e3*5000, 1e3*5000)
        #         ),
        #         yaxis=dict(
        #             range=(-1e3*5000, 1e3*5000)
        #         ),
        #         xaxis=dict(
        #             range=(-1e3*5000, 1e3*5000)
        #         ),
        #         camera=dict(
        #             eye=dict(x=0,y=0,z=1),
        #             # up=dict(x=-1, y=0., z=0),
        #         )
        #     ),
        #     template="plotly_white",
        #     title=f"MSS as System ({testasnoasa})"
        # )
        # mss_d2d = self.system
        # from sharc.support.sharc_geom import polar_to_cartesian
        # boresight_length = 100*1e3  # Length of the boresight vectors for visualization
        # boresight_x, boresight_y, boresight_z = polar_to_cartesian(
        #     boresight_length,
        #     mss_d2d.azimuth[mss_d2d.active],
        #     mss_d2d.elevation[mss_d2d.active],
        # )
        # # Add arrow heads to the end of the boresight vectors
        # for x, y, z, bx, by, bz in zip(mss_d2d.x[mss_d2d.active] / 1,
        #                                mss_d2d.y[mss_d2d.active] / 1,
        #                                mss_d2d.z[mss_d2d.active] / 1,
        #                                boresight_x,
        #                                boresight_y,
        #                                boresight_z):
        #     fig.add_trace(go.Cone(
        #         x=[x + bx],
        #         y=[y + by],
        #         z=[z + bz],
        #         u=[bx],
        #         v=[by],
        #         w=[bz],
        #         colorscale=[[0, 'orange'], [1, 'orange']],
        #         sizemode='absolute',
        #         sizeref=40*1e3,
        #         showscale=False
        #     ))
        # for x, y, z, bx, by, bz in zip(mss_d2d.x[mss_d2d.active] / 1,
        #                                mss_d2d.y[mss_d2d.active] / 1,
        #                                mss_d2d.z[mss_d2d.active] / 1,
        #                                boresight_x,
        #                                boresight_y,
        #                                boresight_z):
        #     fig.add_trace(go.Scatter3d(
        #         x=[x, x + bx],
        #         y=[y, y + by],
        #         z=[z, z + bz],
        #         mode='lines',
        #         line=dict(color='orange', width=2),
        #         name='Boresight'
        #     ))
        # testasnoasa+=1
        # if testasnoasa ==1:
        #     # fig.write_image(f"imgs/MSS_as_System/{testasnoasa}.webp", width=1200, height=1200)
        #     fig.show()
        #     exit()

        self.connect_ue_to_bs()
        self.select_ue(random_number_gen)

        # Calculate coupling loss after beams are created
        self.coupling_loss_imt = self.calculate_intra_imt_coupling_loss(
            self.ue,
            self.bs,
        )
        self.scheduler()
        self.power_control()

        if self.parameters.imt.interfered_with:
            # Execute this piece of code if the other system generates
            # interference into IMT
            self.calculate_sinr()
            self.calculate_sinr_ext()
        else:
            # Execute this piece of code if IMT generates interference into
            # the other system
            self.calculate_sinr()
            self.calculate_external_interference()

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

            # print("##### HERE:")

            # exit()

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

    def calculate_sinr_ext(self):
        """
        Calculates the uplink SINR for each BS taking into account the
        interference that is generated by the other system into IMT system.
        """
        self.coupling_loss_imt_system = \
            self.calculate_coupling_loss_system_imt(
                self.system,
                self.bs)

        in_band_interf = -500
        if self.co_channel:
            if self.overlapping_bandwidth > 0:
                # Inteferer transmit power in dBm over the overlapping band (MHz)
                in_band_interf = self.param_system.tx_power_density + \
                    10 * np.log10(self.overlapping_bandwidth * 1e6) + 30

                # print("in_band_interf", in_band_interf)
        oob_power = -500
        oob_interf_lin = 0
        if self.adjacent_channel:
            if self.parameters.imt.adjacent_interf_model == "SPECTRAL_MASK":
                # Out-of-band power in the adjacent channel.
                oob_power = self.system.spectral_mask.power_calc(self.parameters.imt.frequency,
                                                                 self.parameters.imt.bandwidth)
                oob_interf_lin = np.power(10, 0.1 * oob_power) / \
                    np.power(10, 0.1 * self.parameters.imt.bs_adjacent_ch_selectivity)
            elif self.parameters.imt.adjacent_interf_model == "ACIR":
                acir = -10 * np.log10(10**(-self.param_system.adjacent_ch_leak_ratio / 10) +
                                      10**(-self.parameters.imt.bs_adjacent_ch_selectivity / 10))
                oob_power = self.param_system.tx_power_density + \
                    10 * np.log10(self.param_system.bandwidth * 1e6) -  \
                    acir + 30
                oob_interf_lin = 10**(oob_power / 10)
        
        ext_interference = 10 * np.log10(np.power(10, 0.1 * in_band_interf) + oob_interf_lin)

        bs_active = np.where(self.bs.active)[0]
        sys_active = np.where(self.system.active)[0]
        for bs in bs_active:
            active_beams = \
                [i for i in range(bs * self.parameters.imt.ue.k, (bs + 1) * self.parameters.imt.ue.k)]
            
            # Interference for each active system transmitter
            bs_ext_interference = ext_interference - \
                self.coupling_loss_imt_system[active_beams, :][:, sys_active]
            # print("self.coupling_loss_imt_system[active_beams, :][:, sys_active]", self.coupling_loss_imt_system[active_beams, :][:, sys_active])
            # Sum all the interferers for each bs
            self.bs.ext_interference[bs] = 10 * np.log10(np.sum(np.power(10, 0.1 * bs_ext_interference), axis=1))

            self.bs.sinr_ext[bs] = self.bs.rx_power[bs] \
                - (10 * np.log10(np.power(10, 0.1 * self.bs.total_interference[bs]) +
                                 np.power(10, 0.1 * self.bs.ext_interference[bs],),))
            self.bs.inr[bs] = self.bs.ext_interference[bs] - \
                self.bs.thermal_noise[bs]
        # print("self.system.tx_power", self.system.tx_power)
        # print("self.bs.inr", self.bs.inr)
        # print("self.bs.ext_interference", self.bs.ext_interference)
        # print("self.bs.thermal_noise", self.bs.thermal_noise)
        # print("## ended uplink")
        # exit()
        # global testasnoasa
        # testasnoasa += 1
        # if testasnoasa == 5:
        #     exit()

    def calculate_external_interference(self):
        """
        Calculates interference that IMT system generates on other system
        """

        if self.co_channel:
            self.coupling_loss_imt_system = self.calculate_coupling_loss_system_imt(
                self.system,
                self.ue,
                is_co_channel=True,
            )
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
                if self.overlapping_bandwidth:
                    acs = 0
                    weights = self.calculate_bw_weights(
                        self.ue.bandwidth[ue],
                        self.ue.center_freq[ue],
                        self.param_system.bandwidth,
                        self.param_system.frequency,
                    )
                else:
                    acs = self.param_system.adjacent_ch_selectivity
                    weights = np.ones(self.parameters.imt.ue.k)

                interference_ue = self.ue.tx_power[ue] - \
                    self.coupling_loss_imt_system[ue, sys_active]
                rx_interference += np.sum(
                    weights * np.power(
                        10,
                        0.1 * interference_ue,
                    ),
                ) / 10**(acs / 10.)

            if self.adjacent_channel:
                # The unwanted emission is calculated in terms of TRP (after
                # antenna). In SHARC implementation, ohmic losses are already
                # included in coupling loss. Then, care has to be taken;
                # otherwise ohmic loss will be included twice.
                oob_power = self.ue.spectral_mask.power_calc(self.param_system.frequency, self.system.bandwidth)\
                    - self.ue_power_diff[ue] \
                    + self.parameters.imt.ue.ohmic_loss
                oob_interference_array = oob_power - self.coupling_loss_imt_system_adjacent[ue, sys_active] \
                    + 10 * np.log10(
                        (self.param_system.bandwidth - self.overlapping_bandwidth) /
                        self.param_system.bandwidth)
                rx_interference += np.sum(
                    np.power(10, 0.1 * oob_interference_array,))

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
        if hasattr(self.system.antenna[0], "effective_area") and self.system.num_stations == 1:
            self.system.pfd = 10 * \
                np.log10(
                    10**(self.system.rx_interference / 10) /
                    self.system.antenna[0].effective_area,
                )

    def collect_results(self, write_to_file: bool, snapshot_number: int):
        if not self.parameters.imt.interfered_with and np.any(self.bs.active):
            self.results.system_inr.extend(self.system.inr.tolist())
            self.results.system_ul_interf_power.extend(
                [self.system.rx_interference],
            )
            # TODO: generalize this a bit more if needed
            if hasattr(self.system.antenna[0], "effective_area") and self.system.num_stations == 1:
                self.results.system_pfd.extend([self.system.pfd])

        self.results.system_to_bs_dist.extend(self.dist_from_imt_to_sys.flatten())
        self.results.visible_sats.append(np.sum(self.system.active))
        sys_active = np.where(self.system.active)[0]

        bs_active = np.where(self.bs.active)[0]
        self.results.sat_elevation.extend(
            self.bs.get_elevation(self.system)[np.ix_(bs_active, sys_active)].flatten()
        )
        self.results.sat_es_off_axis.extend(
            self.system.get_off_axis_angle(self.bs)[np.ix_(sys_active, bs_active)].flatten()
        )

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
                self.results.sat_es_off_axis.extend(
                    self.system.get_off_axis_angle(self.bs)[np.ix_(sys_active, bs_active)].flatten()
                )
                self.results.system_inr.extend(self.bs.inr[bs])
                self.results.sat_gain = self.results.system_imt_antenna_gain
                if self.param_system.channel_model == "HDFSS":
                    self.results.imt_system_build_entry_loss.extend(
                        self.imt_system_build_entry_loss[np.ix_(sys_active, active_beams)],
                    )
                    self.results.imt_system_diffraction_loss.extend(
                        self.imt_system_diffraction_loss[np.ix_(sys_active, active_beams)],
                    )
            else:
                self.results.system_imt_antenna_gain.extend(
                    self.system_imt_antenna_gain[np.ix_(sys_active, ue)],
                )
                self.results.imt_system_antenna_gain.extend(
                    self.imt_system_antenna_gain[np.ix_(sys_active, ue)],
                )
                self.results.imt_system_path_loss.extend(
                    self.imt_system_path_loss[np.ix_(sys_active, ue)],
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
