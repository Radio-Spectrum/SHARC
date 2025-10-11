from pathlib import Path

p = Path(r"C:\Achiles\SHARC\sharc\campaigns\09_Guarulhos\Script\Base.yaml")
txt = p.read_text(encoding="utf-8", errors="replace").splitlines()

start, end, err_line, err_col = 80, 108, 94, 2
for i in range(start, min(end, len(txt)) + 1):
    line = txt[i-1]
    prefix = ">>" if i == err_line else "  "
    print(f"{prefix}{i:4d}: {line}")

print("\nMarca coluna:")
print(" " * (6 + len(str(err_line)) + err_col) + "^")