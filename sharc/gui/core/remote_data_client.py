import os
import posixpath
import stat
import pandas as pd
import numpy as np

try:
    import paramiko
except ImportError:
    paramiko = None

class RemoteDataClient:
    """
    Handles SSH/SFTP connections, downloading remote simulation result files, 
    and memory caching (LRU approximation) of large CSV datasets via Pandas.
    """
    
    def __init__(self, cache_limit=50):
        self._data_cache = {}
        self._cache_limit = cache_limit

    def get_ssh_client(self, host, port, user, pwd=None):
        if not paramiko:
            return None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, port=port, username=user, password=pwd, timeout=5)
            return client
        except Exception as e:
            print(f"SSH Connect Error: {e}")
            return None

    def list_dir(self, client, remote_path):
        """Returns a list of tuples: (filename, type)"""
        if not client: return []
        try:
            sftp = client.open_sftp()
            if remote_path == ".":
                remote_path = sftp.normalize(".")
            items = []
            for item in sorted(sftp.listdir_attr(remote_path), key=lambda x: x.filename):
                if stat.S_ISDIR(item.st_mode):
                    items.append((item.filename, "DIR"))
            sftp.close()
            return items
        except Exception as e:
            print(f"SFTP List Error: {e}")
            return []
            
    def scan_columns(self, client, remote_path):
        """Downloads the header of the first CSV file to extract columns"""
        if not client: return []
        try:
            sftp = client.open_sftp()
            files = sftp.listdir(remote_path)
            for f in files:
                if f.endswith(".csv"):
                    with sftp.open(posixpath.join(remote_path, f), 'r') as rf:
                        header_line = rf.readline()
                        import csv
                        reader = csv.reader([header_line])
                        cols = list(reader)[0]
                        return cols, f
            return [], None
        except Exception as e:
            print(f"SFTP Scan Error: {e}")
            return [], None

    def sync_remote_file(self, client, remote_path, fname, local_base, force_refresh=False):
        safe_name = remote_path.strip("/").replace("/", "__").replace(":", "_")
        local_dir = os.path.join(local_base, "_remote_cache", safe_name)
        os.makedirs(local_dir, exist_ok=True)
        local_file = os.path.join(local_dir, fname)

        should_download = force_refresh or not (os.path.exists(local_file) and os.path.getsize(local_file) > 0)

        if should_download and client:
            try:
                sftp = client.open_sftp()
                rem_file = posixpath.join(remote_path, fname)
                sftp.get(rem_file, local_file)
                sftp.close()
            except Exception as e:
                if not os.path.exists(local_file):
                    print(f"Sync failed for {fname}: {e}")
        return local_dir

    def get_data(self, client, remote_folder_tag, field, local_base, force_refresh=False):
        # 1. LRU Cache cleanup
        if len(self._data_cache) > self._cache_limit:
            keys_to_remove = list(self._data_cache.keys())[:int(self._cache_limit * 0.2)]
            for k in keys_to_remove:
                del self._data_cache[k]

        # 2. Sync File
        local_folder = remote_folder_tag
        if remote_folder_tag.startswith("ssh://"):
            remote_path = remote_folder_tag[6:]
            local_folder = self.sync_remote_file(client, remote_path, f"{field}.csv", local_base, force_refresh)
        
        fpath = os.path.join(local_folder, f"{field}.csv")
        if not os.path.exists(fpath):
            return None

        # 3. Check Memory Cache
        try:
            mtime = os.path.getmtime(fpath)
            key = (local_folder, field)
            
            if not force_refresh and key in self._data_cache:
                cm, data = self._data_cache[key]
                if cm == mtime:
                    return data

            # 4. Read Header (Optimization)
            df_header = pd.read_csv(fpath, nrows=0)
            target_col = None
            for c in df_header.columns:
                if field.lower() in c.lower() or "value" in c.lower():
                    target_col = c
                    break

            if target_col is None and len(df_header.columns) > 0:
                target_col = df_header.columns[0]

            if target_col:
                # 5. Read Column with float32 (Memory Optimization)
                df = pd.read_csv(fpath, usecols=[target_col], dtype={target_col: np.float32})
                data = df[target_col].dropna().values
                self._data_cache[key] = (mtime, data)
                return data
        except Exception as e:
            print(f"Read error: {e}")
        return None
