import numpy as np
import matplotlib.pyplot as plt

# faixa de frequência: 3 a 7 GHz
f_ghz = np.linspace(3, 7, 2000)
f_mhz = f_ghz * 1000

# primeiro calculamos a "atenuação positiva" A(f)
A = np.zeros_like(f_mhz)

# abaixo de 4,2 GHz
mask_low = f_mhz < 4200
A[mask_low] = 24 * np.log2(4200 / f_mhz[mask_low])

# acima de 4,4 GHz
mask_high = f_mhz > 4400
A[mask_high] = 24 * np.log2(f_mhz[mask_high] / 4400)

# limita de 0 a 40 dB
A = np.clip(A, 0, 40)

# agora invertemos o filtro: 0 dB na banda, negativo fora
H_db = -A   # 0 na banda, -A fora da banda

# pontos pedidos
f1, f2 = 3.65, 6.5
A1 = 24 * np.log2(4200 / (f1*1000))
A2 = 24 * np.log2((f2*1000) / 4400)
H1, H2 = -A1, -A2   # valores invertidos

print(f"H(3.65 GHz) = {H1:.2f} dB")
print(f"H(6.50 GHz) = {H2:.2f} dB")

# gráfico
plt.figure(figsize=(8,5))
plt.plot(f_ghz, H_db)
plt.grid(True, which="both", ls="--", alpha=0.5)
plt.xlabel("Frequência (GHz)")
plt.ylabel("Ganho (dB)")
plt.title("Filtro do Radioatímetro")

# linhas pontilhadas para 3,65 e 6,5 GHz
plt.axvline(f1, linestyle="--", color="gray")
plt.axvline(f2, linestyle="--", color="gray")

# marcadores nos pontos
plt.scatter([f1], [H1], color="red")
plt.scatter([f2], [H2], color="red")

# textos com os valores
plt.text(f1+0.05, H1-2, f"{H1:.1f} dB", color="red")
plt.text(f2+0.05, H2-2, f"{H2:.1f} dB", color="red")

plt.legend()
plt.tight_layout()
plt.show()
