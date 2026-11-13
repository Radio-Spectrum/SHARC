# IMT → estação terrena, com base de estações-base (feat/macro_database)

Esta pasta traz para a branch `feat/macro_database` o estudo feito no pacote
`branch_database2` (Projeto Anatel 6G, ENE/UnB, 09/10/2026). Ela contém o teste
de 30 estações-base perto do ROEN e um conversor para os demais YAMLs daquele
pacote.

```
database/                             bases de estações-base: NÃO versionadas
input/teste_instalacao.yaml           teste do pacote, convertido para esta branch
reference/branch_database2_*.csv      saída do teste no pacote (referência)
Script/convert_from_branch_database2.py
```

As bases de estações-base trazem sítios e operadoras reais e ficam fora do Git
(`sharc/campaigns/*/database/` está no `.gitignore`). Para rodar o teste, copie
`teste_instalacao/db_teste_30bs.csv` do pacote `branch_database2` para
`database/`. Sem esse arquivo, o teste `tests/e2e/test_branch_database2_case.py`
é pulado.

## Rodar o teste

De dentro de `sharc/`:

```
python main_cli.py -p campaigns/IMT_TO_SES_Database/input/teste_instalacao.yaml
```

São 10 snapshots: 5 por subconjunto × 2 subconjuntos. A saída vai para
`campaigns/IMT_TO_SES_Database/output/`. O teste
`tests/e2e/test_branch_database2_case.py` roda o mesmo caso e confere que cada
INR fica a menos de 0,1 dB da referência do pacote. A diferença medida é de
0,02 a 0,04 dB.

## Converter os YAMLs do pacote

```
python campaigns/IMT_TO_SES_Database/Script/convert_from_branch_database2.py \
    <pasta ou arquivo do pacote> <pasta de saída> \
    [--database <CSV da base>] [--output-dir <pasta de saída do SHARC>] [--check]
```

A conversão edita o texto e preserva os comentários:

| no pacote | nesta branch |
|---|---|
| `imt.topology.type: Macro_countries` | `MACRO_COUNTRIES` |
| `imt.ue.distribution_type: Macro_Countries` | `ANGLE_AND_DISTANCE` com `distribution_distance: SQRT(UNIFORM)` e `distribution_azimuth: UNIFORM` (a mesma distribuição de UEs do pacote) |
| `antenna.itu_r_f_1245_fs.gain` | removido: o ganho de pico da F.1245 é `antenna.gain` |

Com `--check`, cada arquivo convertido é carregado com o `Parameters` desta
branch (sem terreno real). Assim, uma chave desconhecida aparece na hora. Os 108
YAMLs de estações fixas do pacote passam nessa checagem.

Caminhos relativos da base e dos rasters valem a partir da pasta do YAML e,
se não forem encontrados ali, a partir da pasta de onde o SHARC é rodado.

## O que muda em relação ao branch_database2

- **Altura da antena da vítima.** Sem terreno real, o pacote punha a antena em
  `fixed_geo.altitude`, sem somar a altura acima do solo. Aqui a antena fica
  sempre em `altitude + geometry.height`. Com terreno real, as duas versões usam
  a cota do terreno mais a altura.
- **Apontamento.** O azimute e a elevação de uma estação `FIXED_GEO` são dados
  no referencial ENU local do sítio. O azimute é contado a partir do Leste, no
  sentido anti-horário, como em todo o simulador. Confira a convenção dos
  azimutes "extraídos da base" (rumo a partir do Norte?). `POINTING_AT_IMT_CENTER`
  aponta para o ponto de referência do simulador (`central_latitude/longitude`).
- **Segundo Monte Carlo.** Cada snapshot simula um único subconjunto da base.
  Para a interferência da base inteira, some os subconjuntos com
  `PostProcessor.aggregate_over_subsets(results.system_inr,
  results.system_database_subset)`. O pacote não faz essa soma.
- **P.452 pré-calculada** (`override_from_db`, com `use_real_terrain`). A perda
  de cada BS é calculada uma vez, sem ganhos de antena e com um único sorteio
  das partes aleatórias do modelo. Ela vale só para o downlink com o IMT
  interferindo.
- **Fora desta branch:** P.1812, a topologia `GEN_MACROCELL` e o terreno
  sintético da RadiAlti (`is_terrain` só é aceito junto com `override_from_db`).
