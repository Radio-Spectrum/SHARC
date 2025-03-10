import numpy as np
from sharc.antenna.antenna import Antenna

class AntennaQuasiOmni(Antenna):
    def __init__(self, g_max, half_3db_beamwidth, sla):
        self.g_max = g_max
        self.half_3db_beamwidth = half_3db_beamwidth
        self.sla = sla

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculates the gain, which is the same for all the directions in the main lobe
        defined by the half 3dB beamwidth, and returns gain - side lobe attenuation
        for the rest of the directions.

         Parameters
        ----------
        phi_vec (np.array): azimuth angles [degrees]

        Returns
        -------
        gains (np.array): numpy array of gains
        """

        if "phi_vec" in kwargs:
            phi_vec = np.asarray(kwargs["phi_vec"])
        else:
            phi_vec = np.asarray(kwargs["off_axis_angle_vec"])

        if abs(phi_vec) <= self.half_3db_beamwidth:
            return self.g_max
        else:
            return self.g_max - self.sla

if __name__ == "__main__":
    import plotly.graph_objects as go

    # Create an instance of AntennaQuasiOmni
    antenna = AntennaQuasiOmni(g_max=10, half_3db_beamwidth=30, sla=20)

    # Define the azimuth angles
    phi_vec = np.linspace(-180, 180, 360)

    # Calculate the gains for each angle
    gains = np.array([antenna.calculate_gain(phi_vec=phi) for phi in phi_vec])

    # Create the polar plot
    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=gains,
        theta=phi_vec,
        mode='lines',
        name='Antenna Gain'
    ))

    fig.update_layout(
        title='Antenna Quasi-Omni Radiation Pattern',
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, antenna.g_max]
            )
        )
    )

    fig.show()

    # Create the x-y plot
    fig_xy = go.Figure()

    fig_xy.add_trace(go.Scatter(
        x=phi_vec,
        y=gains,
        mode='lines',
        name='Antenna Gain'
    ))

    fig_xy.update_layout(
        title='Antenna Quasi-Omni Gain vs Azimuth Angle',
        xaxis_title='Azimuth Angle (degrees)',
        yaxis_title='Gain (dB)'
    )

    fig_xy.show()