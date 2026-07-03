# -*- coding: utf-8 -*-
"""Cosecant-squared radar antenna pattern, Recommendation ITU-R M.1851-2.

The 3-D pattern is assembled from two principal-plane cuts and the summing
method of Rec. ITU-R M.1851-2, Section 5:

    G(theta, phi) = Gmax + G_az(phi) + G_el(theta)

where G_az and G_el are NORMALIZED patterns (0 dB at the peak):

  * elevation (vertical) -- cosecant-squared ground-radar pattern, Section 2.2,
    eqs (22), (26), (27): a sin(x)/x main lobe up to theta_start, a csc^2 roll
    off from theta_start to theta_end, and a floor G0 elsewhere;
  * azimuth (horizontal) -- rectangular-aperture theoretical pattern (Table 4)
    up to the peak break point, then the PEAK side-lobe mask (Table 6); the
    taper (uniform / cosine / cosine^2) is chosen from the first side-lobe
    level.

Angles follow SHARC's convention from StationManager.get_pointing_vector_to:
phi is the azimuth about x (deg), theta is measured from the zenith (deg), so
the elevation above the horizon used by M.1851 is (90 - theta).

Default __main__ parameters correspond to Radar C of Rec. ITU-R M.1464-2.
"""
import numpy as np

from sharc.antenna.antenna import Antenna
from sharc.parameters.parameters_antenna_m1851_cosecant_squared import (
    ParametersAntennaM1851CosecantSquared,
)

# Rectangular-aperture taper table (Rec. ITU-R M.1851-2, Tables 4 and 6,
# models WITHOUT pedestal). Each entry: beamwidth factor K, mask coefficients
# (A, B), PEAK and AVERAGE break points, the constant added to convert the
# peak mask into the average mask, and the mask floor. Selection is by the
# first side-lobe level (Table 9).
_UNIFORM = dict(n=0, K=50.8, A=8.584, B=2.876,
                peak_brk=-5.75, avg_brk=-12.16, avg_off=-3.72, floor=-30.0)
_COSINE = dict(n=1, K=68.8, A=17.51, B=2.33,
               peak_brk=-14.4, avg_brk=-20.6, avg_off=-4.32, floor=-50.0)
_COSINE2 = dict(n=2, K=83.2, A=26.882, B=1.962,
                peak_brk=-22.3, avg_brk=-29.0, avg_off=-4.6, floor=-60.0)


class AntennaM1851CosecantSquared(Antenna):
    """Cosecant-squared radar antenna pattern (Rec. ITU-R M.1851-2)."""

    def __init__(self, param: ParametersAntennaM1851CosecantSquared,
                 azimuth: float = None, elevation: float = None):
        """Construct the antenna from its parameters.

        Parameters
        ----------
        param : ParametersAntennaM1851CosecantSquared
            Antenna parameters.
        azimuth : float, optional
            Physical boresight azimuth [degrees], passed by the antenna factory
            from the station geometry (single_earth_station.geometry.azimuth).
            Defaults to 0 when not provided (e.g. stand-alone use).
        elevation : float, optional
            Station geometry elevation. Ignored: a ground radar has a fixed
            cosecant-squared beam whose tilt is intrinsic (derived from
            theta_start and theta_3,el), defined in absolute elevation.
        """
        super().__init__()
        self.peak_gain = float(param.peak_gain)
        self.theta3_el = float(param.elevation_beamwidth)
        self.theta3_az = float(param.azimuth_beamwidth)
        self.csc2_start = float(param.csc2_start)
        self.csc2_end = float(param.csc2_end)
        # beam tilt derived from the cosecant geometry (M.1851 §2.2):
        # theta_start = theta_3,el/2 + tilt  ->  tilt = theta_start - theta_3,el/2
        self.tilt = self.csc2_start - self.theta3_el / 2.0

        # boresight azimuth comes from the station geometry (factory arg)
        if azimuth is not None:
            self.boresight_az = float(np.asarray(azimuth).ravel()[0])
        else:
            self.boresight_az = 0.0

        # azimuth aperture taper selected from the first side-lobe level [dB]
        sll = float(param.first_side_lobe) - self.peak_gain
        if sll >= -20.0:
            self.az_taper = _UNIFORM
        elif sll >= -30.0:
            self.az_taper = _COSINE
        else:
            self.az_taper = _COSINE2

        # peak vs average mask (M.1851 §2.1.3)
        if str(param.mask_type).lower() == "average":
            self.az_break = self.az_taper["avg_brk"]
            self.mask_offset = self.az_taper["avg_off"]
        else:
            self.az_break = self.az_taper["peak_brk"]
            self.mask_offset = 0.0

        # floors: driven by the remote side-lobe level when provided, else the
        # ITU-R M.1851 default mask floors
        if param.remote_side_lobe is not None:
            floor = float(param.remote_side_lobe) - self.peak_gain
            self.az_floor = floor
            self.el_floor = floor
            self.front_to_back = floor
        else:
            self.az_floor = self.az_taper["floor"]
            self.el_floor = -55.0
            self.front_to_back = -60.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def calculate_gain(self, *args, **kwargs) -> np.array:
        """Calculate the antenna gain towards the given directions.

        Parameters
        ----------
        phi_vec : np.array
            Azimuth angles [degrees] (about x).
        theta_vec : np.array
            Zenith angles [degrees] (0 = zenith).

        Returns
        -------
        np.array
            Gain [dBi] for each direction.
        """
        phi = np.asarray(kwargs["phi_vec"], dtype=float)
        theta = np.asarray(kwargs["theta_vec"], dtype=float)

        # local azimuth offset wrapped to [-180, 180] and elevation from horizon
        off_az = (phi - self.boresight_az + 180.0) % 360.0 - 180.0
        elevation = 90.0 - theta

        gain = self.peak_gain + self._azimuth_db(off_az) + \
            self._elevation_db(elevation)
        # global front-to-back floor
        return np.maximum(gain, self.peak_gain + self.front_to_back)

    # ------------------------------------------------------------------ #
    # Elevation cut -- cosecant-squared (M.1851 Section 2.2, ground radar)
    # ------------------------------------------------------------------ #
    def _elevation_db(self, el: np.array) -> np.array:
        """Normalized elevation pattern [dB], el = elevation above horizon."""
        el = np.asarray(el, dtype=float)
        th3, tilt = self.theta3_el, self.tilt
        th_start, th_end = self.csc2_start, self.csc2_end
        th_null = tilt - th3 / 0.88  # one-half null-to-null below the beam

        # main lobe sin(x)/x  (uniform, K = 50.8), eq (26)
        mu = np.pi * 50.8 * np.sin(np.radians(el - tilt)) / th3
        g_unif = 20.0 * np.log10(np.maximum(np.abs(_sinc(mu)), 1e-12))

        # cosecant-squared region, eq (27)
        sin_el = np.maximum(np.abs(np.sin(np.radians(el))), 1e-9)
        term1 = 20.0 * np.log10(
            np.sin(np.radians(th_start)) / sin_el,
        )
        c = np.pi * 50.8 * np.sin(np.radians(th_start - tilt)) / th3
        term2 = 20.0 * np.log10(np.maximum(np.abs(_sinc(c)), 1e-12))
        g_csc2 = term1 + term2

        g = np.full(el.shape, self.el_floor, dtype=float)
        main = (el >= th_null) & (el <= th_start)
        csc = (el > th_start) & (el <= th_end)
        g[main] = g_unif[main]
        g[csc] = g_csc2[csc]
        g = np.maximum(g, self.el_floor)
        return np.minimum(g, 0.0)

    # ------------------------------------------------------------------ #
    # Azimuth cut -- rectangular aperture + PEAK mask (M.1851 Section 2.1)
    # ------------------------------------------------------------------ #
    def _azimuth_db(self, off: np.array) -> np.array:
        """Normalized azimuth pattern [dB], off = azimuth offset from boresight."""
        off = np.asarray(off, dtype=float)
        t = self.az_taper
        th3 = self.theta3_az

        mu = np.pi * t["K"] * np.sin(np.radians(off)) / th3
        f, f0 = _aperture_F(mu, t["n"])
        theo = 20.0 * np.log10(np.maximum(np.abs(f) / f0, 1e-12))

        # side-lobe mask: -A * ln(B * |off| / theta3) + offset (0 for peak,
        # ~ -4 dB for average), limited by the floor
        off_safe = np.maximum(np.abs(off), 1e-6)
        mask = -t["A"] * np.log(t["B"] * off_safe / th3) + self.mask_offset
        mask = np.maximum(mask, self.az_floor)

        # theoretical main lobe down to the break point, then the mask.
        # Restrict the theoretical branch to the forward hemisphere: mu ~ sin(off)
        # is periodic, so |off| near 180 deg would otherwise re-create the main
        # lobe in the back direction.
        main = (np.abs(off) <= 90.0) & (theo >= self.az_break)
        g = np.where(main, theo, mask)
        return np.minimum(g, 0.0)


# ---------------------------------------------------------------------- #
# Aperture helpers
# ---------------------------------------------------------------------- #
def _sinc(mu: np.array) -> np.array:
    """sin(mu)/mu, finite at mu = 0 (note np.sinc(x) = sin(pi x)/(pi x))."""
    return np.sinc(mu / np.pi)


def _aperture_F(mu: np.array, n: int):
    """Theoretical aperture pattern F(mu) and its peak value F(0) (Table 4).

    n = 0 uniform, n = 1 cosine, n = 2 cosine-squared (without pedestal).
    """
    if n == 0:
        return _sinc(mu), 1.0
    if n == 1:
        den = (np.pi / 2.0) ** 2 - mu ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            f = (np.pi / 2.0) * np.cos(mu) / den
        f = np.where(np.abs(den) < 1e-6, 0.5, f)  # removable singularity mu=+-pi/2
        return f, 2.0 / np.pi
    # n == 2 (cosine-squared)
    den = mu * (np.pi ** 2 - mu ** 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (np.pi ** 2 / 2.0) * np.sin(mu) / den
    f = np.where(np.abs(mu) < 1e-6, 0.5, f)               # limit at mu = 0
    f = np.where(np.abs(np.pi ** 2 - mu ** 2) < 1e-6, 0.25, f)  # limit at mu=+-pi
    return f, 0.5


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path

    # Radar C, Rec. ITU-R M.1464-2 Table 1.
    #   gain = 34 dBi, elevation theta3 = 4.8 deg, azimuth theta3 = 1.45 deg,
    #   cosecant-squared "6 to +30" -> theta_start = 6 deg, theta_end = 30 deg,
    #   => tilt = theta_start - theta3/2 = 3.6 deg, theta_null = -1.855 deg;
    #   first side lobe +9.5 dBi, remote side lobe +3.5 dBi.
    par = ParametersAntennaM1851CosecantSquared(
        peak_gain=34.0,
        elevation_beamwidth=4.8,
        azimuth_beamwidth=1.45,
        csc2_start=6.0,
        csc2_end=30.0,
        first_side_lobe=9.5,
        remote_side_lobe=3.5,
        mask_type="average",
    )
    ant = AntennaM1851CosecantSquared(par)
    tilt = ant.tilt   # derived beam tilt (3.6 deg)

    # elevation cut (azimuth offset 0): sweep zenith angle so el = 90 - theta
    el = np.linspace(-10.0, 40.0, 5001)
    theta = 90.0 - el
    g_el = ant.calculate_gain(phi_vec=np.zeros_like(theta), theta_vec=theta)

    # azimuth cut at the beam peak (theta so that el = tilt)
    phi = np.linspace(-30.0, 30.0, 6001)
    theta_peak = np.full_like(phi, 90.0 - tilt)
    g_az = ant.calculate_gain(phi_vec=phi, theta_vec=theta_peak)

    print("[check] derived tilt        :", round(tilt, 3),
          "deg ; theta_null =", round(tilt - 4.8 / 0.88, 3), "deg")
    print("[check] peak gain           :", round(float(
        ant.calculate_gain(phi_vec=np.array([0.0]),
                           theta_vec=np.array([90.0 - tilt]))[0]), 2),
        "dBi (expected ~34.0)")
    print("[check] elevation max       :", round(float(np.max(g_el)), 2), "dBi")
    print("[check] gain at el=30 deg   :", round(float(
        ant.calculate_gain(phi_vec=np.array([0.0]),
                           theta_vec=np.array([60.0]))[0]), 2), "dBi")
    print("[check] gain at az=+/-180   :", round(float(
        ant.calculate_gain(phi_vec=np.array([180.0]),
                           theta_vec=np.array([90.0 - tilt]))[0]), 2),
        "dBi (= remote side lobe +3.5 dBi)")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.plot(el, g_el, "b")
    ax1.set_title("Elevation cut (cosecant-squared)")
    ax1.set_xlabel("Elevation above horizon [deg]")
    ax1.set_ylabel("Gain [dBi]")
    ax1.grid(True)
    ax2.plot(phi, g_az, "r")
    ax2.set_title("Azimuth cut (aperture + peak mask)")
    ax2.set_xlabel("Azimuth offset [deg]")
    ax2.set_ylabel("Gain [dBi]")
    ax2.grid(True)
    fig.suptitle("Rec. ITU-R M.1851 cosecant-squared antenna -- Radar C (M.1464)")
    out = Path(__file__).parent / "antenna_m1851_cosecant_squared_radarC.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"[ok] saved {out}")

    # ------------------------------------------------------------------ #
    # 2-D polar diagrams (classic radiation pattern): radial axis = gain[dBi]
    # ------------------------------------------------------------------ #
    figP = plt.figure(figsize=(13, 6))
    r_lim = (0.0, 36.0)          # radial axis in dBi
    r_ticks = [0, 10, 20, 30]

    axpe = figP.add_subplot(1, 2, 1, projection="polar")
    el_p = np.linspace(-90.0, 90.0, 3601)
    g_el_p = ant.calculate_gain(
        phi_vec=np.zeros_like(el_p), theta_vec=90.0 - el_p)
    axpe.plot(np.radians(el_p), g_el_p, "b", lw=2)
    axpe.set_theta_zero_location("E")   # 0 deg (horizon) at the right
    axpe.set_theta_direction(1)         # elevation increases upward
    axpe.set_thetamin(-90)
    axpe.set_thetamax(90)
    axpe.set_ylim(*r_lim)
    axpe.set_rticks(r_ticks)
    axpe.set_title("Vertical plane (elevation)", pad=30)

    axpa = figP.add_subplot(1, 2, 2, projection="polar")
    az_p = np.linspace(-180.0, 180.0, 7201)
    g_az_p = ant.calculate_gain(
        phi_vec=az_p, theta_vec=np.full_like(az_p, 90.0 - tilt))
    axpa.plot(np.radians(az_p), g_az_p, "r", lw=2)
    axpa.set_theta_zero_location("N")   # boresight (0 deg) at the top
    axpa.set_theta_direction(-1)        # clockwise, PPI-like
    axpa.set_ylim(*r_lim)
    axpa.set_rticks(r_ticks)
    axpa.set_title("Horizontal plane (azimuth)", pad=30)

    figP.subplots_adjust(top=0.80, wspace=0.35)
    figP.suptitle(
        "Rec. ITU-R M.1851 cosecant-squared -- Radar C polar diagrams\n"
        "(radial axis = gain in dBi; floor = remote side-lobe +3.5 dBi)",
        y=1.02, fontsize=11)
    outP = Path(__file__).parent / \
        "antenna_m1851_cosecant_squared_radarC_polar.png"
    figP.savefig(outP, dpi=150, bbox_inches="tight")
    print(f"[ok] saved {outP}")

    # ------------------------------------------------------------------ #
    # 3-D sketch: total pattern surface (summing method) + H/V plane cuts
    # ------------------------------------------------------------------ #
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (enables 3d proj.)
    from matplotlib import cm

    dyn = 40.0                      # dynamic range mapped to radius [dB]
    r_ref = par.peak_gain - dyn     # gain mapped to radius 0

    def _radius(gain):
        return np.clip(gain - r_ref, 0.0, None)

    # total-pattern surface over an azimuth x elevation grid
    az_g = np.linspace(-180.0, 180.0, 481)
    el_g = np.linspace(-90.0, 90.0, 241)
    AZ, EL = np.meshgrid(az_g, el_g)
    G = ant.calculate_gain(
        phi_vec=AZ.ravel(), theta_vec=(90.0 - EL).ravel(),
    ).reshape(AZ.shape)
    R = _radius(G)
    azr, elr = np.radians(AZ), np.radians(EL)
    Xs = R * np.cos(elr) * np.cos(azr)
    Ys = R * np.cos(elr) * np.sin(azr)
    Zs = R * np.sin(elr)
    norm = (G - G.min()) / (G.max() - G.min() + 1e-9)

    fig3 = plt.figure(figsize=(9, 8))
    ax = fig3.add_subplot(111, projection="3d")
    ax.plot_surface(
        Xs, Ys, Zs, facecolors=cm.viridis(norm), rstride=1, cstride=1,
        linewidth=0, antialiased=True, alpha=0.30, shade=False, zorder=1,
    )
    # boresight axis (x) for reference
    ax.plot([0, dyn], [0, 0], [0, 0], color="0.4", lw=1.0, ls="--", zorder=2)

    # Vertical (E/elevation) plane cut, azimuth offset = 0  (x-z plane)
    elv = np.linspace(-90.0, 90.0, 1441)
    gv = ant.calculate_gain(
        phi_vec=np.zeros_like(elv), theta_vec=90.0 - elv)
    rv = _radius(gv)
    ax.plot(rv * np.cos(np.radians(elv)), np.zeros_like(elv),
            rv * np.sin(np.radians(elv)), "b", lw=3.0, zorder=10,
            label="Vertical plane (azimuth = 0)")

    # Horizontal (azimuth) plane cut at the beam elevation (el = tilt): a cone
    azh = np.linspace(-180.0, 180.0, 2881)
    gh = ant.calculate_gain(
        phi_vec=azh, theta_vec=np.full_like(azh, 90.0 - tilt))
    rh = _radius(gh)
    ct = np.cos(np.radians(tilt))
    ax.plot(rh * ct * np.cos(np.radians(azh)),
            rh * ct * np.sin(np.radians(azh)),
            rh * np.sin(np.radians(tilt)), "r", lw=3.0, zorder=10,
            label=f"Horizontal plane (elevation = tilt = {tilt:g} deg)")

    # frame tightly around the (forward-pointing) lobe
    ax.set_xlim(-0.1 * dyn, 1.05 * dyn)
    ax.set_ylim(-0.55 * dyn, 0.55 * dyn)
    ax.set_zlim(-0.45 * dyn, 0.65 * dyn)
    ax.set_box_aspect((1.15 * dyn, 1.10 * dyn, 1.10 * dyn))
    ax.set_xlabel("x (boresight)")
    ax.set_ylabel("y")
    ax.set_zlabel("z (up)")
    ax.view_init(elev=20, azim=-62)
    ax.set_title(
        "Rec. ITU-R M.1851 cosecant-squared -- Radar C 3-D radiation sketch\n"
        f"(radius = gain - {r_ref:g} dBi, i.e. {dyn:g} dB dynamic range)")
    # label the floor "sphere" as the remote side-lobe envelope (M.1464)
    from matplotlib.patches import Patch
    floor_dbi = par.peak_gain + ant.front_to_back
    floor_proxy = Patch(
        facecolor=cm.viridis(0.0), edgecolor="none", alpha=0.5,
        label=f"floor / remote side-lobe envelope ≈ +{floor_dbi:.1f} dBi (M.1464)")
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [floor_proxy], loc="upper left", fontsize=8)
    out3 = Path(__file__).parent / "antenna_m1851_cosecant_squared_radarC_3d.png"
    fig3.savefig(out3, dpi=150, bbox_inches="tight")
    print(f"[ok] saved {out3}")

    # ------------------------------------------------------------------ #
    # Azimuth-scan animation: the lobe rotates 360 deg about the z axis.
    # The pattern is azimuthally symmetric about its boresight, so scanning
    # is just a rotation of the precomputed lobe (no re-evaluation needed).
    # ------------------------------------------------------------------ #
    try:
        from matplotlib.animation import FuncAnimation, PillowWriter

        # base lobe at boresight = 0 (coarse grid for animation speed)
        azc = np.linspace(-180.0, 180.0, 145)
        elc = np.linspace(-90.0, 90.0, 73)
        AZc, ELc = np.meshgrid(azc, elc)
        Gc = ant.calculate_gain(
            phi_vec=AZc.ravel(), theta_vec=(90.0 - ELc).ravel(),
        ).reshape(AZc.shape)
        Rc = _radius(Gc)
        azrc, elrc = np.radians(AZc), np.radians(ELc)
        X0 = Rc * np.cos(elrc) * np.cos(azrc)
        Y0 = Rc * np.cos(elrc) * np.sin(azrc)
        Z0 = Rc * np.sin(elrc)
        col = cm.viridis((Gc - Gc.min()) / (Gc.max() - Gc.min() + 1e-9))
        # base principal-plane cuts (reuse rv/elv and rh/azh from above)
        xv0, zv0 = rv * np.cos(np.radians(elv)), rv * np.sin(np.radians(elv))
        xh0 = rh * ct * np.cos(np.radians(azh))
        yh0 = rh * ct * np.sin(np.radians(azh))
        zh0 = rh * np.sin(np.radians(tilt))

        def _rot(x, y, ang):
            c, s = np.cos(ang), np.sin(ang)
            return c * x - s * y, s * x + c * y

        figA = plt.figure(figsize=(8, 7))
        axA = figA.add_subplot(111, projection="3d")

        def _update(scan):
            axA.clear()
            a = np.radians(scan)
            xr, yr = _rot(X0, Y0, a)
            axA.plot_surface(xr, yr, Z0, facecolors=col, rstride=1, cstride=1,
                             linewidth=0, antialiased=False, alpha=0.5,
                             shade=False)
            xv, yv = _rot(xv0, np.zeros_like(xv0), a)
            axA.plot(xv, yv, zv0, "b", lw=2.0)
            xh, yh = _rot(xh0, yh0, a)
            axA.plot(xh, yh, zh0, "r", lw=2.0)
            axA.plot([0, dyn * np.cos(a)], [0, dyn * np.sin(a)], [0, 0],
                     color="0.4", ls="--", lw=1.0)
            axA.set_xlim(-dyn, dyn)
            axA.set_ylim(-dyn, dyn)
            axA.set_zlim(-0.5 * dyn, 0.7 * dyn)
            axA.set_box_aspect((1.0, 1.0, 0.85))
            axA.set_xlabel("x")
            axA.set_ylabel("y")
            axA.set_zlabel("z (up)")
            axA.view_init(elev=28, azim=-60)
            axA.set_title(f"Radar C -- azimuth scan = {scan:3d} deg")

        floor_dbi = par.peak_gain + ant.front_to_back
        figA.text(0.5, 0.03,
                  f"sphere = floor / remote side-lobe envelope ≈ "
                  f"+{floor_dbi:.1f} dBi (M.1464)",
                  ha="center", fontsize=9)
        anim = FuncAnimation(figA, _update, frames=list(range(0, 360, 10)),
                             interval=90)
        out_gif = Path(__file__).parent / \
            "antenna_m1851_cosecant_squared_radarC_sweep.gif"
        anim.save(out_gif, writer=PillowWriter(fps=12))
        print(f"[ok] saved {out_gif}")
    except Exception as exc:  # pragma: no cover - animation is optional
        print(f"[warn] sweep animation skipped: {exc}")
