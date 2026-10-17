# Plano: GUI do SHARC com cara de simulador profissional

Referências visuais e de uso: QGIS, FEKO, CST, Ansys, STK, Altium. Branch de trabalho: `sharc_database`. Stack mantida: PySide6 + QSS + QtWebEngine (Cesium).

## 0. Status
Ver `GUI_BACKLOG.md` (feito, pendente por prioridade e como retomar). Resumo: F0, F1, F2 feitas; F3 em andamento (tabela de propriedades e árvore por seção); preview realista feito; faltam database, antenas, terreno, F4, F6, F7.

## 1. Diagnóstico (capturas das abas General, IMT e Results, 2026-10-16)

| Problema | Onde | Causa no código |
|---|---|---|
| Visual de "app web": cantos de 7 a 12 px, paddings de 6 a 20 px | todas as abas | `build_stylesheet` em `main.py` (~800 linhas de QSS) |
| Páginas trocadas por botões laterais, sem área de trabalho | shell | `QStackedWidget` + `pages_config` em `main.py` |
| Rótulos crus do YAML (`min_separation_distance_bs_ue [m]`), unidade dentro do nome | General, IMT, Victim | tabs montam campos direto das chaves |
| Botões inconsistentes (azul cheio, plano, verde) | General, IMT | estilos por widget |
| Painéis vazios gigantes | tabela de variáveis, "Topology – MACROCELL" | layouts sem tamanho mínimo/estado vazio |
| Painel cortado com barra horizontal | Results | splitter sem largura mínima |
| Caminhos em vermelho sem explicação | General | `_check_path` pinta, não explica |
| Preview mostra o sistema vítima e esconde o macrocell | Preview | `_resolve_preview_type` em `ui/tabs/preview.py` |
| Badge "NOMINAL" sem informação, fontes monoespaçadas espaçadas | header | decoração em `main.py` |

## 2. Princípios de design

1. **Área de trabalho, não páginas.** Janela principal com painéis acopláveis: árvore do cenário, propriedades, vista (mapa/3D), console, resultados.
2. **Denso e plano.** Controles de 22 a 24 px, raio de 0 a 2 px, grade de 4 px, fonte de 9 pt, uma cor de acento.
3. **Propriedades como tabela.** Nome legível, valor, unidade em coluna própria, ajuda ao passar o mouse, marca de "alterado" e validação na linha.
4. **Tudo mostra estado.** Barra de status com projeto, estado da simulação, progresso e número de avisos. Lista de problemas clicável, como as mensagens do Altium.
5. **Layout persistente.** Posição e tamanho dos painéis salvos (`saveState`/`restoreState`) e presets de layout.
6. **Tema único e coerente.** Tokens de cor e de métrica em um módulo, escuro e claro, sem QSS espalhado por widget.

## 3. Fases

Tamanhos: P = pequeno, M = médio, G = grande. Cada fase termina com o app abrindo e as telas antigas ainda funcionando (migração incremental).

### F0. Base e rede de segurança (P)
- Script de tour de capturas (`switch_page` + `grab`) versionado em `sharc/gui/tools/`, para comparar antes e depois.
- Teste de fumaça do app e do Preview em modo automático.
- Corrigir `tests/e2e/test_gui_scenarios.py` se os imports `sharc.gui.main.App` e `core.state.AppState` já existem nesta branch.
- Decidir o destino de `sharc/gui/.legacy/` (cópia antiga de `view.py`).
- Aceite: capturas de referência de todas as 8 páginas e um comando único que roda o fumaça.

### F1. Sistema de design (M)
- `sharc/gui/ui/theme/` com `tokens.py` (cores, métricas, tipografia) e `stylesheet.py` (QSS gerado dos tokens).
- Mover `THEMES`, `build_stylesheet` e a fábrica de ícones de `main.py` para esse módulo.
- Novo tema escuro "grafite" (cinzas neutros, um acento), cantos de 2 px, controles compactos; tema claro derivado.
- Galeria de componentes (botão, campo, combo, tabela, árvore, abas, barra de ferramentas) para revisão visual.
- Aceite: todas as páginas atuais com o visual novo, sem regressão funcional.

### F2. Casca da aplicação (G)
- `QMainWindow` com `QDockWidget`: árvore do cenário (esquerda), propriedades (centro), vista (direita), console e problemas (abaixo).
- Barra de menus real (File, Edit, View, Simulation, Tools, Help), barra de ferramentas (novo/abrir/salvar, validar, rodar, parar) e barra de status.
- As abas atuais entram como painéis, sem reescrever o conteúdo.
- Persistência de layout e presets (Configuração, Execução, Análise).
- Aceite: troca de página some; tudo acessível por painéis e menus; layout restaurado ao reabrir.

### F3. Componente de propriedades (G)
- Widget de tabela de propriedades guiado por um esquema (chave YAML, nome, tipo, unidade, faixa, opções, ajuda, padrão).
- Marca de valor alterado, restaurar padrão, validação inline, busca por parâmetro.
- Piloto: General. Depois IMT, Victim e Earth Station.
- A pesquisar: derivar esquema, unidades e padrões das classes em `sharc/parameters/` (evitar duplicar o que o simulador já define).
- Aceite: General refeita com o componente, gerando o mesmo YAML que hoje (comparação automática de saída).

### F4. Árvore do cenário e validação (M)
- Árvore: Cenário, General, IMT (BS, UE, Topologia, Antena), Sistema vítima, Propagação, Banco de BSs.
- Selecionar um nó mostra suas propriedades; ícones de estado (ok, aviso, erro).
- Painel de problemas com clique que leva ao campo.
- Aceite: erro de caminho ou de faixa aparece na lista, com mensagem e destino.

### F5. Vista principal: mapa e 3D (G)
- Preview vira vista principal com painel de camadas estilo QGIS (BS, UE, footprints, fronteiras, cidades, malha).
- Mostrar IMT e sistema vítima juntos (corrige `_resolve_preview_type`).
- Barra de ferramentas da vista (navegar, medir, centralizar), leitura de coordenadas e escala.
- Base de mapa de maior resolução (a imagem única de 4096 px fica borrada em zoom).
- Aceite: macrocell + satélite/estação visíveis na mesma cena; camadas ligáveis.

### F6. Execução e resultados (M)
- Execução: tabela de jobs (estado, progresso, tempo), console acoplável, parar/retomar.
- Resultados: lista de séries, painel de estilo e gráfico em painéis acopláveis, exportar figura e CSV.
- Corrigir o painel cortado de Results.
- Aceite: rodar uma campanha e ver o resultado sem sair da casca.

### F7. Acabamento (M)
- Conjunto único de ícones, atalhos de teclado, tooltips, tema claro revisado, HiDPI, ajuda contextual.
- Aceite: revisão completa contra as capturas de F0.

## 4. Ordem e dependências
F0 → F1 → F2 → (F3 → F4) em paralelo com F5 → F6 → F7. F1 e F2 dão a maior mudança visível; F3 e F4 dão a sensação de ferramenta de engenharia.

## 5. Riscos
- `main.py` tem 1863 linhas e mistura casca, tema e lógica; mexer nele exige F0 pronta.
- Acoplamento com `AppState` e `SharcVar`: os painéis novos devem usar o mesmo estado, não um paralelo.
- O YAML gerado precisa ficar idêntico; comparar saída antes e depois em cada fase.
- QSS tem limites (cabeçalhos de tabela, árvore); se faltar, usar `QStyledItemDelegate` ou estilo próprio.

## 6. Decisões em aberto
1. Fita (ribbon) estilo CST/Ansys ou barra de ferramentas simples estilo QGIS/Altium?
2. Tema padrão: escuro ou claro?
3. Resolução mínima suportada (1366x768 ou 1920x1080)?
4. Manter o Plotly em Results ou migrar para Matplotlib/pyqtgraph embutido?
