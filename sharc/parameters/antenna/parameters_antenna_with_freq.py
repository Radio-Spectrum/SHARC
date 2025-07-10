from sharc.parameters.parameters_base import ParametersBase

from dataclasses import dataclass


@dataclass
class ParametersAntennaWithFreq(ParametersBase):
    """
    Data class for antenna parameters that include frequency.

    This class extends ParametersBase and adds a frequency attribute with validation.
    """
    frequency: float = None

    # ideally we would make this happen at the ParametersBase.load_subparameters, but
    # since parser is a bit hacky, this is created without acces to system freq and antenna gain
    # so validation needs to happen manually afterwards
    def validate(self, ctx):
        """
        Validate the frequency parameter for the antenna configuration.

        Ensures that the frequency attribute is set and is a number.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        if None in [
            self.frequency,
        ]:
            raise ValueError(f"{ctx} needs to have all its parameters set")

        if not isinstance(
                self.frequency,
                int) and not isinstance(
                self.frequency,
                float):
            raise ValueError(f"{ctx}.frequency needs to be a number")
