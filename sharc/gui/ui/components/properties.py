"""Tabela de propriedades estilo Ansys/Feko/Altium para os formulários do GUI.

`restructure_page(root)` percorre uma página já construída e converte cada
`QGroupBox` em uma seção recolhível, com uma linha por parâmetro:

    [ nome legível        ] [ valor (editor) ] [ unidade ]

Os widgets originais (campos, combos, tabelas) são **movidos**, não recriados,
então as ligações com o estado e a geração do YAML continuam intactas. O próprio
`QGroupBox` é mantido (só muda de aparência), então o código das abas que o
mostra/esconde continua funcionando.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QComboBox, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLayout, QLineEdit, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

_ACRONYMS = {
    "bs", "ue", "imt", "dl", "ul", "rb", "es", "ss", "sa", "mss", "eess", "hdfss", "tvro", "itu",
    "fss", "ras", "rns", "ntn", "fs", "snr", "sinr", "inr", "yaml", "csv", "gps", "rf", "pfd", "eirp",
    "p452", "p619", "p1411", "uma", "umi", "abg", "fspl", "los", "nlos", "3db", "3gpp", "m2101", "s672",
    "s1528", "mimo", "psd", "bw", "ac", "gso", "ngso", "leo", "meo", "haps", "d2d", "dc",
}
_UNIT_RE = re.compile(r"^(.*?)\s*[\[(]([^\])]+)[\])]\s*$")


def humanize(label: str) -> Tuple[str, str, str]:
    """Devolve (texto legível, unidade, chave original) para um rótulo do YAML."""
    raw = (label or "").strip().rstrip(":").strip()
    unit = ""
    m = _UNIT_RE.match(raw)
    if m:
        raw, unit = m.group(1).strip(), m.group(2).strip()
    key = raw
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", raw) and ("_" in raw or raw.islower()):
        words = raw.replace(".", " ").replace("_", " ").split()
        words = [w.upper() if w.lower() in _ACRONYMS else w for w in words]
        if words and not words[0].isupper():
            words[0] = words[0].capitalize()
        text = " ".join(words)
    else:
        text = raw
    return text, unit, key


class _HeaderFilter(QObject):
    """Clique no cabeçalho da seção recolhe/expande o conteúdo."""

    def __init__(self, section):
        super().__init__(section)
        self.section = section

    def eventFilter(self, obj, ev):  # noqa: N802
        if ev.type() == QEvent.MouseButtonRelease and ev.button() == Qt.LeftButton:
            self.section.toggle()
            return True
        return False


class SectionBody:
    """Conteúdo de uma seção: grade de linhas de propriedades."""

    def __init__(self, box: QGroupBox, title: str):
        self.box = box
        self.rows = 0
        self.row_index = []          # (texto em minúsculas, [widgets da linha])
        self.header = QToolButton()
        self.header.setObjectName("SectionHeader")
        self.header.setCheckable(False)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.DownArrow)
        self.header.setText(" " + title)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.clicked.connect(self.toggle)

        self.content = QWidget()
        self.content.setObjectName("SectionBody")
        self.grid = QGridLayout(self.content)
        self.grid.setObjectName("PropGrid")
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(0)
        self.grid.setColumnStretch(0, 5)
        self.grid.setColumnStretch(1, 6)
        self.grid.setColumnMinimumWidth(2, 40)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.header)
        outer.addWidget(self.content)
        self.outer = outer

    def toggle(self):
        show = not self.content.isVisible()
        self.content.setVisible(show)
        self.header.setArrowType(Qt.DownArrow if show else Qt.RightArrow)

    def add_row(self, label_text: str, editor: Optional[QWidget], unit: str = ""):
        if isinstance(editor, QCheckBox) and not (label_text or "").strip():
            label_text = editor.text()
        if isinstance(editor, QCheckBox):
            editor.setText("")
        text, unit_l, key = humanize(label_text)
        unit = unit or unit_l or (str(editor.property("_unit") or "") if editor is not None else "")
        alt = "true" if self.rows % 2 else "false"

        lbl = QLabel(text)
        lbl.setObjectName("PropLabel")
        lbl.setProperty("alt", alt)
        lbl.setToolTip(key if key != text else "")
        lbl.setMinimumHeight(24)
        lbl.setWordWrap(False)
        lbl.setTextInteractionFlags(Qt.NoTextInteraction)

        cell = QFrame()
        cell.setObjectName("PropCell")
        cell.setProperty("alt", alt)
        cl = QHBoxLayout(cell)
        cl.setContentsMargins(4, 1, 4, 1)
        cl.setSpacing(4)
        if editor is not None:
            was_hidden = editor.isHidden()
            editor.setParent(cell)
            cl.addWidget(editor, 1)
            if not was_hidden:
                editor.show()
            editor.setMinimumWidth(40)
            if isinstance(editor, (QLineEdit, QComboBox)):
                editor.setMinimumHeight(22)
                editor.setMaximumHeight(24)
            editor.setSizePolicy(QSizePolicy.Expanding, editor.sizePolicy().verticalPolicy())

        u = QLabel(unit)
        u.setObjectName("PropUnit")
        u.setProperty("alt", alt)
        u.setMinimumHeight(24)

        r = self.rows
        self.grid.addWidget(lbl, r, 0)
        self.grid.addWidget(cell, r, 1)
        self.grid.addWidget(u, r, 2)
        if hasattr(self, "row_index"):
            self.row_index.append((f"{text} {key} {unit}".lower(), [lbl, cell, u]))
        self.rows += 1
        self.grid.setRowStretch(r, 0)
        self.grid.setRowStretch(self.rows, 1)   # sobra de altura vai para o fim, não entre as linhas

    def add_span(self, widget: QWidget):
        """Widget que ocupa a linha inteira (tabela, botões, etc.)."""
        was_hidden = widget.isHidden()
        widget.setParent(self.content)
        self.grid.addWidget(widget, self.rows, 0, 1, 3)
        if not was_hidden:
            widget.show()
        self.rows += 1
        self.grid.setRowStretch(self.rows - 1, 0)
        self.grid.setRowStretch(self.rows, 1)



def _layout_to_widget(layout: QLayout, keep: list) -> QWidget:
    """Cria um QWidget com os mesmos widgets de um layout aninhado (que tem pai)."""
    from PySide6.QtWidgets import QBoxLayout
    holder = QWidget()
    vertical = isinstance(layout, QBoxLayout) and layout.direction() in (
        QBoxLayout.TopToBottom, QBoxLayout.BottomToTop)
    new = QVBoxLayout(holder) if vertical else QHBoxLayout(holder)
    new.setContentsMargins(0, 0, 0, 0)
    new.setSpacing(4)
    widgets = []
    stack = [layout]
    while stack:                       # snapshot antes de mover (mover altera o layout)
        lay = stack.pop(0)
        for n in range(lay.count()):
            it = lay.itemAt(n)
            if it is None:
                continue
            if it.widget() is not None:
                widgets.append(it.widget())
            elif it.layout() is not None:
                stack.append(it.layout())
    for w in widgets:
        new.addWidget(w)
    return holder      # não vai para `keep`: o holder passa a ser o editor da linha


def _discard(label_widget) -> None:
    """Descarta o QLabel original cujo texto virou o nome da linha."""
    if isinstance(label_widget, QLabel):
        label_widget.hide()
        label_widget.deleteLater()


def _merge_unit_labels(entries: list) -> list:
    """Um QLabel curto solto logo após uma linha (ex.: 'm', 'MHz') vira a unidade dela."""
    merged: list = []
    for kind, payload in entries:
        if kind == "span" and isinstance(payload, QLabel) and merged and merged[-1][0] == "row":
            txt = (payload.text() or "").strip()
            if 0 < len(txt) <= 6 and not merged[-1][1][1].property("_unit"):
                merged[-1][1][1].setProperty("_unit", txt)
                _discard(payload)
                continue
        merged.append((kind, payload))
    return merged


def _label_text(item_widget) -> Optional[str]:
    return item_widget.text() if isinstance(item_widget, QLabel) else None


def _collect(layout: QLayout, keep: list) -> List[Tuple[str, object]]:
    """Lista ordenada de ('row', (label, widget)) | ('span', widget) | ('group', QGroupBox)."""
    out: List[Tuple[str, object]] = []

    def widget_of(item):
        w = item.widget()
        return w

    if isinstance(layout, QFormLayout):
        for r in range(layout.rowCount()):
            li = layout.itemAt(r, QFormLayout.LabelRole)
            fi = layout.itemAt(r, QFormLayout.FieldRole)
            si = layout.itemAt(r, QFormLayout.SpanningRole)
            if si is not None and si.widget() is not None:
                w = si.widget()
                out.append(("group", w) if isinstance(w, QGroupBox) else ("span", w))
                continue
            lw = widget_of(li) if li is not None else None
            fw = widget_of(fi) if fi is not None else None
            lt = _label_text(lw) or ""
            if fw is None and fi is not None and fi.layout() is not None:
                fw = _layout_to_widget(fi.layout(), keep)
            if fw is not None:
                if isinstance(fw, QGroupBox):
                    out.append(("group", fw))
                else:
                    out.append(("row", (lt, fw, lw)))
        return out

    if isinstance(layout, QGridLayout):
        cells = {}
        for i in range(layout.count()):
            item = layout.itemAt(i)
            r, c, rs, cs = layout.getItemPosition(i)
            w = item.widget()
            if w is None and item.layout() is not None:
                w = _layout_to_widget(item.layout(), keep)
            if w is not None:
                cells.setdefault(r, []).append((c, w))
        rows_sorted = sorted(cells)
        used_rows = set()
        for idx, r in enumerate(rows_sorted):
            nxt = rows_sorted[idx + 1] if idx + 1 < len(rows_sorted) else None
            if r in used_rows:
                continue
            seq0 = sorted(cells[r], key=lambda t: t[0])
            if nxt is not None and seq0 and all(isinstance(w, QLabel) for _c, w in seq0):
                seq1 = sorted(cells[nxt], key=lambda t: t[0])
                if seq1 and not any(isinstance(w, QLabel) for _c, w in seq1):
                    by_col = {c: w for c, w in seq1}
                    for c, lw in seq0:
                        if c in by_col:
                            out.append(("row", (lw.text(), by_col[c], lw)))
                    used_rows.add(nxt)
                    continue
        for r in rows_sorted:
            if r in used_rows:
                continue
            seq = sorted(cells[r], key=lambda t: t[0])
            k = 0
            while k < len(seq):
                _c, w = seq[k]
                if isinstance(w, QLabel) and k + 1 < len(seq) and not isinstance(seq[k + 1][1], QLabel):
                    nxt = seq[k + 1][1]
                    out.append(("group", nxt) if isinstance(nxt, QGroupBox) else ("row", (w.text(), nxt, w)))
                    k += 2
                elif isinstance(w, QLabel) and not (w.text() or "").strip():
                    k += 1
                elif isinstance(w, QCheckBox) and w.text():
                    out.append(("row", (w.text(), w, None)))
                    k += 1
                else:
                    out.append(("group", w) if isinstance(w, QGroupBox) else ("span", w))
                    k += 1
        return out

    # Box layouts (QHBoxLayout/QVBoxLayout) e outros: ordem de inserção
    i = 0
    items = [layout.itemAt(n) for n in range(layout.count())]
    while i < len(items):
        it = items[i]
        w = it.widget()
        if w is None and it.layout() is not None:
            out.extend(_collect(it.layout(), keep))
        elif w is not None:
            if isinstance(w, QLabel) and i + 1 < len(items) and items[i + 1].widget() is not None \
                    and not isinstance(items[i + 1].widget(), (QLabel, QGroupBox)) \
                    and isinstance(layout, QHBoxLayout):
                out.append(("row", (w.text(), items[i + 1].widget(), w)))
                i += 1
            elif isinstance(w, QGroupBox):
                out.append(("group", w))
            else:
                out.append(("span", w))
        i += 1
    return out


def convert_group(box: QGroupBox, depth: int = 0) -> List[QGroupBox]:
    """Converte `box` em seção (mantendo o objeto). Devolve os QGroupBox filhos extraídos."""
    if box.property("_section_done"):
        return []
    old = box.layout()
    if old is None:
        return []
    keep: list = []
    entries = _merge_unit_labels(_collect(old, keep))
    title = box.title()
    box.setTitle("")
    box.setFlat(True)
    box.setProperty("_section_done", True)
    box.setObjectName("Section")
    box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    # Solta o layout antigo; o holder mantém vivos os widgets até serem reinseridos
    old_holder = QWidget()
    old_holder.setLayout(old)
    keep.append(old_holder)

    body = SectionBody(box, title or "Parameters")
    children: List[QGroupBox] = []
    for kind, payload in entries:
        if kind == "row":
            label, widget, src_label = payload
            body.add_row(label, widget)
            _discard(src_label)
        elif kind == "span":
            body.add_span(payload)
        else:  # group aninhado -> vira seção própria, empilhada abaixo
            children.append(payload)
    box.setLayout(body.outer)
    box._section_body = body

    # Seções filhas entram empilhadas depois das linhas, com recuo visual
    for child in children:
        child.setParent(body.content)
        body.grid.addWidget(child, body.rows, 0, 1, 3)
        body.rows += 1
        child.setProperty("nested", True)
        convert_group(child, depth + 1)
    for h in keep:          # widgets reinseridos já foram reparentados; o resto é descartado
        h.deleteLater()
    return children


def relax_min_widths(root: QWidget) -> None:
    """Evita que textos longos e combos largos forcem rolagem horizontal."""
    from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
    for lbl in root.findChildren(QLabel):
        if len(lbl.text() or "") > 36 and not lbl.wordWrap():
            lbl.setWordWrap(True)
        lbl.setMinimumWidth(0)
    for cmb in root.findChildren(QComboBox):
        cmb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cmb.setMinimumContentsLength(8)
    for ed in root.findChildren(QLineEdit):
        ed.setMinimumWidth(40)
    for te in list(root.findChildren(QTextEdit)) + list(root.findChildren(QPlainTextEdit)):
        te.setMinimumWidth(0)


def flatten_grid(grid: QGridLayout) -> bool:
    """Reorganiza um QGridLayout solto (vários pares por linha) em uma linha por parâmetro."""
    keep: list = []
    entries = _merge_unit_labels(_collect(grid, keep))
    pairs = sum(1 for k, _ in entries if k == "row")
    if pairs < 2:
        for h in keep:
            h.deleteLater()
        return False
    owner = grid.parentWidget()
    # esvazia o grid (os widgets continuam vivos nos holders até serem reinseridos)
    while grid.count():
        it = grid.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(owner)
    grid.setColumnStretch(0, 5)
    grid.setColumnStretch(1, 6)
    grid.setHorizontalSpacing(0)
    grid.setVerticalSpacing(0)
    body = SectionBody.__new__(SectionBody)
    body.rows, body.grid, body.content = 0, grid, owner
    for kind, payload in entries:
        if kind == "row":
            body.add_row(payload[0], payload[1])
            _discard(payload[2])
        elif kind == "span":
            body.add_span(payload)
        else:
            body.add_span(payload)
    for h in keep:
        h.deleteLater()
    return True


def restructure_page(root: QWidget) -> int:
    """Converte todos os QGroupBox de `root`. Retorna quantas seções foram criadas."""
    relax_min_widths(root)
    count = 0
    # só grupos de nível mais alto; os aninhados são convertidos recursivamente
    groups = [g for g in root.findChildren(QGroupBox)
              if not any(isinstance(p, QGroupBox) for p in _ancestors(g))]
    for g in groups:
        convert_group(g)
        count += 1
    # Grades soltas (fora de QGroupBox) com vários pares por linha
    for g in list(root.findChildren(QGridLayout)):
        if g.objectName() == "PropGrid":
            continue
        try:
            flatten_grid(g)
        except RuntimeError:
            pass
    # Grupos escondidos dentro de widgets "span" (stacks, containers) ainda não convertidos
    for _ in range(4):
        pending = [g for g in root.findChildren(QGroupBox) if not g.property("_section_done")]
        if not pending:
            break
        for g in pending:
            convert_group(g)
            count += 1
    return count


def top_level_sections(root: QWidget) -> List[QGroupBox]:
    """Seções de nível mais alto de uma página (mesma ordem de criação)."""
    out = []
    for g in root.findChildren(QGroupBox):
        if not g.property("_section_done"):
            continue
        if any(isinstance(p, QGroupBox) for p in _ancestors(g)):
            continue
        out.append(g)
    return out


def section_title(box: QGroupBox) -> str:
    body = getattr(box, "_section_body", None)
    return body.header.text().strip() if body is not None else box.title()


def _ancestors(w: QWidget):
    p = w.parentWidget()
    while p is not None:
        yield p
        p = p.parentWidget()


def properties_qss(t: dict) -> str:
    """QSS das seções e linhas de propriedades (tokens do tema)."""
    return f"""
    QGroupBox#Section {{
        background: transparent;
        border: none;
        margin: 0 0 6px 0;
        padding: 0;
    }}
    QGroupBox#Section[nested="true"] {{ margin: 0; }}
    QToolButton#SectionHeader {{
        background: {t['bg_panel']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 0;
        padding: 3px 6px;
        text-align: left;
        font-weight: 600;
    }}
    QToolButton#SectionHeader:hover {{ background: {t['bg_hover']}; }}
    QWidget#SectionBody {{ background: transparent; }}
    QLabel#PropLabel {{
        padding: 0 8px;
        color: {t['text_secondary']};
        border-left: 1px solid {t['border_soft']};
    }}
    QFrame#PropCell {{ border: none; }}
    QLabel#PropUnit {{
        padding: 0 8px 0 2px;
        color: {t['text_muted']};
        border-right: 1px solid {t['border_soft']};
    }}
    QLabel#PropLabel[alt="true"], QFrame#PropCell[alt="true"], QLabel#PropUnit[alt="true"] {{
        background: {t['bg_card']};
    }}
    QLabel#PropLabel[alt="false"], QFrame#PropCell[alt="false"], QLabel#PropUnit[alt="false"] {{
        background: transparent;
    }}
    QWidget#SectionBody QLineEdit, QWidget#SectionBody QComboBox {{
        min-height: 20px;
        padding: 1px 4px;
    }}
    """


def filter_sections(boxes, text: str) -> int:
    """Mostra só as linhas que contêm `text` (nome, chave ou unidade). Retorna quantas casaram."""
    needle = (text or "").strip().lower()
    matched = 0
    for box in boxes:
        body = getattr(box, "_section_body", None)
        if body is None:
            continue
        any_row = False
        for hay, widgets in getattr(body, "row_index", []):
            ok = not needle or needle in hay
            for w in widgets:
                w.setVisible(ok)
            any_row = any_row or ok
            matched += 1 if (ok and needle) else 0
        if needle:
            body.content.setVisible(any_row or body.content.isVisible())
        if not needle:
            body.content.setVisible(True)
    return matched
