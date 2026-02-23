"""Utility to generate ITU-R P.619 atmospheric attenuation lookup tables."""

import argparse
import csv
import os

import numpy as np

from sharc.propagation.propagation_p619 import PropagationP619


def update_locations_file(dataset_dir: str, city_name: str, latitude_deg: float):
    """Ensure locations.csv contains a row mapping the latitude to city_name."""
    locations_file = os.path.join(dataset_dir, "locations.csv")

    rows = []
    found_same_lat = False

    if os.path.exists(locations_file):
        with open(locations_file, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                rows.append(row)
                if abs(float(row["Latitude"]) - latitude_deg) < 1e-10:
                    row["Cidade"] = city_name
                    found_same_lat = True

    if not found_same_lat:
        rows.append({"Cidade": city_name, "Latitude": f"{latitude_deg:.4f}"})

    with open(locations_file, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Cidade", "Latitude"])
        writer.writeheader()
        writer.writerows(rows)


def generate_lookup_table(
    *,
    city_name: str,
    frequency_mhz: float,
    earth_station_alt_m: float,
    earth_station_lat_deg: float,
    season: str,
    mean_clutter_height: str,
    below_rooftop: float,
    elevation_min_deg: float,
    elevation_max_deg: float,
    elevation_step_deg: float,
    progress_every: int,
):
    """Generate one atmospheric attenuation lookup table for P.619."""
    dataset_dir = os.path.dirname(__file__)

    update_locations_file(dataset_dir, city_name, earth_station_lat_deg)

    random_number_gen = np.random.RandomState(101)
    propagation = PropagationP619(
        random_number_gen=random_number_gen,
        earth_station_alt_m=earth_station_alt_m,
        earth_station_lat_deg=earth_station_lat_deg,
        season=season,
        mean_clutter_height=mean_clutter_height,
        below_rooftop=below_rooftop,
    )

    apparent_elevation = np.arange(
        elevation_min_deg,
        elevation_max_deg + 1e-9,
        elevation_step_deg,
    )
    losses = []
    total = len(apparent_elevation)
    for idx, elevation in enumerate(apparent_elevation, start=1):
        loss = propagation._get_atmospheric_gasses_loss(
            frequency_MHz=frequency_mhz,
            apparent_elevation=float(elevation),
            lookupTable=False,
        )
        losses.append(float(loss))
        if progress_every > 0 and (idx % progress_every == 0 or idx == total):
            print(
                f"[{city_name} {int(frequency_mhz)} MHz] progress: {idx}/{total} elevations",
                flush=True,
            )

    output_file = os.path.join(
        dataset_dir,
        f"{city_name}_{int(frequency_mhz)}_{int(earth_station_alt_m)}m.csv",
    )

    with open(output_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["apparent_elevation", "loss"])
        for elevation, loss in zip(apparent_elevation, losses):
            writer.writerow([f"{elevation:.1f}", f"{loss:.12f}"])

    print(f"Results saved to {output_file}")


def parse_args():
    """Parse command-line arguments for lookup table generation."""
    parser = argparse.ArgumentParser(
        description="Generate ITU-R P.619 atmospheric attenuation lookup table.",
    )
    parser.add_argument("--city", default="ASUNCION")
    parser.add_argument("--frequency-mhz", type=float, default=2162.5)
    parser.add_argument("--frequencies-mhz", type=float, nargs="+", default=None)
    parser.add_argument("--earth-station-alt-m", type=float, default=200.0)
    parser.add_argument("--earth-station-lat-deg", type=float, default=-25.2637)
    parser.add_argument("--season", choices=["SUMMER", "WINTER"], default="SUMMER")
    parser.add_argument("--mean-clutter-height", choices=["low", "mid", "high"], default="low")
    parser.add_argument("--below-rooftop", type=float, default=0.0)
    parser.add_argument("--elevation-min-deg", type=float, default=0.0)
    parser.add_argument("--elevation-max-deg", type=float, default=90.0)
    parser.add_argument("--elevation-step-deg", type=float, default=1.0)
    parser.add_argument("--progress-every", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    frequencies_mhz = args.frequencies_mhz or [args.frequency_mhz]
    for frequency_mhz in frequencies_mhz:
        generate_lookup_table(
            city_name=args.city,
            frequency_mhz=frequency_mhz,
            earth_station_alt_m=args.earth_station_alt_m,
            earth_station_lat_deg=args.earth_station_lat_deg,
            season=args.season,
            mean_clutter_height=args.mean_clutter_height,
            below_rooftop=args.below_rooftop,
            elevation_min_deg=args.elevation_min_deg,
            elevation_max_deg=args.elevation_max_deg,
            elevation_step_deg=args.elevation_step_deg,
            progress_every=args.progress_every,
        )
