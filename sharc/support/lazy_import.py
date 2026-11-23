"""Deferred import of slow libraries that most simulation runs never use.

matplotlib (plots for debugging), geopandas, pandas, cartopy and scipy.stats
together take several seconds to import, which was more than half of the
time of a short simulation, and the snapshot loop does not need them.
``lazy_module`` gives a stand-in that imports the real module the first time
one of its attributes is used:

    plt = lazy_module("matplotlib.pyplot")      # instead of: import matplotlib.pyplot as plt
    ...
    plt.figure()                                 # matplotlib is imported here

Type annotations that mention such a module must be written as strings
(``ax: "matplotlib.axes.Axes"``), otherwise defining the function would
already import it.
"""
import importlib


class LazyModule:
    """Stand-in for a module, imported on first attribute access."""

    def __init__(self, name: str):
        self.__dict__["_lazy_name"] = name
        self.__dict__["_lazy_module"] = None

    def _lazy_load(self):
        module = self.__dict__["_lazy_module"]
        if module is None:
            module = importlib.import_module(self.__dict__["_lazy_name"])
            self.__dict__["_lazy_module"] = module
        return module

    def __getattr__(self, attr):
        module = self._lazy_load()
        try:
            value = getattr(module, attr)
        except AttributeError:
            # a submodule that nothing imported yet (e.g. matplotlib.axes)
            try:
                value = importlib.import_module(f"{module.__name__}.{attr}")
            except ImportError:
                raise AttributeError(
                    f"module {module.__name__!r} has no attribute {attr!r}") from None
        self.__dict__[attr] = value         # next accesses skip __getattr__
        return value

    def __setattr__(self, attr, value):
        setattr(self._lazy_load(), attr, value)

    def __dir__(self):
        return dir(self._lazy_load())

    def __repr__(self):
        state = "loaded" if self.__dict__["_lazy_module"] is not None else "not loaded yet"
        return f"<lazy module {self.__dict__['_lazy_name']!r} ({state})>"


def lazy_module(name: str) -> LazyModule:
    """Stand-in for module ``name`` that imports it when first used."""
    return LazyModule(name)
