import matplotlib.pyplot as plt
import numpy as np
import os
from sharc.post_processor import PostProcessor
import pandas as pd

path = os.path.join(os.path.dirname((os.path.dirname(__file__))), 'output', 'wifi_ul_sinr.csv')

# Ler o CSV
df = pd.read_csv(path)
# Carregar dados (como antes)
data = df["samples"].dropna().to_numpy()

# Usar a função de CCDF do PostProcessor
x, y = PostProcessor.cdf_from(data)

# Plotar com matplotlib (se quiser manter matplotlib)
plt.figure(figsize=(8,5))
plt.step(x, y, where="post")
plt.xlabel('SINR (dB)')
plt.ylabel("Probabilidade Acumulada (CDF)")
plt.title('CDF do SINR das APs (Impacto da Interferência)')
plt.grid(True)
plt.legend()
plt.show()