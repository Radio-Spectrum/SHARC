import os

class ComputeBackend:
    """
    Singleton that manages the GPU/CPU state for the SHARC simulator.
    It injects the correct library (CuPy or NumPy) globally so equations
    remain agnostic to the underlying hardware.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ComputeBackend, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
        
    def _initialize(self):
        # Can be set via environment variable: export SHARC_USE_GPU=1
        self.use_gpu = os.environ.get("SHARC_USE_GPU", "0") == "1"
        
        if self.use_gpu:
            try:
                import cupy as xp
                self.xp = xp
                print("[SHARC-GPU] CuPy Acceleration Activated.")
            except ImportError:
                print("[SHARC-GPU] Warning: CuPy not found. Fallback to base NumPy.")
                import numpy as xp
                self.xp = xp
                self.use_gpu = False
        else:
            import numpy as xp
            self.xp = xp
            
    def asnumpy(self, array):
        """Transfers matrices from VRAM (GPU) back to RAM (CPU) for I/O operations."""
        if self.use_gpu and hasattr(array, 'get'):
            return array.get()
        return array
        
    def asarray(self, array):
        """Loads base arrays into VRAM (GPU)."""
        return self.xp.asarray(array)

# Global instances to be imported across the SHARC framework
backend = ComputeBackend()
xp = backend.xp
