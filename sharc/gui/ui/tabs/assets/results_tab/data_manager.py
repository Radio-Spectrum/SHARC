import os
import collections
import pandas as pd
import numpy as np
import posixpath
import shutil
import csv

class ResultsDataManager:
    def __init__(self, runner_manager, outdir_var_getter):
        self.runner = runner_manager
        self.outdir_var_getter = outdir_var_getter
        
        self._data_cache = collections.OrderedDict()
        self._cache_limit = 50  # Max number of datasets to keep in RAM

    def _get_base_dir(self):
        base = self.outdir_var_getter() if callable(self.outdir_var_getter) else None
        return base if base else os.getcwd()

    def clear_physical_cache(self):
        """Wipe the entire _remote_cache physical directory."""
        base = self._get_base_dir()
        cache_dir = os.path.join(base, "_remote_cache")
        try:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                return True
            return False
        except Exception:
            return False

    def clear_memory_cache(self):
        """Wipes the RAM LRU Cache."""
        self._data_cache.clear()

    def _sync_remote_file(self, tag, field, force_refresh=False):
        if not tag.startswith("ssh://"):
            return tag
        
        remote_path = tag[6:]
        fname = f"{field}.csv"
        
        base = self._get_base_dir()
        safe_name = remote_path.strip("/").replace("/", "__").replace(":", "_")
        local_dir = os.path.join(base, "_remote_cache", safe_name)
        os.makedirs(local_dir, exist_ok=True)
        local_file = os.path.join(local_dir, fname)

        # Force download logic
        should_download = force_refresh or not (os.path.exists(local_file) and os.path.getsize(local_file) > 0)

        if should_download and self.runner and self.runner.ssh_client:
            try:
                sftp = self.runner.ssh_client.open_sftp()
                rem_file = posixpath.join(remote_path, fname)
                sftp.get(rem_file, local_file)
                sftp.close()
            except Exception as e:
                # If we fail, trust the local cache if it exists
                pass

        return local_dir

    def get_data(self, folder_tag, field, force_refresh=False):
        # 1. Sync File Local or Remote
        local_folder = self._sync_remote_file(folder_tag, field, force_refresh)
        fpath = os.path.join(local_folder, f"{field}.csv")

        if not os.path.exists(fpath):
            return None

        # 2. Check LRU Cache
        key = (local_folder, field)
        try:
            mtime = os.path.getmtime(fpath)
            
            if not force_refresh and key in self._data_cache:
                cm, data = self._data_cache[key]
                if cm == mtime:
                    # Move to end since it was recently used
                    self._data_cache.move_to_end(key)
                    return data
            
            # 3. Read Header Optimization
            df_header = pd.read_csv(fpath, nrows=0)
            target_col = None
            for c in df_header.columns:
                if field.lower() in c.lower() or "value" in c.lower():
                    target_col = c
                    break

            if target_col is None and len(df_header.columns) > 0:
                target_col = df_header.columns[0]

            if target_col:
                # 4. Read Target Column as float32
                df = pd.read_csv(fpath, usecols=[target_col], dtype={target_col: np.float32})
                data = df[target_col].dropna().values
                
                # Update Cache
                self._data_cache[key] = (mtime, data)
                self._data_cache.move_to_end(key)
                
                # Check bounds
                if len(self._data_cache) > self._cache_limit:
                    self._data_cache.popitem(last=False)  # pop oldest
                    
                return data

        except Exception:
            pass
        return None

    def compute_ecdf(self, x, ccdf=False, downsample_to=0):
        x = np.sort(x)
        n = x.size
        if n == 0:
            return [], []
        y = np.arange(1, n+1) / n
        if ccdf:
            y = 1.0 - y

        if downsample_to > 0 and n > downsample_to:
            idx = np.linspace(0, n - 1, downsample_to).astype(int)
            x = x[idx]
            y = y[idx]
        return x, y

    def scan_columns(self, folder):
        """
        Scans a remote or local folder to fetch columns from the first valid CSV file.
        Returns a list of column strings. Raises Exception if it fails.
        """
        if folder.startswith("ssh://"):
            if not self.runner or not self.runner.ssh_client:
                raise ValueError("Not connected to SSH.")
            
            path = folder[6:]
            sftp = self.runner.ssh_client.open_sftp()
            try:
                files = sftp.listdir(path)
                for f in files:
                    if f.endswith(".csv"):
                        with sftp.open(posixpath.join(path, f), 'r') as rf:
                            header_line = rf.readline()
                            reader = csv.reader([header_line])
                            cols = list(reader)[0]
                            return cols, f
            finally:
                sftp.close()
            raise FileNotFoundError("No CSV files found in the remote folder.")
        else:
            for f in os.listdir(folder):
                if f.endswith(".csv"):
                    full_p = os.path.join(folder, f)
                    df = pd.read_csv(full_p, nrows=0)
                    return list(df.columns), f
            raise FileNotFoundError("No CSV files found in the local folder.")
