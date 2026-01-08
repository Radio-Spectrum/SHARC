import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sharc.post_processor import PostProcessor
# Caminho do arquivo CSV
path = os.path.join(os.path.dirname((os.path.dirname(__file__))), 'output', 'wifi_ul_inr.csv')

# Ler o CSV
df = pd.read_csv(path)

# Carregar dados (como antes)
data = df["samples"].dropna().to_numpy()

# Usar a função de CCDF do PostProcessor
x, y = PostProcessor.ccdf_from(data)

# Plotar com matplotlib (se quiser manter matplotlib)
plt.figure(figsize=(8,5))
plt.step(x, y, where="post")
plt.xlabel("samples")
plt.ylabel("P(X > x)")
plt.title("CCDF system_inr")
plt.yscale("log")  # igual ao logy=True padrão da classe
plt.grid(True)
plt.show()