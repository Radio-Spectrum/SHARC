import yaml
from dataclasses import dataclass
import configparser

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
    
                
        with open(config_file, 'r') as yaml_file:

            yaml_config = yaml.safe_load(yaml_file)

            if not self.section_name in yaml_config.keys():
                print(f"ParameterBase: section {self.section_name} not in parameter file.\
                    Only default parameters where loaded.")
                return

            # Load all the parameters from the configuration file
            attr_list = [a for a in dir(self) if not a.startswith('__') and not
                        callable(getattr(self, a)) and a != "section_name"]

            for attr_name in attr_list:
                try:
                    attr_val = getattr(self, attr_name)
                    setattr(self, attr_name, yaml_config[self.section_name][attr_name])
                except:
                    print(f"ParametersBase: NOTICE! Configuration parameter \"{self.section_name}.{attr_name}\" is not set in configuration file. Using default value {attr_val}")