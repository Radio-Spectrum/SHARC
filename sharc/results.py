# -*- coding: utf-8 -*-
"""
Created on Thu Mar 23 08:47:46 2017

@author: edgar
"""

import glob
import os
import datetime
import re
import pathlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from shutil import copy
from sharc.support.sharc_logger import SimulationLogger

# pandas takes more than a second to import and a simulation run only needs it
# for unusual sample types (see Results.write_files): loaded on first use.
_pd = None


def _pandas():
    global _pd
    if _pd is None:
        import pandas
        _pd = pandas
    return _pd


class SampleList(list):
    """
    A list of samples of one result. Being its own class, no other list
    property of Results can be confused with a sample list.

    Post-processing reads the samples as NumPy arrays several times (median,
    mean, histogram...). Converting a list of a million numbers takes far
    longer than the computation itself, so the array is built once
    (as_array) and kept, together with anything derived from it (derived),
    until the list is modified.
    """

    def as_array(self) -> np.ndarray:
        """The samples as an array (the one ``np.asarray(self)`` gives), read-only and reused between calls."""
        arr = self.__dict__.get("_array")
        if arr is None or len(arr) != len(self):
            arr = np.asarray(self)
            arr.flags.writeable = False
            self.__dict__["_array"] = arr
            self.__dict__.pop("_derived", None)
        return arr

    def set_array(self, arr: np.ndarray):
        """Give the array the list was just built from, so that as_array does not convert it back."""
        arr = np.asarray(arr)
        if arr.ndim == 1 and len(arr) == len(self):
            arr.flags.writeable = False
            self.__dict__["_array"] = arr
            self.__dict__.pop("_derived", None)

    def derived(self) -> dict:
        """Scratch space for values computed from the samples (e.g. a histogram); emptied when the list changes."""
        return self.__dict__.setdefault("_derived", {})

    def _changed(self):
        self.__dict__.pop("_array", None)
        self.__dict__.pop("_derived", None)


def _forget_array_on(name):
    method = getattr(list, name)

    def wrapper(self, *args, **kwargs):
        self._changed()
        return method(self, *args, **kwargs)
    wrapper.__name__ = name
    wrapper.__doc__ = method.__doc__
    return wrapper


for _name in ("append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse",
              "__setitem__", "__delitem__", "__iadd__", "__imul__"):
    setattr(SampleList, _name, _forget_array_on(_name))
del _name


class Results(object):
    """Handle the output of the simulator"""

    # This should always be true for 1st samples flush
    overwrite_sample_files = True

    def __init__(self):
        # Transmit power density [dBm/Hz]
        self.imt_ul_tx_power_density = SampleList()
        self.imt_ul_tx_power = SampleList()
        # SINR [dB]
        self.imt_ul_sinr_ext = SampleList()
        # SINR [dB]
        self.imt_ul_sinr = SampleList()
        # SNR [dB]
        self.imt_ul_snr = SampleList()
        self.imt_ul_inr = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_ul_tput_ext = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_ul_tput = SampleList()

        self.imt_path_loss = SampleList()
        self.imt_coupling_loss = SampleList()
        # Antenna gain [dBi]
        self.imt_bs_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_ue_antenna_gain = SampleList()

        # Antenna gain [dBi]
        self.system_imt_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_system_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_system_antenna_gain_adjacent = SampleList()

        # Path Loss [dB]
        self.imt_system_path_loss = SampleList()
        # Building entry loss [dB]
        self.imt_system_build_entry_loss = SampleList()
        # System diffraction loss [dB]
        self.imt_system_diffraction_loss = SampleList()
        # System to IMT coupling loss
        self.sys_to_imt_coupling_loss = SampleList()

        self.imt_dl_tx_power_density = SampleList()
        # Transmit power [dBm]
        self.imt_dl_tx_power = SampleList()
        # SINR [dB]
        self.imt_dl_sinr_ext = SampleList()
        # SINR [dB]
        self.imt_dl_sinr = SampleList()
        # SNR [dB]
        self.imt_dl_snr = SampleList()
        # I/N [dB]
        self.imt_dl_inr = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_dl_tput_ext = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_dl_tput = SampleList()

        # PFD
        self.imt_dl_pfd_external = SampleList()
        self.imt_dl_pfd_external_aggregated = SampleList()

        self.system_ul_coupling_loss = SampleList()
        self.system_ul_interf_power = SampleList()
        # Interference Power [dBm]

        self.system_dl_coupling_loss = SampleList()
        self.system_dl_interf_power = SampleList()
        # Interference Power [dBm/MHz]
        # NOTE: this may not be what you want for a correct
        # protection criteria analysis since it is
        # a mean value. If you have both cochannel
        # and adjacent channel, the adjacent channel interference
        # will always drag the mean down
        self.system_dl_interf_power_per_mhz = SampleList()
        self.system_ul_interf_power_per_mhz = SampleList()

        self.system_inr = SampleList()
        self.system_pfd = SampleList()
        self.system_rx_interf = SampleList()

        # Base-station database runs: the subset that produced each system_inr
        # sample (see PostProcessor.aggregate_over_subsets)
        self.system_database_subset = SampleList()

        self.__sharc_dir = pathlib.Path(__file__).parent.resolve()

    def prepare_to_write(
        self,
        parameters_filename: str,
        overwrite_output: bool,
        output_dir="output",
        output_dir_prefix="output",
    ):
        """Prepare the output directory and filenames for writing results.

        Parameters
        ----------
        parameters_filename : str
            Name of the parameters file.
        overwrite_output : bool
            Whether to overwrite existing output.
        output_dir : str, optional
            Parent output directory. Default is "output".
        output_dir_prefix : str, optional
            Prefix for output directory. Default is "output".
        """
        self.output_dir_parent = output_dir

        if not overwrite_output:
            today = datetime.date.today()

            results_number = 1
            results_dir_head = (
                output_dir_prefix + "_" + today.isoformat() + "_" + "{:02n}"
            )
            self.create_dir(results_number, results_dir_head)
            copy(parameters_filename, self.output_directory)

        else:
            self.output_directory = self.__sharc_dir / self.output_dir_parent
            try:
                os.makedirs(self.output_directory)
            except FileExistsError:
                pass
        SimulationLogger.set_output_dir(self.output_directory)

        return self

    def prepare_to_resume(self, output_directory: str):
        """Reopen the output folder of an interrupted run: new samples are appended to its CSVs.

        Parameters
        ----------
        output_directory : str
            Folder written by the interrupted run (see sharc.support.checkpoint).
        """
        self.output_directory = pathlib.Path(output_directory)
        self.output_dir_parent = str(self.output_directory.parent)
        self.overwrite_sample_files = False
        SimulationLogger.set_output_dir(self.output_directory)
        return self

    def create_dir(self, results_number: int, dir_head: str):
        """Creates the output directory if it doesn't exist.

        Parameters
        ----------
        results_number : int
            Increment used in directory name
        dir_head : str
            Directory name prefix

        Returns
        -------
        str
            output directory name
        """

        dir_head_complete = (
            self.__sharc_dir /
            self.output_dir_parent /
            dir_head.format(results_number))

        try:
            os.makedirs(dir_head_complete)
            self.output_directory = dir_head_complete
        except FileExistsError:
            self.create_dir(results_number + 1, dir_head)

    def get_relevant_attributes(self):
        """
        Returns the attributes that are used for storing samples
        """
        self_dict = self.__dict__

        results_relevant_attr_names = list(
            filter(
                lambda x: isinstance(
                    getattr(
                        self,
                        x),
                    SampleList),
                self_dict))

        return results_relevant_attr_names

    def write_files(self, snapshot_number: int):
        """Writes the sample data to the output file

        Parameters
        ----------
        snapshot_number : int
            Current snapshot number
        """
        results_relevant_attr_names = self.get_relevant_attributes()
        for attr_name in results_relevant_attr_names:
            file_path = os.path.join(
                self.output_directory,
                attr_name + ".csv",
            )
            samples = getattr(self, attr_name)
            if len(samples) == 0:
                continue
            if self.overwrite_sample_files:
                mode, header = "w", True
            else:
                # a file first written in a later flush (or after a resume) still needs its header
                new_file = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
                mode, header = "a", new_file
            if not self._write_float_samples(file_path, samples, mode, header):
                df = _pandas().DataFrame({"samples": samples})
                df.to_csv(file_path, mode=mode, index=False, header=header)
            setattr(self, attr_name, SampleList())

        if self.overwrite_sample_files:
            self.overwrite_sample_files = False

    @staticmethod
    def _write_float_samples(file_path: str, samples: list, mode: str, header: bool) -> bool:
        """Write a sample file whose samples are all floats, without pandas.

        Produces the same bytes as ``DataFrame({"samples": samples}).to_csv(
        file_path, mode=mode, index=False, header=header)``: pandas formats a float column with
        ``ndarray.astype(str)`` and writes a missing value as a quoted empty
        field, which is what is done here. Any other content (integers,
        booleans, arrays...) is left to pandas.

        Returns
        -------
        bool
            False when the samples are not plain floats and nothing was written.
        """
        if not set(map(type, samples)) <= {float, np.float64}:
            return False
        values = np.asarray(samples, dtype=np.float64)
        text = values.astype(str)
        missing = np.isnan(values)
        if missing.any():
            text = text.astype(object)
            text[missing] = '""'
        lines = text.tolist()
        if header:
            lines.insert(0, "samples")
        with open(file_path, mode, newline="", encoding="utf-8") as file:
            file.write(os.linesep.join(lines) + os.linesep)
        return True

    @staticmethod
    def load_many_from_dir(
        root_dir: str,
        *,
        only_latest=True,
        only_samples: list[str] = None,
        filter_fn=None,
    ) -> list["Results"]:
        """
        Load multiple Results objects from a directory containing output folders.

        Args:
            root_dir (str): The root directory to search for output folders.
            only_latest (bool, optional): If True, only load the most recent output for each prefix. Defaults to True.
            only_samples (list[str], optional): List of sample names to load. If None, load all samples. Defaults to None.
            filter_fn (callable, optional): Function to filter output directories. Defaults to None.

        Returns:
            list[Results]: A list of loaded Results objects.
        """
        output_dirs = sorted(list(glob.glob(f"{root_dir}/output_*")))

        if len(output_dirs) == 0:
            print("[WARNING]: Results.load_many_from_dir did not find any results")

        if only_latest:
            output_dirs = Results.get_most_recent_outputs_for_each_prefix(
                output_dirs)

        if filter_fn:
            output_dirs = filter(filter_fn, output_dirs)

        all_res = []
        for output_dir in output_dirs:
            res = Results()
            res.load_from_dir(output_dir, only_samples=only_samples)
            all_res.append(res)

        return all_res

    def load_from_dir(
            self,
            abs_path: str,
            *,
            only_samples: list[str] = None) -> "Results":
        """
        Load results from a specified directory, optionally loading only specified samples.

        Args:
            abs_path (str): Absolute path to the output directory.
            only_samples (list[str], optional): List of sample names to load. If None, load all samples. Defaults to None.

        Returns:
            Results: The Results object with loaded data.
        """
        self.output_directory = abs_path

        self_dict = self.__dict__
        if only_samples is not None:
            results_relevant_attr_names = only_samples
        else:
            results_relevant_attr_names = filter(
                lambda x: isinstance(getattr(self, x), SampleList), self_dict
            )

        pd = _pandas()

        def read_samples(attr_name, file_path):
            """Samples of one file as an array (None if it has no data)."""
            # Try reading the .csv file using pandas with different
            # delimiters
            try:
                data = pd.read_csv(file_path, delimiter=",")
            except pd.errors.ParserError:
                data = pd.read_csv(file_path, delimiter=";")

            # Ensure the data has exactly one column
            if data.shape[1] != 1:
                raise Exception(
                    f"The file with samples of {attr_name} should have a single column.", )

            # Remove rows that do not contain valid numeric values
            data = data.apply(pd.to_numeric, errors="coerce").dropna()

            # Ignore if there is no data
            if data.empty:
                return None
            return data.to_numpy()[:, 0]

        present = []
        for attr_name in results_relevant_attr_names:
            file_path = os.path.join(abs_path, f"{attr_name}.csv")
            if os.path.exists(file_path):
                present.append((attr_name, file_path))

        # The files are independent and parsing them releases the interpreter
        # lock, so they are read side by side; the results are then taken in
        # the original order (the first bad file, in that order, is reported).
        workers = max(1, min(8, os.cpu_count() or 1, len(present)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = [pool.submit(read_samples, *item) for item in present]
            for (attr_name, _), future in zip(present, pending):
                try:
                    values = future.result()
                    if values is None:
                        continue
                    samples = SampleList(values)
                    samples.set_array(values)
                    setattr(self, attr_name, samples)
                except Exception as e:
                    print(e)
                    raise Exception(
                        f"Error processing the sample file ({attr_name}.csv) for {attr_name}: {e}")

        return self

    @staticmethod
    def get_most_recent_outputs_for_each_prefix(
            dirnames: list[str]) -> list[str]:
        """
        Get the most recent output directory for each output prefix.

        Args:
            dirnames (list[str]): A list of output directory names.

        Returns:
            list[str]: A list containing the most recent output dirname for each output_prefix.
        """
        res = {}

        for dirname in dirnames:
            prefix, date, id = Results.get_prefix_date_and_id(dirname)
            res.setdefault(
                prefix, {
                    "date": date, "id": id, "dirname": dirname})
            if date > res[prefix]["date"]:
                res[prefix]["date"] = date
                res[prefix]["id"] = id
                res[prefix]["dirname"] = dirname
            if date == res[prefix]["date"] and id > res[prefix]["id"]:
                res[prefix]["id"] = id
                res[prefix]["dirname"] = dirname

        return list(map(lambda x: x["dirname"], res.values()))

    @staticmethod
    def get_prefix_date_and_id(dirname: str) -> tuple[str, str, str]:
        """
        Extract the prefix, date, and id from a directory name.

        Args:
            dirname (str): The directory name to parse.

        Returns:
            tuple: A tuple containing the prefix, date, and id as strings.
        """
        mtch = re.search(
            "(.*)(20[2-9][0-9]-[0-1][0-9]-[0-3][0-9])_([0-9]{2})",
            dirname)
        prefix, date, id = mtch.group(1), mtch.group(2), mtch.group(3)
        return prefix, date, id
