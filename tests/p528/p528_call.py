import numpy as np
from sharc.propagation.propagation_p528 import PropagationP528


def test_p528_variations():
    """Test different ways of calling P528 propagation model."""

    # Initialize random number generator with fixed seed for reproducibility
    random_number_gen = np.random.RandomState(101)

    # Create P528 propagation model instance
    p528_model = PropagationP528(random_number_gen)

    print("Testing P528 Model with Various Input Types")
    print("=" * 50)

    # Test Case 1: Single Value Test
    print("\n1. Single Value Test")
    print("-" * 30)
    distance = np.array([100.0])  # 100 km
    h1 = 1.5  # meters
    h2 = 20000.0  # meters
    frequency = np.array([4000.0])  # MHz

    result = p528_model.get_loss(distance, h1, h2, frequency)
    print(f"Single value test result: {result[0]:.2f} dB")

    # Test Case 2: Vector of Distances
    print("\n2. Distance Vector Test")
    print("-" * 30)
    distances = np.array([10.0, 50.0, 100.0, 500.0, 1000.0])
    frequency = np.array([4000.0]) * np.ones(distances.shape)

    results = p528_model.get_loss(distances, h1, h2, frequency)
    for d, r in zip(distances, results):
        print(f"Distance: {d:6.1f} km -> Loss: {r:.2f} dB")

    # Test Case 3: Different Time Percentages
    print("\n3. Time Percentage Variations")
    print("-" * 30)
    distance = np.array([100.0])
    frequency = np.array([4000.0])
    time_percentages = [1, 10, 50, 90, 99]

    for p in time_percentages:
        result = p528_model.get_loss(distance, h1, h2, frequency, time_percentage=p)
        print(f"Time {p:3d}% -> Loss: {result[0]:.2f} dB")

    # Test Case 4: Different Polarizations
    print("\n4. Polarization Test")
    print("-" * 30)
    polarizations = [0, 1]  # Horizontal, Vertical
    labels = ["Horizontal", "Vertical"]

    for pol, label in zip(polarizations, labels):
        result = p528_model.get_loss(distance, h1, h2, frequency, polarization=pol)
        print(f"{label:10s} polarization -> Loss: {result[0]:.2f} dB")

    # Test Case 5: Frequency Variations
    print("\n5. Frequency Test")
    print("-" * 30)
    distance = np.array([100.0])
    frequencies = np.array([100.0, 1000.0, 5000.0, 10000.0, 30000.0])

    for f in frequencies:
        try:
            result = p528_model.get_loss(distance, h1, h2, np.array([f]))
            print(f"Frequency: {f:8.1f} MHz -> Loss: {result[0]:.2f} dB")
        except ValueError as e:
            print(f"Frequency: {f:8.1f} MHz -> Error: {str(e)}")

    # Test Case 6: Edge Cases
    print("\n6. Edge Cases")
    print("-" * 30)
    edge_cases = [
        (np.array([0.1]), 1.5, 20000.0),  # Very short distance
        (np.array([5000.0]), 1.5, 20000.0),  # Very long distance
        (np.array([100.0]), 1.5, 1.5),  # Equal heights
    ]

    for d, h1_test, h2_test in edge_cases:
        try:
            result = p528_model.get_loss(d, h1_test, h2_test, np.array([4000.0]))
            print(
                f"Distance: {d[0]:6.1f} km, h1: {h1_test:7.1f} m, h2: {h2_test:7.1f} m -> Loss: {result[0]:.2f} dB"
            )
        except ValueError as e:
            print(
                f"Distance: {d[0]:6.1f} km, h1: {h1_test:7.1f} m, h2: {h2_test:7.1f} m -> Error: {str(e)}"
            )


if __name__ == "__main__":
    test_p528_variations()
