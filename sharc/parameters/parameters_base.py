import configparser
from dataclasses import dataclass

@dataclass
class ParametersBase:
    """Base class for parameter dataclassess
    """
    section_name: str = "DEFAULT"
    is_space_to_earth: bool = False # whether the system is a space station or not

    def load_parameters_from_file(self, config_file: str):
        """Load the parameters from file.
        The sanity check is child class reponsibility

        Parameters
        ----------
        file_name : str
            the path to the configuration file

        Raises
        ------
        ValueError
            if a parameter is not valid
        """
        config = configparser.ConfigParser()
        config.read(config_file)

        if not self.section_name in config.sections():
            print(f"ParameterBase: section {self.section_name} not in parameter file.\
                  Only default parameters where loaded.")
            return

        # Load all the parameters from the configuration file
        attr_list = [a for a in dir(self) if not a.startswith('__') and not
                     callable(getattr(self, a)) and a != "section_name"]

        for attr_name in attr_list:
            try:
                attr_val = getattr(self, attr_name)
                if isinstance(attr_val, str):
                    setattr(self, attr_name, config.get(self.section_name, attr_name))
                elif isinstance(attr_val, bool):
                    setattr(self, attr_name, config.getboolean(self.section_name, attr_name))
                elif isinstance(attr_val, float):
                    setattr(self, attr_name, config.getfloat(self.section_name, attr_name))
                elif isinstance(attr_val, int):
                    setattr(self, attr_name, config.getint(self.section_name, attr_name))
                elif isinstance(attr_val, tuple):
                    # Check if the string defines a list of floats
                    try:
                        param_val = config.get(self.section_name, attr_name)
                        tmp_val = list(map(float, param_val.split(",")))
                        setattr(self, attr_name, tuple(tmp_val))
                    except ValueError:
                        # its a regular string. Let the specific class implementation
                        # do the sanity check
                        print(f"ParametersBase: could not convert string to tuple \"{self.section_name}.{attr_name}\"")
                        exit()

            except configparser.NoOptionError:
                print(f"ParametersBase: NOTICE! Configuration parameter \"{self.section_name}.{attr_name}\" is not set in configuration file. Using default value {attr_val}")
