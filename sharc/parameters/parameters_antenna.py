from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_antenna_with_diameter import ParametersAntennaWithDiameter
from sharc.parameters.parameters_antenna_with_envelope_gain import ParametersAntennaWithEnvelopeGain
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528
from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
from sharc.parameters.antenna.parameters_antenna_with_freq import ParametersAntennaWithFreq
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.parameters.antenna.parameters_antenna_system4 import ParametersAntennaSystem4
from sharc.parameters.antenna.parameters_antenna_from_table import ParametersAntennaFromTable
from sharc.parameters.parameters_antenna_m1851_cosecant_squared import (
    ParametersAntennaM1851CosecantSquared,
)

from dataclasses import dataclass, field
import typing


@dataclass
class ParametersAntenna(ParametersBase):
    """
    Parameters for antenna configuration, including pattern, gain, and sub-parameters for different antenna models.
    """
    # available antenna radiation patterns
    __SUPPORTED_ANTENNA_PATTERNS = [
        "OMNI",
        "HibleoX",
        "ITU-R F.699",
        "ITU-R S.465",
        "ITU-R S.580",
        "MODIFIED ITU-R S.465",
        "ITU-R S.1855",
        "ITU-R Reg. RR. Appendice 7 Annex 3",
        "ARRAY",
        "ARRAY Satellite",
        "ARRAY System 4",
        "ITU-R-S.1528-Taylor",
        "ITU-R-S.1528-Section1.2",
        "ITU-R-S.1528-LEO",
        "ITU-R F.1245_fs",
        "Cosine Antenna",
        "Antenna System3 OOB",
        "Antenna System 4",
        "FROM TABLE",
        "ITU-R F.1336",
        "ITU-R M.1851",
        "M.1851-cosecant-squared"]

    # chosen antenna radiation pattern
    pattern: typing.Literal["OMNI",
                            "HibleoX",
                            "ITU-R F.699",
                            "ITU-R S.465",
                            "ITU-R S.580",
                            "MODIFIED ITU-R S.465",
                            "ITU-R S.1855",
                            "ITU-R Reg. RR. Appendice 7 Annex 3",
                            "ARRAY",
                            "ARRAY Satellite",
                            "ARRAY System 4",
                            "ITU-R-S.1528-Taylor",
                            "ITU-R-S.1528-Section1.2",
                            "ITU-R-S.1528-LEO",
                            "ITU-R F.1245_fs",
                            "Cosine Antenna",
                            "Antenna System3 OOB",
                            "Antenna System 4",
                            "FROM TABLE",
                            "ITU-R F.1336",
                            "ITU-R M.1851",
                            "M.1851-cosecant-squared"] = None

    # antenna gain [dBi]
    gain: float = None

    mss_adjacent: ParametersAntennaWithFreq = field(
        default_factory=ParametersAntennaWithFreq,
    )

    hibleo_x: ParametersAntennaWithFreq = field(
        default_factory=ParametersAntennaWithFreq,
    )

    itu_r_f_699: ParametersAntennaWithDiameter = field(
        default_factory=ParametersAntennaWithDiameter,
    )

    itu_r_s_465: ParametersAntennaWithDiameter = field(
        default_factory=ParametersAntennaWithDiameter,
    )

    itu_r_s_1855: ParametersAntennaWithDiameter = field(
        default_factory=ParametersAntennaWithDiameter,
    )

    itu_r_s_580: ParametersAntennaWithDiameter = field(
        default_factory=ParametersAntennaWithDiameter,
    )

    itu_r_s_465_modified: ParametersAntennaWithEnvelopeGain = field(
        default_factory=ParametersAntennaWithEnvelopeGain,
    )

    itu_reg_rr_a7_3: ParametersAntennaWithDiameter = field(
        default_factory=ParametersAntennaWithDiameter,
    )

    array: ParametersAntennaImt = field(
        default_factory=lambda: ParametersAntennaImt(
            downtilt=0.0))

    # TODO: maybe separate each different S.1528 parameter?
    itu_r_s_1528: ParametersAntennaS1528 = field(
        default_factory=ParametersAntennaS1528,
    )

    itu_r_s_672: ParametersAntennaS672 = field(
        default_factory=ParametersAntennaS672,
    )

    @dataclass
    class ParametersAntennaRF1245(ParametersBase):
        """
        Parameters for ITU-R F.1245 antenna model. It's commonly used
        for fixed service antennas.

        Paremeters
        ----------
        gain : float, default=-25
            Antenna gain in dB.
        diameter : float, optional
            Antenna diameter in meters.
        frequency : float, optional
            Operating frequency.
        """
        gain: float = -25
        diameter: float = None
        frequency: float = None

        def validate(self, ctx):
            """
            Validate the antenna parameters for correctness.

            Parameters
            ----------
            ctx : str
                Context string for error messages.
            Raises
            ------
            ValueError
                If any parameter is invalid.
            """
            if None in [self.gain, self.diameter, self.frequency]:
                raise ValueError(f"{ctx}.antenna_3_dB should be set to a number")

    itu_r_f_1245_fs: ParametersAntennaRF1245 = field(
        default_factory=ParametersAntennaRF1245,
    )

    antenna_system_4: ParametersAntennaSystem4 = field(
        default_factory=ParametersAntennaSystem4,
    )

    from_table: ParametersAntennaFromTable = field(
        default_factory=ParametersAntennaFromTable,
    )

    @dataclass
    class ParametersAntennaF1336(ParametersBase):
        """
        Parameters for ITU-R F.1336 antenna model.

        Paremeters
        ----------
        gain : float, default=12
            Antenna gain in dB.
        k : float, optional
            Accounts for side-lobe.
        cable_loss : float, optional
            Cable loss.
        mask_type : str, optional
            Side-lobe mask: "average" (eq. 1d, aggregate of multiple
            interferers -- the usual ITU-R sharing case, default) or "peak"
            (eq. 1a, single-entry worst case). Rec. ITU-R F.1336-5 sec. 2.1.
        """
        gain: float = 12.0
        k: float = 0.7
        cable_loss: float = 2.0
        # >>> F.1336 sec. 2.1 side-lobe mask (default average = aggregate case)
        mask_type: str = "average"
        # <<<

        def validate(self, ctx):
            """
            Validate the antenna parameters for correctness.

            Parameters
            ----------
            ctx : str
                Context string for error messages.

            Raises
            ------
            ValueError
                If any parameter is invalid.
            """
            if None in [self.gain, self.k, self.cable_loss]:
                raise ValueError(
                    f"{ctx}.(gain|k|cable_loss) need to be set to numbers"
                )

            if self.k < 0:
                raise ValueError(f"{ctx}.k needs to be a positive number")

            # >>> F.1336 sec. 2.1: validate the side-lobe mask type
            if str(self.mask_type).lower() not in ("peak", "average"):
                raise ValueError(
                    f"{ctx}.mask_type must be 'peak' or 'average'"
                )
            # <<<

            if getattr(super(), 'validate', None):
                super().validate(ctx)
                
    itu_r_f_1336: ParametersAntennaF1336 = field(
            default_factory=ParametersAntennaF1336,
        )
    
    @dataclass
    class ParametersAntennaM1851(ParametersBase):
        """
        Parâmetros para o modelo de antena ITU-R M.1851-12 (CSC²).

        Parâmetros
        ----------
        gain : float, default=30.0
            Ganho máximo da antena em dBi.
        theta_3 : float, default=2.0
            Largura de feixe (beamwidth) em graus.
        theta_start : float, default=1.0
            Ângulo inicial para o CSC² em graus.
        theta_end : float, default=45.0
            Ângulo final para o CSC² em graus.
        g_0 : float, default=-30.0
            Nível de floor (ganho base) em dB.
        theta_tilt : float
            Ângulo de inclinação em graus.
        """
        gain: float = 30.0
        theta_3: float = 2.0
        theta_start: float = 1.0
        theta_end: float = 45.0
        g_0: float = -30.0

        def validate(self, ctx):
            """
            Valida os parâmetros da antena para a norma M.1851.

            Parameters
            ----------
            ctx : str
                Contexto da string para mensagens de erro.
                
            Raises
            ------
            ValueError
                Se algum parâmetro numérico estiver faltando ou for fisicamente inconsistente.
            """
            # Verifica se os parâmetros essenciais estão presentes
            if None in [self.gain, self.theta_3, self.theta_start, self.theta_end, self.g_0]:
                raise ValueError(
                    f"{ctx}.(gain|theta_3|theta_start|theta_end|g_0) precisam ser definidos"
                )
            
            # Validações lógicas para consistência geométrica
            if self.theta_3 <= 0:
                raise ValueError(f"{ctx}.theta_3 deve ser um número positivo")
                
            if self.theta_end <= self.theta_start:
                raise ValueError(f"{ctx}.theta_end deve ser maior que theta_start")
                
            # Chama a validação da classe pai, se existir
            if getattr(super(), 'validate', None):
                super().validate(ctx)

    itu_r_m_1851: ParametersAntennaM1851 = field(
        default_factory=ParametersAntennaM1851,
    )

    itu_r_m1851_csc2: ParametersAntennaM1851CosecantSquared = field(
        default_factory=ParametersAntennaM1851CosecantSquared,
    )

    def set_external_parameters(self, **kwargs):
        """
        Set external parameters for all sub-parameters of the antenna.

        Parameters
        ----------
        **kwargs : dict
            External parameters to set on sub-parameters.
        """
        attr_list = [a for a in dir(self) if not a.startswith(
            '__') and isinstance(getattr(self, a), ParametersBase)]

        for attr_name in attr_list:
            param = getattr(self, attr_name)

            for k, v in kwargs.items():
                # we only set if not already set
                if k in dir(param) and getattr(param, k, None) is None:
                    setattr(param, k, v)

            if "antenna_gain" in dir(param):
                param.antenna_gain = self.gain

    def load_parameters_from_file(self, config_file):
        """
        Not implemented for ParametersAntenna. Should only be loaded as a subparameter.

        Parameters
        ----------
        config_file : str
            Path to the configuration file.
        Raises
        ------
        NotImplementedError
            Always raised for this method.
        """
        raise NotImplementedError()

    def validate(self, ctx):
        """
        Validate the antenna parameters for correctness.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        if None in [self.pattern]:
            raise ValueError(
                f"{ctx}.pattern should be set. It is None instead",
            )

        if self.pattern not in [
            "ARRAY", "ARRAY System 4", "ARRAY Satellite", "M.1851-cosecant-squared"
        ] and self.gain is None:
            raise ValueError(
                f"{ctx}.gain should be set if not using array antenna.",
            )

        if self.pattern not in self.__SUPPORTED_ANTENNA_PATTERNS:
            raise ValueError(
                f"Invalid {ctx}.pattern. It should be one of: {
                    self.__SUPPORTED_ANTENNA_PATTERNS}.", )

        match self.pattern:
            case "OMNI":
                pass
            case "HibleoX":
                self.hibleo_x.validate(f"{ctx}.hibleo_x")
            case "ITU-R F.699":
                self.itu_r_f_699.validate(f"{ctx}.itu_r_f_699")
            case "ITU-R S.465":
                self.itu_r_s_465.validate(f"{ctx}.itu_r_s_465")
            case "ITU-R S.1855":
                self.itu_r_s_1855.validate(f"{ctx}.itu_r_s_1855")
            case "MODIFIED ITU-R S.465":
                self.itu_r_s_465_modified.validate(
                    f"{ctx}.itu_r_s_465_modified",
                )
            case "ITU-R S.580":
                self.itu_r_s_580.validate(f"{ctx}.itu_r_s_580")
            case "ITU-R Reg. RR. Appendice 7 Annex 3":
                if self.itu_reg_rr_a7_3.diameter is None:
                    # just hijacking validation since diameter is optional
                    self.itu_reg_rr_a7_3.diameter = 0
                self.itu_reg_rr_a7_3.validate(f"{ctx}.itu_reg_rr_a7_3")
            case "ARRAY" | "ARRAY Satellite" | "ARRAY System 4":
                # TODO: validate here and make array non imt specific
                # self.array.validate(
                #     f"{ctx}.array",
                # )
                pass
            case "ITU-R-S.1528-Taylor":
                self.itu_r_s_1528.validate(f"{ctx}.itu_r_s_1528")
            case "ITU-R-S.1528-Section1.2":
                self.itu_r_s_1528.validate(f"{ctx}.itu_r_s_1528")
            case "ITU-R-S.1528-LEO":
                self.itu_r_s_1528.validate(f"{ctx}.itu_r_s_1528")
            case "ITU-R-S.672":
                self.itu_r_s_672.validate(f"{ctx}.itu_r_s_672")
            case "Cosine Antenna":
                self.mss_adjacent.validate(f"{ctx}.mss_adjacent")
            case "ITU-R F.1245_fs":
                self.itu_r_f_1245_fs.validate(f"{ctx}.itu_r_f_1245_fs")
            case "Antenna System3 OOB":
                # FIXME: do validation here
                pass
            case "Antenna System 4":
                self.antenna_system_4.validate(f"{ctx}.antenna_system_4")
            case "FROM TABLE":
                self.from_table.validate(f"{ctx}.from_table")
            case "ITU-R F.1336":
                self.itu_r_f_1336.validate(f"{ctx}.itu_r_f1336")
            case "ITU-R M.1851":
                self.itu_r_m_1851.validate(f"{ctx}.itu_r_m_1851")
            case "M.1851-cosecant-squared":
                self.itu_r_m1851_csc2.validate(f"{ctx}.itu_r_m1851_csc2")
            case _:
                raise NotImplementedError(
                    "ParametersAntenna.validate does not implement this antenna validation!", )
