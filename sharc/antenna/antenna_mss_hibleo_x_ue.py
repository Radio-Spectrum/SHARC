
# -*- coding: utf-8 -*-
"""Antenna model for HibleoX MSS UE in the 2.5GHz frequency band."""
from sharc.antenna.antenna import Antenna

import numpy as np

# The filing does not provide an antenna model, but a set of points.
# We interpolate these points to create a continuous function.
# The points are taken from the filing.
data_str = """
x, y
0, 2.7
10, 2.6566311598597308
20, 2.431925804835606
30, 2.150602473172147
40, 1.6546431302238513
50, 0.9929370896722656
60, 0.0904942389326866
70, -0.9031468347087825
80, -2.386785139873968
90, -3.679459224299312
"""

HALF_BEAM_WIDTH_DEG = 64.0


class AntennaMssHibleoXUe(Antenna):
    """
    Implements the MSS UE antenna pattern provided for the HIBLEO-X system in it's filings.

    This is provided as a reference antenna pattern in document Document 4C/166-E - 30 September 2024.
    This is valid only for frequencies around 2.45 GHz.
    """

    def __init__(self, frequency_MHz: float):
        """
        Initialize the AntennaMSSAdjacent class.

        Parameters
        ----------
        frequency_MHz : float
            Frequency in MHz for the antenna model.
        """
        super().__init__()
        if frequency_MHz < 2483 or frequency_MHz > 2500:
            raise ValueError("This antenna model is only valid for frequencies around 2.45 GHz")
        self.frequency = frequency_MHz

        # Parse the data string to extract x and y values
        lines = data_str.strip().split('\n')[1:]
        self.pattern_theta_deg = np.array([float(line.split(',')[0]) for line in lines])
        self.patten_gain_dbi = np.array([float(line.split(',')[1]) for line in lines])

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate the antenna gain for the given off-axis angles.

        Parameters
        ----------
        *args : tuple
            Positional arguments (not used).
        **kwargs : dict
            Keyword arguments, expects 'off_axis_angle_vec' in degrees as input.

        Returns
        -------
        np.array
            Calculated antenna gain values.
        """
        theta_deg = kwargs["off_axis_angle_vec"]
        return -2.5226404 * (np.deg2rad(theta_deg) ** 2) + 2.7


if __name__ == '__main__':
    import plotly.graph_objects as go
    from scipy.optimize import curve_fit

    # Compare the fitted parabolic function to the provided points

    mss_ue_antenna = AntennaMssHibleoXUe(2483)

    # Define the custom parabolic function without the linear term
    def poly_no_linear(x, a):
        """
        Polynomial function of the form ax^2 + c (no linear term).
        """
        return a * x**2 + np.max(mss_ue_antenna.patten_gain_dbi)

    # Fit the data using curve_fit
    # initial_guess = [1, 1] # Optional: provide an initial guess for the parameters
    params, covariance = curve_fit(
        poly_no_linear,
        np.deg2rad(mss_ue_antenna.pattern_theta_deg),
        mss_ue_antenna.patten_gain_dbi
    )

    print("Fitting parabolic function (no linear term) to the provided points:")
    print(f"Fitted parameters:\na={params}")
    print(f"Covariance matrix:\n{covariance}")

    off_axis_vec_deg = np.linspace(-90, 90, 100)
    gains = mss_ue_antenna.calculate_gain(off_axis_angle_vec=off_axis_vec_deg)

    gains_interp = np.interp(
        np.abs(off_axis_vec_deg),
        mss_ue_antenna.pattern_theta_deg,
        mss_ue_antenna.patten_gain_dbi
    )

    fig = go.Figure(data=go.Scatter(x=off_axis_vec_deg, y=gains, mode='markers+lines', name='Parabolic Fit pattern'))
    fig.update_layout(
        title='Hibleo-X UE pattern from filing',
        xaxis_title='off-axis angle (degrees)',
        yaxis_title='Gain (dBi)',
        template="plotly_white"
    )
    fig.update_yaxes(
        linewidth=1,
        linecolor='black',
        mirror=True,
        ticks='inside',
        showline=True,
        gridcolor="#DCDCDC",
        gridwidth=1.5,
    )
    fig.add_trace(go.Scatter(x=off_axis_vec_deg, y=gains_interp, mode='markers', name='Interpolated'))
    fig.show()
