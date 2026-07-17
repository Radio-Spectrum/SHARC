from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout

class ScrollableContainer(QScrollArea):
    """
    Substituto PySide6 para o antigo ScrollableContainer.
    Gerencia a rolagem nativa de forma eficiente e fluida.
    """
    def __init__(self, parent=None, width=None, **kwargs):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setWidget(self.container)
        
        if width:
            self.setMinimumWidth(width)