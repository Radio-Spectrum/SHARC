# ui/tabs/__init__.py

from .general import GeneralTab
from .imt import IMTTab
from .victim import VictimTab
from .preview import PreviewTab
from .runner import RunnerTab
from .results import ResultsTab

__all__ = [
    "GeneralTab",
    "IMTTab",
    "VictimTab",
    "PreviewTab",
    "RunnerTab",
    "ResultsTab"
]
