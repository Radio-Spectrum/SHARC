import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sharc.post_processor import PostProcessor
# Caminho do arquivo CSV
path = os.path.join(os.path.dirname((os.path.dirname(__file__))), 'output', 'wifi_coupling_loss.csv')

# Ler o CSV
df = pd.read_csv(path)

# Carregar dados (como antes)
data = df["samples"].dropna().to_numpy()

# Usar a função de CCDF do PostProcessor
x, y = PostProcessor.cdf_from(data)

plt.figure(figsize=(8,5))
plt.step(x, y, where="post")
plt.xlabel("Coupling loss [dB]")
plt.ylabel("P(X ≤ x)")
plt.title("CDF — coupling loss - WIFI")
plt.grid(True)
plt.show()