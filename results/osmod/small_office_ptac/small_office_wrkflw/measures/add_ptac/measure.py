# ==================================================================================================
#    Copyright (c) 2024, Kian Wee Chen (chenkianwee@gmail.com)
# ==================================================================================================
import typing

import openstudio
from openstudio import model as osmod

def create_coil_cooling_dx_single_speed(openstudio_model: osmod, air_loop_node: osmod.Node = None, name: str = '1spd DX Clg Coil', 
                                        schedule: osmod.Schedule = None, type: str = 'PTAC', cop: float = None) -> osmod.CoilCoolingDXSingleSpeed:
    """
    Create a osmod.CoilCoolingDXSingleSpeed coil object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    air_loop_node : osmod.Node, optional
        default: None, the node of the air loop where the coil will be placed.

    name : str, optional
        default: '2spd DX Clg Coil', name of the coil.

    schedule : osmod.Schedule, optional
        default: None, availability schedule of the coil, if None = always on.
    
    type : str, optional
        default: 'PTAC', the type of 2 speed DX coil, used for referencing the correct curve set, 
        - choices: ['Heat Pump', 'PSZ-AC', 'Window AC', 'Residential Central AC', 'Residential Central ASHP', 'Split AC', 'PTAC']

    Returns
    -------
    CoilCoolingDXTwoSpeed : osmod.CoilCoolingDXTwoSpeed
        osmod.CoilCoolingDXSingleSpeed object.
    """
    clg_coil = osmod.CoilCoolingDXSingleSpeed(openstudio_model)

    # add to air loop if specified
    if air_loop_node != None:
        clg_coil.addToNode(air_loop_node)

    # set coil name
    clg_coil.setName(name)

    # set coil availability schedule
    # set coil schedule
    if schedule != None:
        clg_coil.setAvailabilitySchedule(schedule)
    else:
        # always on
        clg_coil.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())

    # set coil cop
    if cop != None:
        clg_coil.setRatedCOP(cop)

    clg_cap_f_of_temp = None
    clg_cap_f_of_flow = None
    clg_energy_input_ratio_f_of_temp = None
    clg_energy_input_ratio_f_of_flow = None
    clg_part_load_ratio = None

    # curve sets
    if type == 'Heat Pump':
        # "PSZ-AC_Unitary_PackagecoolCapFT"
        clg_cap_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_cap_f_of_temp.setCoefficient1Constant(0.766956)
        clg_cap_f_of_temp.setCoefficient2x(0.0107756)
        clg_cap_f_of_temp.setCoefficient3xPOW2(-0.0000414703)
        clg_cap_f_of_temp.setCoefficient4y(0.00134961)
        clg_cap_f_of_temp.setCoefficient5yPOW2(-0.000261144)
        clg_cap_f_of_temp.setCoefficient6xTIMESY(0.000457488)
        clg_cap_f_of_temp.setMinimumValueofx(12.78)
        clg_cap_f_of_temp.setMaximumValueofx(23.89)
        clg_cap_f_of_temp.setMinimumValueofy(21.1)
        clg_cap_f_of_temp.setMaximumValueofy(46.1)

        clg_cap_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_cap_f_of_flow.setCoefficient1Constant(0.8)
        clg_cap_f_of_flow.setCoefficient2x(0.2)
        clg_cap_f_of_flow.setCoefficient3xPOW2(0.0)
        clg_cap_f_of_flow.setMinimumValueofx(0.5)
        clg_cap_f_of_flow.setMaximumValueofx(1.5)

        clg_energy_input_ratio_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_energy_input_ratio_f_of_temp.setCoefficient1Constant(0.297145)
        clg_energy_input_ratio_f_of_temp.setCoefficient2x(0.0430933)
        clg_energy_input_ratio_f_of_temp.setCoefficient3xPOW2(-0.000748766)
        clg_energy_input_ratio_f_of_temp.setCoefficient4y(0.00597727)
        clg_energy_input_ratio_f_of_temp.setCoefficient5yPOW2(0.000482112)
        clg_energy_input_ratio_f_of_temp.setCoefficient6xTIMESY(-0.000956448)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofx(12.78)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofx(23.89)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofy(21.1)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofy(46.1)

        clg_energy_input_ratio_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_energy_input_ratio_f_of_flow.setCoefficient1Constant(1.156)
        clg_energy_input_ratio_f_of_flow.setCoefficient2x(-0.1816)
        clg_energy_input_ratio_f_of_flow.setCoefficient3xPOW2(0.0256)
        clg_energy_input_ratio_f_of_flow.setMinimumValueofx(0.5)
        clg_energy_input_ratio_f_of_flow.setMaximumValueofx(1.5)

        clg_part_load_ratio = osmod.CurveQuadratic(openstudio_model)
        clg_part_load_ratio.setCoefficient1Constant(0.85)
        clg_part_load_ratio.setCoefficient2x(0.15)
        clg_part_load_ratio.setCoefficient3xPOW2(0.0)
        clg_part_load_ratio.setMinimumValueofx(0.0)
        clg_part_load_ratio.setMaximumValueofx(1.0)

    if type == 'PSZ-AC':
        # Defaults to "DOE Ref DX Clg Coil Cool-Cap-fT"
        clg_cap_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_cap_f_of_temp.setCoefficient1Constant(0.9712123)
        clg_cap_f_of_temp.setCoefficient2x(-0.015275502)
        clg_cap_f_of_temp.setCoefficient3xPOW2(0.0014434524)
        clg_cap_f_of_temp.setCoefficient4y(-0.00039321)
        clg_cap_f_of_temp.setCoefficient5yPOW2(-0.0000068364)
        clg_cap_f_of_temp.setCoefficient6xTIMESY(-0.0002905956)
        clg_cap_f_of_temp.setMinimumValueofx(-100.0)
        clg_cap_f_of_temp.setMaximumValueofx(100.0)
        clg_cap_f_of_temp.setMinimumValueofy(-100.0)
        clg_cap_f_of_temp.setMaximumValueofy(100.0)

        clg_cap_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_cap_f_of_flow.setCoefficient1Constant(1.0)
        clg_cap_f_of_flow.setCoefficient2x(0.0)
        clg_cap_f_of_flow.setCoefficient3xPOW2(0.0)
        clg_cap_f_of_flow.setMinimumValueofx(-100.0)
        clg_cap_f_of_flow.setMaximumValueofx(100.0)

        # "DOE Ref DX Clg Coil Cool-EIR-fT",
        clg_energy_input_ratio_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_energy_input_ratio_f_of_temp.setCoefficient1Constant(0.28687133)
        clg_energy_input_ratio_f_of_temp.setCoefficient2x(0.023902164)
        clg_energy_input_ratio_f_of_temp.setCoefficient3xPOW2(-0.000810648)
        clg_energy_input_ratio_f_of_temp.setCoefficient4y(0.013458546)
        clg_energy_input_ratio_f_of_temp.setCoefficient5yPOW2(0.0003389364)
        clg_energy_input_ratio_f_of_temp.setCoefficient6xTIMESY(-0.0004870044)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofx(-100.0)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofx(100.0)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofy(-100.0)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofy(100.0)

        clg_energy_input_ratio_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_energy_input_ratio_f_of_flow.setCoefficient1Constant(1.0)
        clg_energy_input_ratio_f_of_flow.setCoefficient2x(0.0)
        clg_energy_input_ratio_f_of_flow.setCoefficient3xPOW2(0.0)
        clg_energy_input_ratio_f_of_flow.setMinimumValueofx(-100.0)
        clg_energy_input_ratio_f_of_flow.setMaximumValueofx(100.0)

        # "DOE Ref DX Clg Coil Cool-PLF-fPLR"
        clg_part_load_ratio = osmod.CurveQuadratic(openstudio_model)
        clg_part_load_ratio.setCoefficient1Constant(0.90949556)
        clg_part_load_ratio.setCoefficient2x(0.09864773)
        clg_part_load_ratio.setCoefficient3xPOW2(-0.00819488)
        clg_part_load_ratio.setMinimumValueofx(0.0)
        clg_part_load_ratio.setMaximumValueofx(1.0)
        clg_part_load_ratio.setMinimumCurveOutput(0.7)
        clg_part_load_ratio.setMaximumCurveOutput(1.0)

    if type == 'Window AC':
        # Performance curves
        # From Frigidaire 10.7 EER unit in Winkler et. al. Lab Testing of Window ACs (2013)
        # @note These coefficients are in SI UNITS
        cool_cap_ft_coeffs_si = [0.6405, 0.01568, 0.0004531, 0.001615, -0.0001825, 0.00006614]
        cool_eir_ft_coeffs_si = [2.287, -0.1732, 0.004745, 0.01662, 0.000484, -0.001306]
        cool_cap_fflow_coeffs = [0.887, 0.1128, 0]
        cool_eir_fflow_coeffs = [1.763, -0.6081, 0]
        cool_plf_fplr_coeffs = [0.78, 0.22, 0]

        # Make the curves
        clg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, cool_cap_ft_coeffs_si, 'RoomAC-Cap-fT', 0, 100, 0, 100)
        clg_cap_f_of_flow = create_curve_quadratic(openstudio_model, cool_cap_fflow_coeffs, 'RoomAC-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, cool_eir_ft_coeffs_si, 'RoomAC-EIR-fT', 0, 100, 0, 100)
        clg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, cool_eir_fflow_coeffs, 'RoomAC-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_part_load_ratio = create_curve_quadratic(openstudio_model, cool_plf_fplr_coeffs, 'RoomAC-PLF-fPLR', 0, 1, 0, 1, is_dimensionless = True)

    if type == 'Residential Central AC':
        # Performance curves
        # These coefficients are in IP UNITS
        cool_cap_ft_coeffs_ip = [3.670270705, -0.098652414, 0.000955906, 0.006552414, -0.0000156, -0.000131877]
        cool_eir_ft_coeffs_ip = [-3.302695861, 0.137871531, -0.001056996, -0.012573945, 0.000214638, -0.000145054]
        cool_cap_fflow_coeffs = [0.718605468, 0.410099989, -0.128705457]
        cool_eir_fflow_coeffs = [1.32299905, -0.477711207, 0.154712157]
        cool_plf_fplr_coeffs = [0.8, 0.2, 0]

        # Convert coefficients from IP to SI
        cool_cap_ft_coeffs_si = convert_curve_biquadratic(cool_cap_ft_coeffs_ip)
        cool_eir_ft_coeffs_si = convert_curve_biquadratic(cool_eir_ft_coeffs_ip)

        # Make the curves
        clg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, cool_cap_ft_coeffs_si, 'AC-Cap-fT', 0, 100, 0, 100)
        clg_cap_f_of_flow = create_curve_quadratic(openstudio_model, cool_cap_fflow_coeffs, 'AC-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, cool_eir_ft_coeffs_si, 'AC-EIR-fT', 0, 100, 0, 100)
        clg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, cool_eir_fflow_coeffs, 'AC-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_part_load_ratio = create_curve_quadratic(openstudio_model, cool_plf_fplr_coeffs, 'AC-PLF-fPLR', 0, 1, 0, 1, is_dimensionless = True)

    if type == 'Residential Central ASHP':
        # ASHP = Air Source Heat Pump
        # Performance curves
        # These coefficients are in IP UNITS
        cool_cap_ft_coeffs_ip = [3.68637657, -0.098352478, 0.000956357, 0.005838141, -0.0000127, -0.000131702]
        cool_eir_ft_coeffs_ip = [-3.437356399, 0.136656369, -0.001049231, -0.0079378, 0.000185435, -0.0001441]
        cool_cap_fflow_coeffs = [0.718664047, 0.41797409, -0.136638137]
        cool_eir_fflow_coeffs = [1.143487507, -0.13943972, -0.004047787]
        cool_plf_fplr_coeffs = [0.8, 0.2, 0]

        # Convert coefficients from IP to SI
        cool_cap_ft_coeffs_si = convert_curve_biquadratic(cool_cap_ft_coeffs_ip)
        cool_eir_ft_coeffs_si = convert_curve_biquadratic(cool_eir_ft_coeffs_ip)

        # Make the curves
        clg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, cool_cap_ft_coeffs_si, 'Cool-Cap-fT', 0, 100, 0, 100)
        clg_cap_f_of_flow = create_curve_quadratic(openstudio_model, cool_cap_fflow_coeffs, 'Cool-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, cool_eir_ft_coeffs_si, 'Cool-EIR-fT', 0, 100, 0, 100)
        clg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, cool_eir_fflow_coeffs, 'Cool-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_part_load_ratio = create_curve_quadratic(openstudio_model, cool_plf_fplr_coeffs, 'Cool-PLF-fPLR', 0, 1, 0, 1, is_dimensionless = True)

    else: # default curve set, type == 'Split AC' || 'PTAC'
        clg_cap_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_cap_f_of_temp.setCoefficient1Constant(0.942587793)
        clg_cap_f_of_temp.setCoefficient2x(0.009543347)
        clg_cap_f_of_temp.setCoefficient3xPOW2(0.00068377)
        clg_cap_f_of_temp.setCoefficient4y(-0.011042676)
        clg_cap_f_of_temp.setCoefficient5yPOW2(0.000005249)
        clg_cap_f_of_temp.setCoefficient6xTIMESY(-0.00000972)
        clg_cap_f_of_temp.setMinimumValueofx(12.77778)
        clg_cap_f_of_temp.setMaximumValueofx(23.88889)
        clg_cap_f_of_temp.setMinimumValueofy(23.88889)
        clg_cap_f_of_temp.setMaximumValueofy(46.11111)

        clg_cap_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_cap_f_of_flow.setCoefficient1Constant(0.8)
        clg_cap_f_of_flow.setCoefficient2x(0.2)
        clg_cap_f_of_flow.setCoefficient3xPOW2(0)
        clg_cap_f_of_flow.setMinimumValueofx(0.5)
        clg_cap_f_of_flow.setMaximumValueofx(1.5)

        clg_energy_input_ratio_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_energy_input_ratio_f_of_temp.setCoefficient1Constant(0.342414409)
        clg_energy_input_ratio_f_of_temp.setCoefficient2x(0.034885008)
        clg_energy_input_ratio_f_of_temp.setCoefficient3xPOW2(-0.0006237)
        clg_energy_input_ratio_f_of_temp.setCoefficient4y(0.004977216)
        clg_energy_input_ratio_f_of_temp.setCoefficient5yPOW2(0.000437951)
        clg_energy_input_ratio_f_of_temp.setCoefficient6xTIMESY(-0.000728028)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofx(12.77778)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofx(23.88889)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofy(23.88889)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofy(46.11111)

        clg_energy_input_ratio_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_energy_input_ratio_f_of_flow.setCoefficient1Constant(1.1552)
        clg_energy_input_ratio_f_of_flow.setCoefficient2x(-0.1808)
        clg_energy_input_ratio_f_of_flow.setCoefficient3xPOW2(0.0256)
        clg_energy_input_ratio_f_of_flow.setMinimumValueofx(0.5)
        clg_energy_input_ratio_f_of_flow.setMaximumValueofx(1.5)

        clg_part_load_ratio = osmod.CurveQuadratic(openstudio_model)
        clg_part_load_ratio.setCoefficient1Constant(0.85)
        clg_part_load_ratio.setCoefficient2x(0.15)
        clg_part_load_ratio.setCoefficient3xPOW2(0.0)
        clg_part_load_ratio.setMinimumValueofx(0.0)
        clg_part_load_ratio.setMaximumValueofx(1.0)
        clg_part_load_ratio.setMinimumCurveOutput(0.7)
        clg_part_load_ratio.setMaximumCurveOutput(1.0)

    if clg_cap_f_of_temp != None:
        clg_coil.setTotalCoolingCapacityFunctionOfTemperatureCurve(clg_cap_f_of_temp)
    if clg_cap_f_of_flow != None:
        clg_coil.setTotalCoolingCapacityFunctionOfFlowFractionCurve(clg_cap_f_of_flow)
    if clg_energy_input_ratio_f_of_temp != None:
        clg_coil.setEnergyInputRatioFunctionOfTemperatureCurve(clg_energy_input_ratio_f_of_temp)
    if clg_energy_input_ratio_f_of_flow != None:
        clg_coil.setEnergyInputRatioFunctionOfFlowFractionCurve(clg_energy_input_ratio_f_of_flow)
    if clg_part_load_ratio != None:
        clg_coil.setPartLoadFractionCorrelationCurve(clg_part_load_ratio)

    return clg_coil

def create_coil_heating_electric(openstudio_model: osmod, air_loop_node: osmod.Node = None, name: str = 'Electric Htg Coil', schedule: osmod.Schedule = None, 
                                 nominal_capacity: float = None, efficiency: float = 1.0) -> osmod.CoilHeatingElectric:
    """
    Create a osmod.CoilHeatingGas coil object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    air_loop_node : osmod.Node, optional
        default: None, the node of the air loop where the coil will be placed.

    name : str, optional
        default: 'Electric Htg Coil', name of the coil.

    schedule : osmod.Schedule, optional
        default: None, availability schedule of the coil, if None = always on.
    
    nominal_capacity : float, optional
        default: None, rated nominal capacity.

    efficiency : float, optional
        default: 0.8, rated heating efficiency.

    Returns
    -------
    CoilHeatingElectric : osmod.CoilHeatingElectric
        osmod.CoilHeatingElectric object.
    """
    htg_coil = osmod.CoilHeatingElectric(openstudio_model)
    # add to air loop
    if air_loop_node != None:
        htg_coil.addToNode(air_loop_node)
    # set coil name
    htg_coil.setName(name)
    # set coil schedule
    if schedule != None:
        htg_coil.setAvailabilitySchedule(schedule)
    else:
        # always on
        htg_coil.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())
    # set capacity
    if nominal_capacity != None:
        htg_coil.setNominalCapacity(nominal_capacity)
    # set efficiency
    htg_coil.setEfficiency(efficiency)
 
    return htg_coil

def create_coil_heating_gas(openstudio_model: osmod, air_loop_node: osmod.Node = None, name: str = 'Gas Htg Coil', schedule: osmod.Schedule = None, 
                            nominal_capacity: float = None, efficiency: float = 0.8) -> osmod.CoilHeatingGas:
    """
    Create a osmod.CoilHeatingGas coil object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    air_loop_node : osmod.Node, optional
        default: None, the node of the air loop where the coil will be placed.

    name : str, optional
        default: 'Gas Htg Coil', name of the coil.

    schedule : osmod.Schedule, optional
        default: None, availability schedule of the coil, if None = always on.
    
    nominal_capacity : float, optional
        default: None, rated nominal capacity.

    efficiency : float, optional
        default: 0.8, rated heating efficiency.

    Returns
    -------
    CoilHeatingGas : osmod.CoilHeatingGas
        osmod.CoilHeatingGas object.
    """
    htg_coil = osmod.CoilHeatingGas(openstudio_model)
    # add to air loop
    if air_loop_node != None:
        htg_coil.addToNode(air_loop_node)
    # set coil name
    htg_coil.setName(name)
    # set coil schedule
    if schedule != None:
        htg_coil.setAvailabilitySchedule(schedule)
    else:
        # always on
        htg_coil.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())
    # set capacity
    if nominal_capacity != None:
        htg_coil.setNominalCapacity(nominal_capacity)
    # set efficiency
    htg_coil.setGasBurnerEfficiency(efficiency)
    # defaults
    htg_coil.setParasiticElectricLoad(0)
    htg_coil.setParasiticGasLoad(0)
    return htg_coil

def create_coil_heating_water(openstudio_model: osmod, hot_water_loop: osmod.PlantLoop, air_loop_node: osmod.Node = None, name: str = 'Htg Coil', 
                              schedule: osmod.Schedule = None, rated_inlet_water_temperature: float = None, 
                              rated_outlet_water_temperature: float = None, rated_inlet_air_temperature: float = 16.6,
                              rated_outlet_air_temperature: float = 32.2, controller_convergence_tolerance: float = 0.1) -> osmod.CoilHeatingWater:
    """
    Create a osmod.CoilHeatingGas coil object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    hot_water_loop : osmod.PlantLoop
        the coil will be place on the demand side of the loop.

    air_loop_node : osmod.Node, optional
        default: None, the node of the air loop where the coil will be placed.

    name : str, optional
        default: 'Htg Coil', name of the coil.

    schedule : osmod.Schedule, optional
        default: None, availability schedule of the coil, if None = always on.
    
    rated_inlet_water_temperature : float, optional
        default: None, rated inlet water temperature in degC, if None == hot water loop design exit temperature

    rated_outlet_water_temperature : float, optional
        default: None, rated outlet water temperature in degC, if None == hot water loop design return temperature.

    rated_inlet_air_temperature : float, optional
        default: 16.6, rated inlet air temperature in degC, default is 16.6 (62F).
    
    rated_outlet_air_temperature : float, optional
        default: 32.2, rated outlet air temperature in degC, default is 32.2 (90F).

    controller_convergence_tolerance : float, optional
        default: 0.1, controller convergence tolerance.

    Returns
    -------
    CoilHeatingWater : osmod.CoilHeatingWater
        osmod.CoilHeatingWater object.
    """
    htg_coil = osmod.CoilHeatingWater(openstudio_model)
    # add to hot water loop
    hot_water_loop.addDemandBranchForComponent(htg_coil)
    # add to air loop
    if air_loop_node != None:
        htg_coil.addToNode(air_loop_node)
    # set coil name
    htg_coil.setName(name)
    # set coil schedule
    if schedule != None:
        htg_coil.setAvailabilitySchedule(schedule)
    else:
        # always on
        htg_coil.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())
    # rated water temperatures, use hot water loop temperatures if defined
    if rated_inlet_water_temperature == None:
        rated_inlet_water_temperature = hot_water_loop.sizingPlant().designLoopExitTemperature()
    htg_coil.setRatedInletWaterTemperature(rated_inlet_water_temperature)

    if rated_outlet_water_temperature == None:
        rated_outlet_water_temperature = rated_inlet_water_temperature - hot_water_loop.sizingPlant().loopDesignTemperatureDifference()
    htg_coil.setRatedOutletWaterTemperature(rated_outlet_water_temperature)

    htg_coil.setRatedInletAirTemperature(rated_inlet_air_temperature)
    htg_coil.setRatedOutletAirTemperature(rated_outlet_air_temperature)

    # coil controller properties
    # @note These inputs will get overwritten if addToNode or addDemandBranchForComponent is called on the htg_coil object after this
    htg_coil_controller = htg_coil.controllerWaterCoil().get()
    htg_coil_controller.setName(htg_coil.name + 'Controller')
    htg_coil_controller.setMinimumActuatedFlow(0.0)
    htg_coil_controller.setControllerConvergenceTolerance(controller_convergence_tolerance)

    return htg_coil

def create_curve_biquadratic(openstudio_model: osmod, coeffs: list, crv_name: str, min_x: float, max_x: float, min_y: float, max_y: float, 
                             min_out: float = None, max_out: float = None) -> osmod.CurveBiquadratic:
    """
    creates a biquadratic curve z = C1 + C2*x + C3*x^2 + C4*y + C5*y^2 + C6*x*y
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    coeffs : list[float]
        6 coefficients arranged in order.
    
    crv_name : str
        curve name.
    
    min_x : float
        min value of independent variable x.
    
    max_x : float
        max value of independent variable x.

    min_y : float
        min value of independent variable y.

    max_y : float
        max value of independent variable y.

    min_out : float, optional
        default: None, min value of dependent variable z.

    max_out : float, optional
        default: None, max value of dependent variable z.
    
    Returns
    -------
    CurveBiquadratic : osmod.CurveBiquadratic
        CurveBiquadratic curve use for determining performance of equipment.
    """
    curve = osmod.CurveBiquadratic(openstudio_model)
    curve.setName(crv_name)
    curve.setCoefficient1Constant(coeffs[0])
    curve.setCoefficient2x(coeffs[1])
    curve.setCoefficient3xPOW2(coeffs[2])
    curve.setCoefficient4y(coeffs[3])
    curve.setCoefficient5yPOW2(coeffs[4])
    curve.setCoefficient6xTIMESY(coeffs[5])
    curve.setMinimumValueofx(min_x)
    curve.setMaximumValueofx(max_x)
    curve.setMinimumValueofy(min_y)
    curve.setMaximumValueofy(max_y)
    if min_out != None:
        curve.setMinimumCurveOutput(min_out)
    if max_out != None:
        curve.setMaximumCurveOutput(max_out)
    return curve

def create_curve_quadratic(openstudio_model: osmod, coeffs: list, crv_name: str, min_x: float, max_x: float, min_out: float, 
                           max_out: float, is_dimensionless: bool = False) -> osmod.CurveQuadratic:
    """
    creates a quadratic curve z = C1 + C2*x + C3*x^2
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    coeffs : list[float]
        3 coefficients arranged in order.
    
    crv_name : str
        curve name.
    
    min_x : float
        min value of independent variable x.
    
    max_x : float
        max value of independent variable x.

    min_out : float
        min value of dependent variable z.

    max_out : float
        max value of dependent variable z.
    
    is_dimensionless : bool, optional
        default: False, if True, the X independent variable is unitless and the output dependent variable Z is unitless.
    
    Returns
    -------
    CurveQuadratic : osmod.CurveQuadratic
        CurveQuadratic curve use for determining performance of equipment.
    """
    curve = osmod.CurveQuadratic(openstudio_model)
    curve.setName(crv_name)
    curve.setCoefficient1Constant(coeffs[0])
    curve.setCoefficient2x(coeffs[1])
    curve.setCoefficient3xPOW2(coeffs[2])
    curve.setMinimumValueofx(min_x)
    curve.setMaximumValueofx(max_x)
    curve.setMinimumCurveOutput(min_out)
    curve.setMaximumCurveOutput(max_out)
    if is_dimensionless:
        curve.setInputUnitTypeforX('Dimensionless')
        curve.setOutputUnitType('Dimensionless')
    return curve

def convert_curve_biquadratic(coeffs: list, ip_to_si: bool = True) -> list:
    """
    Convert biquadratic curves that are a function of temperature from IP (F) to SI or vice-versa. 
    The curve is of the form z = C1 + C2*x + C3*x^2 + C4*y + C5*y^2 + C6*x*y where C1, C2, … are the coefficients, 
    x is the first independent variable (in F or C) y is the second independent variable (in F or C) and z is the resulting value

    Parameters
    ----------
    coeffs : list[float]
        3 coefficients arranged in order.

    ip_to_si : bool, optional
        default: True, if False, converts from si to ip.

    Returns
    -------
    new_coeffs : list[float]
        the converted coeff for the new unit system.
    """
    if ip_to_si:
        # Convert IP curves to SI curves
        si_coeffs = []
        si_coeffs.append(coeffs[0] + 32.0 * (coeffs[1] + coeffs[3]) + 1024.0 * (coeffs[2] + coeffs[4] + coeffs[5]))
        si_coeffs.append(9.0 / 5.0 * coeffs[1] + 576.0 / 5.0 * coeffs[2] + 288.0 / 5.0 * coeffs[5])
        si_coeffs.append(81.0 / 25.0 * coeffs[2]) 
        si_coeffs.append(9.0 / 5.0 * coeffs[3] + 576.0 / 5.0 * coeffs[4] + 288.0 / 5.0 * coeffs[5])
        si_coeffs.append(81.0 / 25.0 * coeffs[4])
        si_coeffs.append(81.0 / 25.0 * coeffs[5])
        return si_coeffs
    else:
        # Convert SI curves to IP curves
        ip_coeffs = []
        ip_coeffs.append(coeffs[0] - 160.0 / 9.0 * (coeffs[1] + coeffs[3]) + 25_600.0 / 81.0 * (coeffs[2] + coeffs[4] + coeffs[5]))
        ip_coeffs.append(5.0 / 9.0 * (coeffs[1] - 320.0 / 9.0 * coeffs[2] - 160.0 / 9.0 * coeffs[5]))
        ip_coeffs.append(25.0 / 81.0 * coeffs[2])
        ip_coeffs.append(5.0 / 9.0 * (coeffs[3] - 320.0 / 9.0 * coeffs[4] - 160.0 / 9.0 * coeffs[5]))
        ip_coeffs.append(25.0 / 81.0 * coeffs[4])
        ip_coeffs.append(25.0 / 81.0 * coeffs[5])
        return ip_coeffs

def create_on_off_fan_4ptac(openstudio_model: osmod, fan_name: str = None, fan_efficiency: float = 0.52, pressure_rise: float = 331.28, 
                            motor_efficiency: float = 0.8, motor_in_airstream_fraction: float = 1.0, 
                            end_use_subcategory: str = None) -> osmod.FanOnOff:
    """
    Create a osmod.FanOnOff fan object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_name : str, optional
        default: None, fan name

    fan_efficiency : float, optional
        default: 0.52', fan efficiency

    pressure_rise : float, optional
        default: 331.28, fan pressure rise in Pa.
    
    motor_efficiency : float, optional
        default: 0.8, fan motor efficiency

    motor_in_airstream_fraction : bool, optional
        default: 1.0, fraction of motor heat in airstream
    
    end_use_subcategory : str, optional
        default: None, end use subcategory name

    Returns
    -------
    on_off_fan : osmod.FanOnOff
        osmod.FanOnOff object
    """
    fan_on_off = osmod.FanOnOff(openstudio_model)
    if fan_name != None:
        fan_on_off.setName(fan_name)
    fan_on_off.setFanEfficiency(fan_efficiency)
    fan_on_off.setPressureRise(pressure_rise)
    fan_on_off.setMotorEfficiency(motor_efficiency)
    fan_on_off.setMotorInAirstreamFraction(motor_in_airstream_fraction)
    if end_use_subcategory != None:
        fan_on_off.setEndUseSubcategory(end_use_subcategory)
    return fan_on_off

def std_dgn_sizing_temps() -> dict:
    """
    creates a Packaged Terminal Air-Conditioning system for each zone and adds it to the model.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard#model_add_ptac-instance_method)
    
    Returns
    -------
    result : dict
        dictionary of all the standard temperatures used for sizing in degC
        - prehtg_dsgn_sup_air_temp_f = 45.0
        - preclg_dsgn_sup_air_temp_f = 55.0
        - htg_dsgn_sup_air_temp_f = 55.0
        - clg_dsgn_sup_air_temp_f = 55.0
        - zn_htg_dsgn_sup_air_temp_f = 104.0
        - zn_clg_dsgn_sup_air_temp_f = 55.0
        - prehtg_dsgn_sup_air_temp_c = 7.2
        - preclg_dsgn_sup_air_temp_c = 12.8
        - htg_dsgn_sup_air_temp_c = 12.8
        - clg_dsgn_sup_air_temp_c = 12.8
        - zn_htg_dsgn_sup_air_temp_c = 40.0
        - zn_clg_dsgn_sup_air_temp_c = 12.8
    """
    dsgn_temps = {}
    dsgn_temps['prehtg_dsgn_sup_air_temp_f'] = 45.0
    dsgn_temps['preclg_dsgn_sup_air_temp_f'] = 55.0
    dsgn_temps['htg_dsgn_sup_air_temp_f'] = 55.0
    dsgn_temps['clg_dsgn_sup_air_temp_f'] = 55.0
    dsgn_temps['zn_htg_dsgn_sup_air_temp_f'] = 104.0
    dsgn_temps['zn_clg_dsgn_sup_air_temp_f'] = 55.0
    dsgn_temps['prehtg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['prehtg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dsgn_temps['preclg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['preclg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dsgn_temps['htg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['htg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dsgn_temps['clg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['clg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dsgn_temps['zn_htg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['zn_htg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dsgn_temps['zn_clg_dsgn_sup_air_temp_c'] = openstudio.convert(dsgn_temps['zn_clg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    return dsgn_temps

def add_ptac(openstudio_model: osmod, thermal_zones: list, cooling_type: str = 'Single Speed DX AC', heating_type: str = 'Gas', 
             hot_water_loop: osmod.PlantLoop = None, fan_type: str = 'Cycling',  
             ventilation: bool = True) -> list:
    """
    creates a Packaged Terminal Air-Conditioning system for each zone and adds it to the model.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard#model_add_ptac-instance_method)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    thermal_zones : list[osmod.ThermalZone]
        list of zones connected to this system.
    
    cooling_type : str, optional
        default: 'Two Speed DX AC', choices: ['Single Speed DX AC']

    heating_type : str, optional
        default: 'Gas', choices: ['Gas', 'Electricity', 'Water', None(no heat)]

    hot_water_loop : osmod.PlantLoop, optional
        default: None, hot water loop connecting to the heating coil. Set to None for all 'heating_type' options except 'Water'.

    fan_type : str, optional
        default: 'Cycling', choices: ['Cycling', 'ConstantVolume']

    ventilation : bool, optional
        default: True. If True ventilation is supplied through the system. If False no ventilation will be supplied through the system.
    
    Returns
    -------
    ptac : list[osmod.ZoneHVACPackagedTerminalAirConditioner]
        list of configured ptac object 
    """
    # default design temperatures used across all air loops
    dgn_temps = std_dgn_sizing_temps()
    if hot_water_loop != None:
        hw_temp_c = hot_water_loop.sizingPlant().designLoopExitTemperature()
        hw_delta_t_k = hot_water_loop.sizingPlant().loopDesignTemperatureDifference()
    
    # adjusted zone design temperatures for ptac
    dgn_temps['zn_htg_dsgn_sup_air_temp_f'] = 122.0
    dgn_temps['zn_htg_dsgn_sup_air_temp_c'] = openstudio.convert(dgn_temps['zn_htg_dsgn_sup_air_temp_f'], 'F', 'C').get()
    dgn_temps['zn_clg_dsgn_sup_air_temp_f'] = 57.0
    dgn_temps['zn_clg_dsgn_sup_air_temp_c'] = openstudio.convert(dgn_temps['zn_clg_dsgn_sup_air_temp_f'], 'F', 'C').get()

    # make a ptac for each zone
    ptacs = []
    for thermal_zone in thermal_zones:
        # zone sizing
        sizing_zn = thermal_zone.sizingZone()
        sizing_zn.setZoneCoolingDesignSupplyAirTemperature(dgn_temps['zn_clg_dsgn_sup_air_temp_c'])
        sizing_zn.setZoneHeatingDesignSupplyAirTemperature(dgn_temps['zn_htg_dsgn_sup_air_temp_c'])
        sizing_zn.setZoneCoolingDesignSupplyAirHumidityRatio(0.008)
        sizing_zn.setZoneHeatingDesignSupplyAirHumidityRatio(0.008)
        # add fan
        on_off_fan = create_on_off_fan_4ptac(openstudio_model, fan_name = str(thermal_zone.name()) + 'PTAC_fan')
        on_off_fan.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())

        # add heating coil
        if heating_type == 'Gas':
            htg_coil = create_coil_heating_gas(openstudio_model, name = str(thermal_zone.name()) + 'PTAC Gas Htg Coil')
        elif heating_type == 'Electricity':
            htg_coil = create_coil_heating_electric(openstudio_model, name = str(thermal_zone.name()) + 'PTAC Electric Htg Coil')
        elif heating_type == None:
            htg_coil = create_coil_heating_electric(openstudio_model, name = str(thermal_zone.name()) + 'PTAC No Heat',
                                                    schedule = openstudio_model.alwaysOffDiscreteSchedule(), nominal_capacity=0)
        elif heating_type == 'Water':
            if hot_water_loop == None:
                print('Error! heating_type str == Water, but no hot_water_loop provided')
                return False
            htg_coil = create_coil_heating_water(openstudio_model, hot_water_loop, name = str(thermal_zone.name()) + 'Water Htg Coil',
                                                 rated_inlet_water_temperature = hw_temp_c, rated_outlet_water_temperature = (hw_temp_c - hw_delta_t_k))
        else:
            print('Error! heating_type str not recognized')
            return False

        # add cooling coil
        # if cooling_type == 'Two Speed DX AC':
        #     clg_coil = create_coil_cooling_dx_two_speed(openstudio_model, name = str(thermal_zone.name()) + 'PTAC 2spd DX AC Clg Coil')
        if cooling_type == 'Single Speed DX AC':
            clg_coil = create_coil_cooling_dx_single_speed(openstudio_model, name = str(thermal_zone.name()) + 'PTAC 1spd DX AC Clg Coil')
        else:
            print('Error! cooling_type str not recognized')
            return False
        
        ptac_system = osmod.ZoneHVACPackagedTerminalAirConditioner(openstudio_model, openstudio_model.alwaysOnDiscreteSchedule(), 
                                                                   on_off_fan, htg_coil, clg_coil)
        
        ptac_system.setName(str(thermal_zone.name()) + " PTAC")
        ptac_system.setFanPlacement('DrawThrough')
        if fan_type == 'ConstantVolume':
            ptac_system.setSupplyAirFanOperatingModeSchedule(openstudio_model.alwaysOnDiscreteSchedule())
        else:
            ptac_system.setSupplyAirFanOperatingModeSchedule(openstudio_model.alwaysOffDiscreteSchedule())
  
        if ventilation == False:
            ptac_system.setOutdoorAirFlowRateDuringCoolingOperation(0.0)
            ptac_system.setOutdoorAirFlowRateDuringHeatingOperation(0.0)
            ptac_system.setOutdoorAirFlowRateWhenNoCoolingorHeatingisNeeded(0.0)
        
        ptac_system.addToThermalZone(thermal_zone)
        ptacs.append(ptac_system)
    
    return ptacs

class AddPTAC(openstudio.measure.ModelMeasure):
    """A ModelMeasure."""

    def name(self):
        """Returns the human readable name.

        Measure name should be the title case of the class name.
        The measure name is the first contact a user has with the measure;
        it is also shared throughout the measure workflow, visible in the OpenStudio Application,
        PAT, Server Management Consoles, and in output reports.
        As such, measure names should clearly describe the measure's function,
        while remaining general in nature
        """
        return "Add Packaged Terminal Air-Conditioning (PTAC) Unit"

    def description(self):
        """Human readable description.

        The measure description is intended for a general audience and should not assume
        that the reader is familiar with the design and construction practices suggested by the measure.
        """
        return "Add Packaged Terminal Air-Conditioning (PTAC) unit to all the zones in the building"

    def modeler_description(self):
        """Human readable description of modeling approach.

        The modeler description is intended for the energy modeler using the measure.
        It should explain the measure's intent, and include any requirements about
        how the baseline model must be set up, major assumptions made by the measure,
        and relevant citations or references to applicable modeling resources
        """
        return "Loop through all the zones in the building and apply the PTAC unit to the thermal zone"

    def arguments(self, model: typing.Optional[openstudio.model.Model] = None):
        """Prepares user arguments for the measure.

        Measure arguments define which -- if any -- input parameters the user may set before running the measure.
        """
        args = openstudio.measure.OSArgumentVector()

        heating_type = openstudio.measure.OSArgument.makeChoiceArgument("heating_type", ['Gas', 'Electricity', 'Water', 'No Heat'], False)
        heating_type.setDisplayName('heating_type')
        heating_type.setDescription('The heating unit type')
        heating_type.setDefaultValue('Gas')
        args.append(heating_type)

        fan_type = openstudio.measure.OSArgument.makeChoiceArgument("fan_type", ['Cycling', 'ConstantVolume'], False)
        fan_type.setDisplayName('fan_type')
        fan_type.setDescription('The fan type of the system')
        fan_type.setDefaultValue('Cycling')
        args.append(fan_type)

        return args

    def run(
        self,
        model: openstudio.model.Model,
        runner: openstudio.measure.OSRunner,
        user_arguments: openstudio.measure.OSArgumentMap,
    ):
        """Defines what happens when the measure is run."""
        super().run(model, runner, user_arguments)  # Do **NOT** remove this line

        if not (runner.validateUserArguments(self.arguments(model), user_arguments)):
            return False

        #----------------------------------------------------------------------------
        # assign the user inputs to variables
        #----------------------------------------------------------------------------
        heating_type_str = runner.getStringArgumentValue("heating_type", user_arguments)
        if heating_type_str.lower() == 'no heat':
            heating_type = None
        else:
            heating_type = heating_type_str

        fan_type = runner.getStringArgumentValue("fan_type", user_arguments)

        # report initial condition of model
        runner.registerInitialCondition(f"The PTAC will have Single Speed DX AC for cooling, {heating_type_str} for heating and uses {fan_type} fan")
        
        # get all the thermal zones from the model and add ptac to the zones
        # thermal_zones = model.getThermalZones()
        thermal_zones = []
        spaces = model.getSpaces()
        for space in spaces:
            out_air = space.designSpecificationOutdoorAir()
            if out_air.empty() == False:
                tz = space.thermalZone() 
                if tz.empty() == False:
                    thermal_zones.append(tz.get())

        add_ptac(model, thermal_zones, heating_type=heating_type, fan_type=fan_type)
        runner.registerInfo(f"Added PTAC with Single Speed DX AC, {heating_type} heating and {fan_type} fan to all thermal zones")

        vars = []
        # plant loop variables
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Electricity Rate', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Electricity Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Total Cooling Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Total Cooling Rate', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Total Heating Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Total Heating Rate', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Sensible Heating Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Latent Heating Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Sensible Cooling Energy', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Packaged Terminal Air Conditioner Latent Cooling Energy', model)
        vars.append(var)
        
        for var in vars:
            var.setReportingFrequency('Hourly')

        # report final condition of model
        runner.registerFinalCondition(f"Successfully added PTAC to the building")
        return True

# register the measure to be used by the application
AddPTAC().registerWithApplication()
