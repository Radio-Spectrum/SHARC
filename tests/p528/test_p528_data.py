import os
import re
import numpy as np
from glob import glob
from sharc.propagation.propagation_p528 import PropagationP528
import time


def run_p528_tests():
    """Run validation tests for P528 propagation model using reference data tables."""

    # Initialize random number generator with fixed seed for reproducibility
    random_number_gen = np.random.RandomState(101)

    # Create P528 propagation model instance
    p528_model = PropagationP528(random_number_gen)

    # Define paths to search for data files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [os.path.join(current_dir, "Data Tables")]

    # Debug prints
    print(f"Current directory: {current_dir}")
    print(f"Search paths: {paths}")

    cnt_fail = 0
    cnt_pass = 0

    start_time = time.time()

    for path_index in paths:
        print(f"Searching in path: {path_index}")
        print(f"Path exists: {os.path.exists(path_index)}")

        filenames = glob(os.path.join(path_index, "*.csv"))
        datanumber = len(filenames)

        print(f"Found {datanumber} CSV files")

        if datanumber == 0:
            continue

        for ii, filename in enumerate(filenames, 1):
            print("*" * 47)
            print(f" Processing file {ii}/{datanumber}: {filename} ...")
            print("*" * 47)

            with open(filename, "r") as fid:
                # First line contains frequency and time percentage
                readLine = fid.readline().strip()
                rgx = r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?"
                dummy = re.findall(rgx, readLine)
                freq_mhz = float(dummy[0])
                time_percentage = float(dummy[1])

                # h2 values (heights for second terminal)
                readLine = fid.readline().strip()
                dummy = readLine.split(",")
                h2 = [float(x) for x in dummy[2:-3]]

                # h1 values (heights for first terminal)
                readLine = fid.readline().strip()
                dummy = readLine.split(",")
                h1 = [float(x) for x in dummy[2:-3]]

                fid.readline()  # Skip header line

                print(f'{"PYTHON":>20} {"REF TABLE":>20} {"DELTA":>20}')

                # Read distance and loss values
                D, FSL, tl_ref = [], [], []
                for line in fid:
                    dummy = line.strip().split(",")
                    D.append(float(dummy[0]))
                    FSL.append(float(dummy[1]))
                    tl_ref.append([float(x) for x in dummy[2:-3]])

            # Convert to numpy arrays for processing
            D = np.array(D)
            tl_ref = np.array(tl_ref)

            # Test each distance/height combination
            for i in range(0, len(D)):
                for j in range(len(h1)):
                    # Setup input arrays for get_loss
                    distance_km = np.array([D[i]])
                    frequency_mhz = np.array([freq_mhz])
                    h1_meter = h1[j]
                    h2_meter = h2[j]

                    # Call get_loss with explicit time percentage and horizontal polarization
                    try:
                        result = p528_model.get_loss(
                            distance_km,
                            h1_meter,
                            h2_meter,
                            frequency_mhz,
                            time_percentage=time_percentage * 100,
                            polarization=0,  # horizontal polarization
                        )

                        # Compare results (rounded to 1 decimal place)
                        delta = round(10.0 * (result[0] - tl_ref[i, j])) / 10.0

                        if abs(delta) > 0.1:
                            cnt_fail += 1
                            print(
                                f"{result[0]:20.1f} {tl_ref[i, j]:20.1f} {delta:20.1f} FAIL"
                            )
                        else:
                            cnt_pass += 1
                            print(
                                f"{result[0]:20.1f} {tl_ref[i, j]:20.1f} {delta:20.1f} PASS"
                            )

                    except Exception as e:
                        print(f"Error processing d={D[i]}km, h1={h1[j]}m, h2={h2[j]}m")
                        print(f"Error details: {str(e)}")
                        cnt_fail += 1

    end_time = time.time()
    elapsed_time = end_time - start_time

    if cnt_pass + cnt_fail == 0:
        print("\nNo tests were run! Please check your data paths and files.")
    else:
        print("\nTest Summary:")
        print("=" * 40)
        print(f"Total tests: {cnt_pass + cnt_fail}")
        print(f"Passed: {cnt_pass}")
        print(f"Failed: {cnt_fail}")
        print(f"Pass rate: {(cnt_pass / (cnt_pass + cnt_fail)) * 100:.1f}%")
        print(f"Time taken: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    run_p528_tests()
