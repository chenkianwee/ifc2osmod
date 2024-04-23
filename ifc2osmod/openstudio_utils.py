import json
import pathlib
import subprocess
from distutils.dir_util import copy_tree

import geomie3d
from ladybug.epw import EPW
import numpy as np
import openstudio
from openstudio import model as osmod

def g3dverts2ospt3d(g3dverts: list[geomie3d.topobj.Vertex], decimals: int = 6) -> list[openstudio.openstudioutilitiesgeometry.Point3d]:
    pt3ds = []
    for v in g3dverts:
        xyz = v.point.xyz
        xyz = np.round(xyz, decimals=decimals)
        x = xyz[0]
        y = xyz[1]
        z = xyz[2]
        pt3d = openstudio.openstudioutilitiesgeometry.Point3d(x,y,z)
        pt3ds.append(pt3d)
    return pt3ds

def save_osw_project(proj_dir: str, openstudio_model: osmod, measure_folder_list: list[dict]) -> str:
    # create all the necessary directory
    proj_path = pathlib.Path(proj_dir)
    proj_name = proj_path.stem
    wrkflow_dir = pathlib.PurePath(proj_dir, proj_name + '_wrkflw')
    dir_ls = ['files', 'measures', 'run']
    for dir in dir_ls:
        dir_in_wrkflw = pathlib.PurePath(wrkflow_dir, dir)
        pathlib.Path(dir_in_wrkflw).mkdir(parents=True, exist_ok=True)
    
    # create the osm file
    osm_filename = proj_name + '.osm'
    osm_path = pathlib.PurePath(proj_dir, osm_filename)
    openstudio_model.save(str(osm_path), True)

    # retrieve the osw file
    oswrkflw = openstudio_model.workflowJSON()
    oswrkflw.setSeedFile('../' + osm_filename)

    # create the result measure into the measures folder
    msteps = {0: [], 1: [], 2: [], 3: []}
    for measure_folder in measure_folder_list:
        measure_dir_orig = measure_folder['dir']
        foldername = pathlib.Path(measure_dir_orig).stem
        measure_dir_dest = str(pathlib.PurePath(wrkflow_dir, 'measures', foldername))
        copy_tree(measure_dir_orig, measure_dir_dest)
        # set measurestep
        mstep = openstudio.MeasureStep(measure_dir_dest)
        mstep.setName(foldername)
        mstep.setDescription(measure_folder['description'])
        mstep.setModelerDescription(measure_folder['modeler_description'])
        if 'arguments' in measure_folder.keys():
            arguments = measure_folder['arguments']
            for argument in arguments:
                mstep.setArgument(argument['argument'], argument['value'])
        msteps[measure_folder['type']].append(mstep)
    
    for mt_val in msteps.keys():
        measure_type = openstudio.MeasureType(mt_val)
        measure_steps = msteps[mt_val]
        if len(measure_steps) != 0:
            oswrkflw.setMeasureSteps(measure_type, measure_steps)
    
    wrkflw_path = str(pathlib.PurePath(wrkflow_dir, proj_name + '.osw'))
    oswrkflw.saveAs(wrkflw_path)
    with open(wrkflw_path) as wrkflw_f:
        data = json.load(wrkflw_f)
        steps = data['steps']
        for step in steps:
            dirname = step['measure_dir_name']
            foldername = pathlib.Path(dirname).stem
            step['measure_dir_name'] = foldername

    out_file = open(wrkflw_path, "w") 
    json.dump(data, out_file)
    out_file.close()
    return wrkflw_path

def save2idf(idf_path: str, openstudio_model: osmod):
    ft = openstudio.energyplus.ForwardTranslator()
    idf = ft.translateModel(openstudio_model)
    idf.save(idf_path, True)

def setup_ppl_schedule(openstudio_model: osmod, ruleset: osmod.ScheduleRuleset, act_ruleset:osmod.ScheduleRuleset, name: str = None) -> osmod.People:
    # occupancy definition
    ppl_def = osmod.PeopleDefinition(openstudio_model)
    ppl = osmod.People(ppl_def)
    ppl.setNumberofPeopleSchedule(ruleset)
    ppl.setActivityLevelSchedule(act_ruleset)
    if name != None:
        ppl_def.setName(name + 'definition')
        ppl.setName(name)
    return ppl

def setup_light_schedule(openstudio_model: osmod, ruleset: osmod.ScheduleRuleset, name: str = None) -> osmod.Lights:
    # light definition
    light_def = osmod.LightsDefinition(openstudio_model)
    light = osmod.Lights(light_def)
    if name != None:
        light_def.setName(name + '_definition')
        light.setName(name)
    light.setSchedule(ruleset)
    return light

def setup_elec_equip_schedule(openstudio_model: osmod, ruleset: osmod.ScheduleRuleset, name: str = None) -> osmod.ElectricEquipment:
    # light definition
    elec_def = osmod.ElectricEquipmentDefinition(openstudio_model)
    elec_equip = osmod.ElectricEquipment(elec_def)
    if name != None:
        elec_def.setName(name + '_definition')
        elec_equip.setName(name)
    elec_equip.setSchedule(ruleset)
    return elec_equip

def execute_workflow(wrkflow_path:str):
    print('executing workflow ...')
    result = subprocess.run(['openstudio', 'run', '-w', wrkflow_path], capture_output=True, text=True)
    print(result.stdout)

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

def create_curve_biquadratic(openstudio_model: osmod, coeffs: list[float], crv_name: str, min_x: float, max_x: float, min_y: float, max_y: float, 
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

def create_curve_quadratic(openstudio_model: osmod, coeffs: list[float], crv_name: str, min_x: float, max_x: float, min_out: float, 
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

def convert_curve_biquadratic(coeffs: list[float], ip_to_si: bool = True) -> list[float]:
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

def model_apply_prm_sizing_parameters(openstudio_model: osmod):
    '''
    Apply sizing parameter to the openstudio model.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    '''
    clg = 1.15
    htg = 1.25
    sizing_params = openstudio_model.getSizingParameters()
    sizing_params.setHeatingSizingFactor(htg)
    sizing_params.setCoolingSizingFactor(clg)

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

def create_coil_cooling_dx_two_speed(openstudio_model: osmod, air_loop_node: osmod.Node = None, name: str = '2spd DX Clg Coil', 
                                     schedule: osmod.Schedule = None, type: str = 'PTAC') -> osmod.CoilCoolingDXTwoSpeed:
    """
    Create a osmod.CoilCoolingDXTwoSpeed coil object.
    
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
        - choices: ['Residential Minisplit HP', 'PSZ-AC', 'Split AC', 'PTAC']

    Returns
    -------
    CoilCoolingDXTwoSpeed : osmod.CoilCoolingDXTwoSpeed
        osmod.CoilCoolingDXTwoSpeed object.
    """
    clg_coil = osmod.CoilCoolingDXTwoSpeed(openstudio_model)
    # add to air loop
    if air_loop_node != None:
        clg_coil.addToNode(air_loop_node)
    # set coil name
    clg_coil.setName(name)
    # set coil schedule
    if schedule != None:
        clg_coil.setAvailabilitySchedule(schedule)
    else:
        # always on
        clg_coil.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())
    
    clg_cap_f_of_temp = None
    clg_cap_f_of_flow = None
    clg_energy_input_ratio_f_of_temp = None
    clg_energy_input_ratio_f_of_flow = None
    clg_part_load_ratio = None
    clg_cap_f_of_temp_low_spd = None
    clg_energy_input_ratio_f_of_temp_low_spd = None

    if type == 'Residential Minisplit HP':
        # Performance curves
        # These coefficients are in SI units
        cool_cap_ft_coeffs_si = [0.7531983499655835, 0.003618193903031667, 0.0, 0.006574385031351544, -6.87181191015432e-05, 0.0]
        cool_eir_ft_coeffs_si = [-0.06376924779982301, -0.0013360593470367282, 1.413060577993827e-05, 0.019433076486584752, -4.91395947154321e-05, -4.909341249475308e-05]
        cool_cap_fflow_coeffs = [1, 0, 0]
        cool_eir_fflow_coeffs = [1, 0, 0]
        cool_plf_fplr_coeffs = [0.89, 0.11, 0]

        # Make the curves
        clg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, cool_cap_ft_coeffs_si, 'Cool-Cap-fT', 0, 100, 0, 100)
        clg_cap_f_of_flow = create_curve_quadratic(openstudio_model, cool_cap_fflow_coeffs, 'Cool-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, cool_eir_ft_coeffs_si, 'Cool-EIR-fT', 0, 100, 0, 100)
        clg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, cool_eir_fflow_coeffs, 'Cool-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        clg_part_load_ratio = create_curve_quadratic(openstudio_model, cool_plf_fplr_coeffs, 'Cool-PLF-fPLR', 0, 1, 0, 1, is_dimensionless = True)
        clg_cap_f_of_temp_low_spd = create_curve_biquadratic(openstudio_model, cool_cap_ft_coeffs_si, 'Cool-Cap-fT', 0, 100, 0, 100)
        clg_energy_input_ratio_f_of_temp_low_spd = create_curve_biquadratic(openstudio_model, cool_eir_ft_coeffs_si, 'Cool-EIR-fT', 0, 100, 0, 100)
        clg_coil.setRatedLowSpeedSensibleHeatRatio(0.73)
        clg_coil.setCondenserType('AirCooled')
    elif type == 'PSZ-AC' or type =='Split AC' or type == 'PTAC':
        clg_cap_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_cap_f_of_temp.setCoefficient1Constant(0.42415)
        clg_cap_f_of_temp.setCoefficient2x(0.04426)
        clg_cap_f_of_temp.setCoefficient3xPOW2(-0.00042)
        clg_cap_f_of_temp.setCoefficient4y(0.00333)
        clg_cap_f_of_temp.setCoefficient5yPOW2(-0.00008)
        clg_cap_f_of_temp.setCoefficient6xTIMESY(-0.00021)
        clg_cap_f_of_temp.setMinimumValueofx(17.0)
        clg_cap_f_of_temp.setMaximumValueofx(22.0)
        clg_cap_f_of_temp.setMinimumValueofy(13.0)
        clg_cap_f_of_temp.setMaximumValueofy(46.0)

        clg_cap_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_cap_f_of_flow.setCoefficient1Constant(0.77136)
        clg_cap_f_of_flow.setCoefficient2x(0.34053)
        clg_cap_f_of_flow.setCoefficient3xPOW2(-0.11088)
        clg_cap_f_of_flow.setMinimumValueofx(0.75918)
        clg_cap_f_of_flow.setMaximumValueofx(1.13877)

        clg_energy_input_ratio_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        clg_energy_input_ratio_f_of_temp.setCoefficient1Constant(1.23649)
        clg_energy_input_ratio_f_of_temp.setCoefficient2x(-0.02431)
        clg_energy_input_ratio_f_of_temp.setCoefficient3xPOW2(0.00057)
        clg_energy_input_ratio_f_of_temp.setCoefficient4y(-0.01434)
        clg_energy_input_ratio_f_of_temp.setCoefficient5yPOW2(0.00063)
        clg_energy_input_ratio_f_of_temp.setCoefficient6xTIMESY(-0.00038)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofx(17.0)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofx(22.0)
        clg_energy_input_ratio_f_of_temp.setMinimumValueofy(13.0)
        clg_energy_input_ratio_f_of_temp.setMaximumValueofy(46.0)

        clg_energy_input_ratio_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        clg_energy_input_ratio_f_of_flow.setCoefficient1Constant(1.20550)
        clg_energy_input_ratio_f_of_flow.setCoefficient2x(-0.32953)
        clg_energy_input_ratio_f_of_flow.setCoefficient3xPOW2(0.12308)
        clg_energy_input_ratio_f_of_flow.setMinimumValueofx(0.75918)
        clg_energy_input_ratio_f_of_flow.setMaximumValueofx(1.13877)

        clg_part_load_ratio = osmod.CurveQuadratic(openstudio_model)
        clg_part_load_ratio.setCoefficient1Constant(0.77100)
        clg_part_load_ratio.setCoefficient2x(0.22900)
        clg_part_load_ratio.setCoefficient3xPOW2(0.0)
        clg_part_load_ratio.setMinimumValueofx(0.0)
        clg_part_load_ratio.setMaximumValueofx(1.0)

        clg_cap_f_of_temp_low_spd = osmod.CurveBiquadratic(openstudio_model)
        clg_cap_f_of_temp_low_spd.setCoefficient1Constant(0.42415)
        clg_cap_f_of_temp_low_spd.setCoefficient2x(0.04426)
        clg_cap_f_of_temp_low_spd.setCoefficient3xPOW2(-0.00042)
        clg_cap_f_of_temp_low_spd.setCoefficient4y(0.00333)
        clg_cap_f_of_temp_low_spd.setCoefficient5yPOW2(-0.00008)
        clg_cap_f_of_temp_low_spd.setCoefficient6xTIMESY(-0.00021)
        clg_cap_f_of_temp_low_spd.setMinimumValueofx(17.0)
        clg_cap_f_of_temp_low_spd.setMaximumValueofx(22.0)
        clg_cap_f_of_temp_low_spd.setMinimumValueofy(13.0)
        clg_cap_f_of_temp_low_spd.setMaximumValueofy(46.0)

        clg_energy_input_ratio_f_of_temp_low_spd = osmod.CurveBiquadratic(openstudio_model)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient1Constant(1.23649)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient2x(-0.02431)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient3xPOW2(0.00057)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient4y(-0.01434)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient5yPOW2(0.00063)
        clg_energy_input_ratio_f_of_temp_low_spd.setCoefficient6xTIMESY(-0.00038)
        clg_energy_input_ratio_f_of_temp_low_spd.setMinimumValueofx(17.0)
        clg_energy_input_ratio_f_of_temp_low_spd.setMaximumValueofx(22.0)
        clg_energy_input_ratio_f_of_temp_low_spd.setMinimumValueofy(13.0)
        clg_energy_input_ratio_f_of_temp_low_spd.setMaximumValueofy(46.0)

        clg_coil.setRatedLowSpeedSensibleHeatRatio(openstudio.OptionalDouble(0.69))
        clg_coil.setBasinHeaterCapacity(10)
        clg_coil.setBasinHeaterSetpointTemperature(2.0)
    
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
    if clg_cap_f_of_temp_low_spd != None:
        clg_coil.setLowSpeedTotalCoolingCapacityFunctionOfTemperatureCurve(clg_cap_f_of_temp_low_spd)
    if clg_energy_input_ratio_f_of_temp_low_spd != None:
        clg_coil.setLowSpeedEnergyInputRatioFunctionOfTemperatureCurve(clg_energy_input_ratio_f_of_temp_low_spd)

    return clg_coil

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

def do_all_zones_have_surfaces(openstudio_model: osmod) -> bool:
    """
    Check if all the zones in the model have surfaces.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    Returns
    -------
    have_surfaces : bool
        True if there are surfaces.
    """
    # Check to see if all zones have surfaces.
    thermal_zones = openstudio_model.getThermalZones()
    for thermal_zone in thermal_zones:
      spaces = thermal_zone.spaces()
      for space in spaces:
          srfs = space.surfaces()
          if len(srfs) == 0:
              return False
    return True

def add_design_days_and_weather_file(openstudio_model: osmod, epw_path: str, ddy_path: str):
    """
    Add WeatherFile, Site, SiteGroundTemperatureBuildingSurface, SiteWaterMainsTemperature and DesignDays to the model using information from epw and ddy files.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    epw_path : str
        path to epw file.
    
    ddy_path : str
        path to ddy file.

    Returns
    -------
    success : bool
        True if successfully executed.
    """
    epw_file = openstudio.openstudioutilitiesfiletypes.EpwFile(epw_path)
    oswf = openstudio_model.getWeatherFile()
    oswf.setWeatherFile(openstudio_model, epw_file)
    weather_name = epw_file.city() + '_' + epw_file.stateProvinceRegion() + '_' + epw_file.country()
    weather_lat = epw_file.latitude()
    weather_lon = epw_file.longitude()
    weather_time = epw_file.timeZone()
    weather_elev = epw_file.elevation()

    # Add or update site data
    site = openstudio_model.getSite()
    site.setName(weather_name)
    site.setLatitude(weather_lat)
    site.setLongitude(weather_lon)
    site.setTimeZone(weather_time)
    site.setElevation(weather_elev)

    lb_epw = EPW(epw_path)
    grd_temps_dict = lb_epw.monthly_ground_temperature
    grd_temps_0_5 = grd_temps_dict[0.5]
    osm_sitegrd = osmod.SiteGroundTemperatureBuildingSurface(openstudio_model)
    for i, grd_temp in enumerate(grd_temps_0_5):
        osm_sitegrd.setTemperatureByMonth(i+1, grd_temp)

    water_temp = openstudio_model.getSiteWaterMainsTemperature()
    water_temp.setAnnualAverageOutdoorAirTemperature(lb_epw.dry_bulb_temperature.average)
    db_mthly_bounds = lb_epw.dry_bulb_temperature.average_monthly().bounds
    water_temp.setMaximumDifferenceInMonthlyAverageOutdoorAirTemperatures(db_mthly_bounds[1] - db_mthly_bounds[0])

    # Remove any existing Design Day objects that are in the file
    dgndys = openstudio_model.getDesignDays()
    for dgndy in dgndys:
        dgndy.remove()

    # Load in the ddy file based on convention that it is in
    rev_translate = openstudio.energyplus.ReverseTranslator()
    ddy_mod = rev_translate.loadModel(ddy_path)
    if ddy_mod.empty() == False:
        ddy_mod = ddy_mod.get()
        designday_objs = ddy_mod.getObjectsByType('OS:SizingPeriod:DesignDay')
        for dd in designday_objs:
            ddy_name = dd.name().get()
            if 'Htg 99.6% Condns DB' in ddy_name or 'Clg .4% Condns DB=>MWB' in ddy_name:
                openstudio_model.addObject(dd.clone())

def add_ptac(openstudio_model: osmod, thermal_zones: list[osmod.ThermalZone], cooling_type: str = 'Single Speed DX AC', heating_type: str = 'Gas', 
             hot_water_loop: osmod.PlantLoop = None, fan_type: str = 'Cycling',  
             ventilation: bool = True) -> list[osmod.ZoneHVACPackagedTerminalAirConditioner]:
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
        default: 'Two Speed DX AC', choices: ['Two Speed DX AC', 'Single Speed DX AC']

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

def add_schedule_type_limits(openstudio_model: osmod, standard_sch_type_limit: str = None, name: str = None, lower_limit_value: float = None,
                             upper_limit_value: float = None, numeric_type: str = None, unit_type: str = None) -> osmod.ScheduleTypeLimits:
    '''
    creates a schedule type limit
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_schedule_type_limits)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    standard_sch_type_limit : str, optional
        the name of a standard schedule type limit with predefined limits options are Dimensionless, Temperature, Humidity Ratio, Fractional, OnOff, and Activity
    
    name : str, optional
        schedule name.

    lower_limit_value : float, optional
        lower limt value 

    upper_limit_value : float, optional
        upper limt value

    numeric_type: str, optional
        the numeric type, options are Continuous or Discrete
    
    unit_type: str, optional
        the unit type, options are defined in EnergyPlus I/O reference. If unsure can just choose Dimensionless

    Returns
    -------
    schedule_type_limits : osmod.ScheduleTypeLimits
        the resultant schedule_type_limits.
    '''
    if standard_sch_type_limit == None:
        if lower_limit_value == None or upper_limit_value == None or numeric_type.nil == None or unit_type == None:
            print('If calling model_add_schedule_type_limits without a standard_sch_type_limit, you must specify all properties of ScheduleTypeLimits.')
            return False
        else:
            schedule_type_limits = osmod.ScheduleTypeLimits(openstudio_model)
            if name != None:
                schedule_type_limits.setName(name)
            schedule_type_limits.setLowerLimitValue(lower_limit_value)
            schedule_type_limits.setUpperLimitValue(upper_limit_value)
            schedule_type_limits.setNumericType(numeric_type)
            schedule_type_limits.setUnitType(unit_type)
    else:
        schedule_type_limits = openstudio_model.getScheduleTypeLimitsByName(standard_sch_type_limit)
        if schedule_type_limits.empty() == False:
            schedule_type_limits = schedule_type_limits.get()
            if str(schedule_type_limits.name()).lower() == 'temperature':
                schedule_type_limits.resetLowerLimitValue()
                schedule_type_limits.resetUpperLimitValue()
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('Temperature')
        else:
            standard_sch_type_limit_lwr = standard_sch_type_limit.lower()
            schedule_type_limits = osmod.ScheduleTypeLimits(openstudio_model)
            if standard_sch_type_limit_lwr == 'dimensionless':
                schedule_type_limits.setName('Dimensionless')
                schedule_type_limits.setLowerLimitValue(0.0)
                schedule_type_limits.setUpperLimitValue(1000.0)
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('Dimensionless')

            elif standard_sch_type_limit_lwr == 'temperature':
                schedule_type_limits.setName('Temperature')
                schedule_type_limits.setLowerLimitValue(0.0)
                schedule_type_limits.setUpperLimitValue(100.0)
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('Temperature')

            elif standard_sch_type_limit_lwr == 'humidity ratio': 
                schedule_type_limits.setName('Humidity Ratio')
                schedule_type_limits.setLowerLimitValue(0.0)
                schedule_type_limits.setUpperLimitValue(0.3)
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('Dimensionless')

            elif standard_sch_type_limit_lwr == 'fraction' or standard_sch_type_limit_lwr == 'fractional': 
                schedule_type_limits.setName('Fraction')
                schedule_type_limits.setLowerLimitValue(0.0)
                schedule_type_limits.setUpperLimitValue(1.0)
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('Dimensionless')

            elif standard_sch_type_limit_lwr == 'onoff':
                schedule_type_limits.setName('OnOff')
                schedule_type_limits.setLowerLimitValue(0)
                schedule_type_limits.setUpperLimitValue(1)
                schedule_type_limits.setNumericType('Discrete')
                schedule_type_limits.setUnitType('Availability')

            elif standard_sch_type_limit_lwr == 'activity': 
                schedule_type_limits.setName('Activity')
                schedule_type_limits.setLowerLimitValue(70.0)
                schedule_type_limits.setUpperLimitValue(1000.0)
                schedule_type_limits.setNumericType('Continuous')
                schedule_type_limits.setUnitType('ActivityLevel')
            else:
                print('Invalid standard_sch_type_limit for method model_add_schedule_type_limits.')

    return schedule_type_limits

def add_constant_schedule_ruleset(openstudio_model: osmod, value: float, name: str = None, sch_type_limit: str = 'Temperature') -> osmod.ScheduleRuleset:
    '''
    creates a constant schedule ruleset
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_constant_schedule_ruleset)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    value : float
        value for the schedule
    
    name : str, optional
        schedule name.

    sch_type_limit : str, optional
        the name of a schedule type limit options are Temperature (Default), Humidity Ratio, Fractional, OnOff, and Activity

    Returns
    -------
    schedule_ruleset : osmod.ScheduleRuleset
        the resultant ruleset.
    '''
    # check to see if schedule exists with same name and constant value and return if true
    if name != None:
        existing_sch = openstudio_model.getScheduleRulesetByName(name)
        if existing_sch.empty() == False:
            existing_sch = existing_sch.get()
            existing_day_sch_vals = existing_sch.defaultDaySchedule().values()
            if len(existing_day_sch_vals) == 1 and abs(existing_day_sch_vals[0] - value) < 1.0e-6:
                return existing_sch
    
    schedule = osmod.ScheduleRuleset(openstudio_model)
    if name != None:
        schedule.setName(name)
        schedule.defaultDaySchedule().setName(name + 'Default')

    sch_type_limits_obj = add_schedule_type_limits(openstudio_model, standard_sch_type_limit = sch_type_limit)
    schedule.setScheduleTypeLimits(sch_type_limits_obj)

    schedule.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), value)
    return schedule

def add_district_ambient_loop(openstudio_model: osmod, system_name: str = 'Ambient Loop') -> osmod.PlantLoop:
    '''
    Adds an ambient condenser water loop that will be used in a district to connect buildings as a shared sink/source for heat pumps.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_district_ambient_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    Returns
    -------
    ambient_loop : osmod.PlantLoop
        the resultant ambient_loop.
    '''
    # create ambient loop
    ambient_loop = osmod.PlantLoop(openstudio_model)
    ambient_loop.setName(system_name)
    ambient_loop_name = ambient_loop.name()
    # ambient loop sizing and controls
    ambient_loop.setMinimumLoopTemperature(5.0)
    ambient_loop.setMaximumLoopTemperature(80.0)

    amb_high_temp_f = 90 # Supplemental cooling below 65F
    amb_low_temp_f = 41 # Supplemental heat below 41F
    amb_temp_sizing_f = 102.2 # CW sized to deliver 102.2F
    amb_delta_t_r = 19.8 # 19.8F delta-T
    amb_high_temp_c = openstudio.convert(amb_high_temp_f, 'F', 'C').get()
    amb_low_temp_c = openstudio.convert(amb_low_temp_f, 'F', 'C').get()
    amb_temp_sizing_c = openstudio.convert(amb_temp_sizing_f, 'F', 'C').get()
    amb_delta_t_k = openstudio.convert(amb_delta_t_r, 'R', 'K').get()

    amb_high_temp_sch = add_constant_schedule_ruleset(openstudio_model, amb_high_temp_c, name = 'Ambient Loop High Temp-' + str(amb_high_temp_c) + 'degC')
    amb_low_temp_sch = add_constant_schedule_ruleset(openstudio_model, amb_low_temp_c, name = 'Ambient Loop Low Temp-' +  str(amb_low_temp_c) + 'degC')

    amb_stpt_manager = osmod.SetpointManagerScheduledDualSetpoint(openstudio_model)
    amb_stpt_manager.setName(ambient_loop_name + 'Supply Water Setpoint Manager')
    amb_stpt_manager.setHighSetpointSchedule(amb_high_temp_sch)
    amb_stpt_manager.setLowSetpointSchedule(amb_low_temp_sch)
    amb_stpt_manager.addToNode(ambient_loop.supplyOutletNode())

    sizing_plant = ambient_loop.sizingPlant()
    sizing_plant.setLoopType('Heating')
    sizing_plant.setDesignLoopExitTemperature(amb_temp_sizing_c)
    sizing_plant.setLoopDesignTemperatureDifference(amb_delta_t_k)

    # create pump
    pump = osmod.PumpVariableSpeed(openstudio_model)
    pump.setName(ambient_loop_name + 'Pump')
    pump.setRatedPumpHead(openstudio.convert(60.0, 'ftH_{2}O', 'Pa').get())
    pump.setPumpControlType('Intermittent')
    pump.addToNode(ambient_loop.supplyInletNode())

    # cooling
    district_cooling = osmod.DistrictCooling(openstudio_model)
    district_cooling.setNominalCapacity(1000000000000) # large number; no autosizing
    ambient_loop.addSupplyBranchForComponent(district_cooling)

    # heating
    if openstudio_model.version() < openstudio.VersionString('3.7.0'):
        district_heating = osmod.DistrictHeating(openstudio_model)
    else:
        district_heating = osmod.DistrictHeatingWater(openstudio_model)

    district_heating.setNominalCapacity(1000000000000) # large number; no autosizing
    ambient_loop.addSupplyBranchForComponent(district_heating)

    # add ambient water loop pipes
    supply_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_bypass_pipe.setName(ambient_loop_name + ' Supply Bypass')
    ambient_loop.addSupplyBranchForComponent(supply_bypass_pipe)

    demand_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_bypass_pipe.setName(ambient_loop_name + ' Demand Bypass')
    ambient_loop.addDemandBranchForComponent(demand_bypass_pipe)

    supply_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_outlet_pipe.setName(ambient_loop_name + ' Supply Outlet')
    supply_outlet_pipe.addToNode(ambient_loop.supplyOutletNode())

    demand_inlet_pipe = osmod.PipeAdiabatic.new(openstudio_model)
    demand_inlet_pipe.setName(ambient_loop_name + ' Demand Inlet')
    demand_inlet_pipe.addToNode(ambient_loop.demandInletNode())

    demand_outlet_pipe = osmod.PipeAdiabatic.new(openstudio_model)
    demand_outlet_pipe.setName(ambient_loop_name + ' Demand Outlet')
    demand_outlet_pipe.addToNode(ambient_loop.demandOutletNode())

    return ambient_loop

def get_or_add_ambient_water_loop(openstudio_model: osmod) -> osmod.PlantLoop:
    '''
    get a the existing ambient water loop if not add a new one.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_schedule_type_limits)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    Returns
    -------
    ambient_loop : osmod.PlantLoop
        the resultant ambient_loop.
    '''
    # retrieve the existing hot water loop or add a new one if necessary
    ambient_water_loop = openstudio_model.getPlantLoopByName('Ambient Loop')
    if ambient_water_loop.empty() == False:
        ambient_water_loop = ambient_water_loop.get()
    else:
        ambient_water_loop = add_district_ambient_loop(openstudio_model)
    
    return ambient_water_loop

def create_central_air_source_heat_pump(openstudio_model: osmod, hw_loop: osmod.PlantLoop, name: str = None, cop: float = 3.65) -> osmod.PlantComponentUserDefined:
    """
    A Prototype CentralAirSourceHeatPump object using PlantComponentUserDefined
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_central_air_source_heat_pump)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    hw_loop : osmod.PlantLoop
        a hot water loop served by the central air source heat pump
    
    name : str, optional
        name of the heat pump.
    
    cop : float, optional
        heat pump rated COP. Default = 3.65

    Returns
    -------
    ashp : osmod.PlantComponentUserDefined
        the resultant air-source heatpump.
    """
    # create the PlantComponentUserDefined object as a proxy for the Central Air Source Heat Pump
    plant_comp = osmod.PlantComponentUserDefined(openstudio_model)
    if name == None:
        name = hw_loop.name() + ' Central Air Source Heat Pump'

    # change equipment name for EMS validity
    plant_comp.setName(name)
    plant_comp_name = plant_comp.name()

    # set plant component properties
    plant_comp.setPlantLoadingMode('MeetsLoadWithNominalCapacityHiOutLimit')
    plant_comp.setPlantLoopFlowRequestMode('NeedsFlowIfLoopIsOn')

    # plant design volume flow rate internal variable
    vdot_des_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Plant Design Volume Flow Rate')
    vdot_des_int_var.setName( plant_comp_name + '_Vdot_Des_Int_Var')
    vdot_des_int_var.setInternalDataIndexKeyName(str(hw_loop.handle()))

    # inlet temperature internal variable
    tin_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Inlet Temperature for Plant Connection 1')
    tin_int_var.setName(plant_comp_name + '_Tin_Int_Var')
    tin_int_var.setInternalDataIndexKeyName(str(plant_comp.handle()))

    # inlet mass flow rate internal variable
    mdot_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Inlet Mass Flow Rate for Plant Connection 1')
    mdot_int_var.setName(plant_comp_name + '_Mdot_Int_Var')
    mdot_int_var.setInternalDataIndexKeyName(str(plant_comp.handle()))

    # inlet specific heat internal variable
    cp_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Inlet Specific Heat for Plant Connection 1')
    cp_int_var.setName(plant_comp_name + '_Cp_Int_Var')
    cp_int_var.setInternalDataIndexKeyName(str(plant_comp.handle()))

    # inlet density internal variable
    rho_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Inlet Density for Plant Connection 1')
    rho_int_var.setName(plant_comp_name + '_rho_Int_Var')
    rho_int_var.setInternalDataIndexKeyName(str(plant_comp.handle()))

    # load request internal variable
    load_int_var = osmod.EnergyManagementSystemInternalVariable(openstudio_model, 'Load Request for Plant Connection 1')
    load_int_var.setName(plant_comp_name + '_Load_Int_Var')
    load_int_var.setInternalDataIndexKeyName(str(plant_comp.handle()))

    # supply outlet node setpoint temperature sensor
    setpt_mgr_sch_sen = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
    setpt_mgr_sch_sen.setName(plant_comp_name + '_Setpt_Mgr_Temp_Sen')

    sp_mgers = hw_loop.supplyOutletNode().setpointManagers()
    for sp_mg in sp_mgers:
        if sp_mg.to_SetpointManagerScheduled().empty() == False:
            setpt_mgr_sch_sen.setKeyName(str(sp_mg.to_SetpointManagerScheduled().get().schedule().name()))

    # hw_loop.supplyOutletNode().setpointManagers.each do |m|
    # if m.to_SetpointManagerScheduled.is_initialized
    #     setpt_mgr_sch_sen.setKeyName(m.to_SetpointManagerScheduled.get.schedule.name.to_s)


    # outdoor air drybulb temperature sensor
    oa_dbt_sen = osmod.EnergyManagementSystemSensor(openstudio_model, 'Site Outdoor Air Drybulb Temperature')
    oa_dbt_sen.setName(plant_comp_name + '_OA_DBT_Sen')
    oa_dbt_sen.setKeyName('Environment')

    # minimum mass flow rate actuator
    mdot_min_act = plant_comp.minimumMassFlowRateActuator().get()
    mdot_min_act.setName(plant_comp_name + '_Mdot_Min_Act')

    # maximum mass flow rate actuator
    mdot_max_act = plant_comp.maximumMassFlowRateActuator().get()
    mdot_max_act.setName(plant_comp_name + '_Mdot_Max_Act')

    # design flow rate actuator
    vdot_des_act = plant_comp.designVolumeFlowRateActuator().get()
    vdot_des_act.setName(plant_comp_name + '_Vdot_Des_Act')

    # minimum loading capacity actuator
    cap_min_act = plant_comp.minimumLoadingCapacityActuator().get()
    cap_min_act.setName(plant_comp_name + '_Cap_Min_Act')

    # maximum loading capacity actuator
    cap_max_act = plant_comp.maximumLoadingCapacityActuator().get()
    cap_max_act.setName(plant_comp_name + '_Cap_Max_Act')

    # optimal loading capacity actuator
    cap_opt_act = plant_comp.optimalLoadingCapacityActuator().get()
    cap_opt_act.setName(plant_comp_name + '_Cap_Opt_Act')

    # outlet temperature actuator
    tout_act = plant_comp.outletTemperatureActuator().get()
    tout_act.setName(plant_comp_name + '_Tout_Act')

    # mass flow rate actuator
    mdot_req_act = plant_comp.massFlowRateActuator().get()
    mdot_req_act.setName(plant_comp_name + '_Mdot_Req_Act')

    # heat pump COP curve
    constant_coeff = 1.932 + (cop - 3.65)
    hp_cop_curve = osmod.CurveQuadratic(openstudio_model)
    hp_cop_curve.setCoefficient1Constant(constant_coeff)
    hp_cop_curve.setCoefficient2x(0.227674286)
    hp_cop_curve.setCoefficient3xPOW2(-0.007313143)
    hp_cop_curve.setMinimumValueofx(1.67)
    hp_cop_curve.setMaximumValueofx(12.78)
    hp_cop_curve.setInputUnitTypeforX('Temperature')
    hp_cop_curve.setOutputUnitType('Dimensionless')

    # heat pump COP curve index variable
    hp_cop_curve_idx_var = osmod.EnergyManagementSystemCurveOrTableIndexVariable(openstudio_model, hp_cop_curve)

    # high outlet temperature limit actuator
    tout_max_act = osmod.EnergyManagementSystemActuator(plant_comp, 'Plant Connection 1', 'High Outlet Temperature Limit')
    tout_max_act.setName(plant_comp_name + '_Tout_Max_Act')

    # init program
    init_pgrm = plant_comp.plantInitializationProgram().get()
    init_pgrm.setName(plant_comp_name + '_Init_Pgrm')

    init_pgrm_body = f"SET Loop_Exit_Temp = {hw_loop.sizingPlant().designLoopExitTemperature()}" + "\n" +\
    f"SET Loop_Delta_Temp = {hw_loop.sizingPlant().loopDesignTemperatureDifference()}" + "\n" +\
    f"SET Cp = @CPHW Loop_Exit_Temp" + "\n" +\
    f"SET rho = @RhoH2O Loop_Exit_Temp" + "\n" +\
    f"SET {vdot_des_act.handle()} = {vdot_des_int_var.handle()}" + "\n" +\
    f"SET {mdot_min_act.handle()} =  0" + "\n" +\
    f"SET Mdot_Max = {vdot_des_int_var.handle()} * rho" + "\n" +\
    f"SET {mdot_max_act.handle()} = Mdot_Max" + "\n" +\
    f"SET Cap = Mdot_Max * Cp * Loop_Delta_Temp" + "\n" +\
    f"SET {cap_min_act.handle()} = 0" + "\n" +\
    f"SET {cap_max_act.handle()} = Cap" + "\n" +\
    f"SET {cap_opt_act.handle()} = 1 * Cap"

    init_pgrm.setBody(init_pgrm_body)

    # sim program
    sim_pgrm = plant_comp.plantSimulationProgram().get()
    sim_pgrm.setName(f"{plant_comp_name}_Sim_Pgrm")

    sim_pgrm_body = f"SET tmp = {load_int_var.handle()}" + "\n" +\
    f"SET tmp = {tin_int_var.handle()}" + "\n" +\
    f"SET tmp = {mdot_int_var.handle()}" + "\n" +\
    f"SET {tout_max_act.handle()} = 75.0" + "\n" +\
    f"IF {load_int_var.handle()} == 0" + "\n" +\
    f"SET {tout_act.handle()} = {tin_int_var.handle()}" + "\n" +\
    f"SET {mdot_req_act.handle()} = 0" + "\n" +\
    f"SET Elec = 0" + "\n" +\
    f"RETURN" + "\n" +\
    f"ENDIF" + "\n" +\
    f"IF {load_int_var.handle()} >= {cap_max_act.handle()}" + "\n" +\
    f"SET Qdot = {cap_max_act.handle()}" + "\n" +\
    f"SET Mdot = {mdot_max_act.handle()}" + "\n" +\
    f"SET {mdot_req_act.handle()} = Mdot" + "\n" +\
    f"SET {tout_act.handle()} = (Qdot / (Mdot * {cp_int_var.handle()})) + {tin_int_var.handle()}" + "\n" +\
    f"IF {tout_act.handle()} > {tout_max_act.handle()}" + "\n" +\
    f"SET {tout_act.handle()} = {tout_max_act.handle()}" + "\n" +\
    f"SET Qdot = Mdot * {cp_int_var.handle()} * ({tout_act.handle()} - {tin_int_var.handle()})" + "\n" +\
    f"ENDIF" + "\n" +\
    f"ELSE" + "\n" +\
    f"SET Qdot = {load_int_var.handle()}" + "\n" +\
    f"SET {tout_act.handle()} = {setpt_mgr_sch_sen.handle()}" + "\n" +\
    f"SET Mdot = Qdot / ({cp_int_var.handle()} * ({tout_act.handle()} - {tin_int_var.handle()}))" + "\n" +\
    f"SET {mdot_req_act.handle()} = Mdot" + "\n" +\
    f"ENDIF" + "\n" +\
    f"SET Tdb = {oa_dbt_sen.handle()}" + "\n" +\
    f"SET COP = @CurveValue {hp_cop_curve_idx_var.handle()} Tdb" + "\n" +\
    f"SET EIR = 1 / COP" + "\n" +\
    f"SET Pwr = Qdot * EIR" + "\n" +\
    f"SET Elec = Pwr * SystemTimestep * 3600"
    
    sim_pgrm.setBody(sim_pgrm_body)

    # init program calling manager
    init_mgr = plant_comp.plantInitializationProgramCallingManager().get()
    init_mgr.setName(f"{plant_comp_name}_Init_Pgrm_Mgr")

    # sim program calling manager
    sim_mgr = plant_comp.plantSimulationProgramCallingManager.get
    sim_mgr.setName(f"{plant_comp_name}_Sim_Pgrm_Mgr")

    # metered output variable
    elec_mtr_out_var = osmod.EnergyManagementSystemMeteredOutputVariable(openstudio_model, f"{plant_comp_name} Electricity Consumption")
    elec_mtr_out_var.setName(f"{plant_comp_name} Electricity Consumption")
    elec_mtr_out_var.setEMSVariableName('Elec')
    elec_mtr_out_var.setUpdateFrequency('SystemTimestep')
    elec_mtr_out_var.setString(4, sim_pgrm.handle.to_s)
    elec_mtr_out_var.setResourceType('Electricity')
    elec_mtr_out_var.setGroupType('HVAC')
    elec_mtr_out_var.setEndUseCategory('Heating')
    elec_mtr_out_var.setEndUseSubcategory('')
    elec_mtr_out_var.setUnits('J')

    # add to supply side of hot water loop if specified
    hw_loop.addSupplyBranchForComponent(plant_comp)

    # add operation scheme
    htg_op_scheme = osmod.PlantEquipmentOperationHeatingLoad(openstudio_model)
    htg_op_scheme.addEquipment(1000000000, plant_comp)
    hw_loop.setPlantEquipmentOperationHeatingLoad(htg_op_scheme)

    return plant_comp

def create_boiler_hot_water(openstudio_model: osmod, hw_loop: osmod.PlantLoop, name: str = 'Boiler', fuel_type: str = 'NaturalGas', 
                            draft_type: str = 'Natural', nominal_thermal_efficiency: float = 0.80, eff_curve_temp_eval_var: str = 'LeavingBoiler', 
                            flow_mode: str = 'LeavingSetpointModulated', lvg_temp_dsgn_c: float = 82.2, out_temp_lmt_c: float = 95.0, 
                            min_plr: float = 0.0, max_plr: float = 1.2, opt_plr: float = 1.0, sizing_factor: float = None) -> osmod.BoilerHotWater:
    """
    creates a hot water loop with a boiler, district heating, or water-water-heat pump and adds it to the model.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_boiler_hot_water)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    hw_loop : osmod.PlantLoop
        a hot water loop served by the boiler
    
    name : str, optional
        name of boiler.

    fuel_type : str, optional
        type of fuel serving the boiler, 'NaturalGas', 'Propane'. Default to 'NaturalGas'

    draft_type : str, optional
        Boiler type Condensing, MechanicalNoncondensing, Natural (default).

    nominal_thermal_efficiency : float, optional
        boiler nominal thermal efficiency. Default to 0.80.

    eff_curve_temp_eval_var : str, optional
        LeavingBoiler or EnteringBoiler temperature for the boiler efficiency curve.
    
    flow_mode : str, optional
        boiler flow mode. Default to 'LeavingSetpointModulated'

    lvg_temp_dsgn_f : str, optional
        boiler leaving design temperature in degrees Fahrenheit note that this field is deprecated in OS versions 3.0+
    
    out_temp_lmt_f : str, optional
        boiler outlet temperature limit in degrees Fahrenheit

    min_plr : float, optional
        boiler minimum part load ratio
    
    max_plr : float, optional
        boiler maximum part load ratio
    
    opt_plr : float, optional
        boiler optimum part load ratio

    sizing_factor : float, optional
        boiler oversizing factor
    
    Returns
    -------
    hw_loop : osmod.PlantLoop
        the resultant hot water loop 
    """
    # create the boiler
    boiler = osmod.BoilerHotWater(openstudio_model)
    boiler.setName(name)

    if fuel_type == None or fuel_type == 'Gas':
        boiler.setFuelType('NaturalGas')
    elif fuel_type == 'Propane' or fuel_type == 'PropaneGas':
        boiler.setFuelType('Propane')
    else:
        boiler.setFuelType(fuel_type)

    boiler.setNominalThermalEfficiency(nominal_thermal_efficiency)
    boiler.setEfficiencyCurveTemperatureEvaluationVariable(eff_curve_temp_eval_var)
    boiler.setBoilerFlowMode(flow_mode)

    if openstudio_model.version() < openstudio.VersionString('3.0.0'):
        boiler.setDesignWaterOutletTemperature(lvg_temp_dsgn_c)

    boiler.setWaterOutletUpperTemperatureLimit(out_temp_lmt_c)

    # logic to set different defaults for condensing boilers if not specified
    if draft_type == 'Condensing':
        if openstudio_model.version() < openstudio.VersionString('3.0.0'):
            # default to 120 degrees Fahrenheit (48.49 degrees Celsius)
            boiler.setDesignWaterOutletTemperature(lvg_temp_dsgn_c)
        boiler.setNominalThermalEfficiency(nominal_thermal_efficiency)


    boiler.setMinimumPartLoadRatio(min_plr)
    boiler.setMaximumPartLoadRatio(max_plr)
    boiler.setOptimumPartLoadRatio(opt_plr)
    if sizing_factor != None:
        boiler.setSizingFactor(sizing_factor)

    # add to supply side of hot water loop if specified
    hw_loop.addSupplyBranchForComponent(boiler)

    return boiler

def add_hw_loop(openstudio_model: osmod, boiler_fuel_type: str, ambient_loop: osmod.PlantLoop = None, system_name: str = 'Hot Water Loop', 
                dgn_sup_wtr_temp: float = 82.2, dgn_sup_wtr_temp_delt: float = 11.1, pump_spd_ctrl: str = 'Variable',  pump_tot_hd: float = None,
                boiler_draft_type: str = 'Natural', boiler_eff_curve_temp_eval_var: str = None, boiler_lvg_temp_dsgn: float = None, 
                boiler_out_temp_lmt: float = None, boiler_max_plr: float = None, boiler_sizing_factor: float = None) -> osmod.PlantLoop:
    """
    creates a hot water loop with a boiler, district heating, or water-water-heat pump and adds it to the model.
    It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_hw_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    boiler_fuel_type : str
        valid choices are Electricity, NaturalGas, Propane, PropaneGas, FuelOilNo1, FuelOilNo2, DistrictHeating, DistrictHeatingWater, DistrictHeatingSteam, HeatPump
    
    ambient_loop : osmod.PlantLoop, optional
        The condenser loop for the heat pump. Only used when boiler_fuel_type is HeatPump.

    system_name : str, optional
        name of the system. Default to 'Hot Water Loop'

    dgn_sup_wtr_temp : float, optional
        design supply water temperature, default to 82.2C (180F).

    dgn_sup_wtr_temp_delt : float, optional
        design supply-return water temperature difference in Kelvin, default 11.1K

    pump_spd_ctrl : str, optional
        pump speed control type, Constant or Variable (default).
    
    pump_tot_hd : float, optional
        pump head in ft H2O.

    boiler_draft_type : str, optional
        Boiler type Condensing, MechanicalNoncondensing, Natural (default)
    
    boiler_eff_curve_temp_eval_var : str, optional
        LeavingBoiler or EnteringBoiler temperature for the boiler efficiency curve

    boiler_lvg_temp_dsgn : str, optional
        boiler leaving design temperature in degreesC
    
    boiler_out_temp_lmt : str, optional
        boiler outlet temperature limit in degreesC
    
    boiler_max_plr : str, optional
        boiler maximum part load ratio

    boiler_sizing_factor : str, optional
        boiler oversizing factor
    
    Returns
    -------
    hw_loop : osmod.PlantLoop
        the resultant hot water loop 
    """
    # create hot water loop
    hw_loop = osmod.PlantLoop(openstudio_model)
    hw_loop.setName(system_name)
    hw_lp_name = hw_loop.name()
    # hot water loop sizing and controls
    sizing_plant = hw_loop.sizingPlant()
    sizing_plant.setLoopType('Heating')
    sizing_plant.setDesignLoopExitTemperature(dgn_sup_wtr_temp)
    sizing_plant.setLoopDesignTemperatureDifference(dgn_sup_wtr_temp_delt)
    hw_loop.setMinimumLoopTemperature(10.0)

    hw_temp_sch = add_constant_schedule_ruleset(openstudio_model, dgn_sup_wtr_temp, name = hw_lp_name + '-Temp-'  + str(dgn_sup_wtr_temp) + 'degC')
    hw_stpt_manager = osmod.SetpointManagerScheduled(openstudio_model, hw_temp_sch)
    hw_stpt_manager.setName(hw_lp_name + 'Setpoint Manager')
    hw_stpt_manager.addToNode(hw_loop.supplyOutletNode())

    # create hot water pump
    if pump_spd_ctrl == 'Constant':
        hw_pump = osmod.PumpConstantSpeed(openstudio_model)
    elif pump_spd_ctrl == 'Variable':
        hw_pump = osmod.PumpVariableSpeed(openstudio_model)
    else:
        hw_pump = osmod.PumpVariableSpeed(openstudio_model)

    hw_pump.setName(hw_lp_name + 'Pump')
    if pump_tot_hd == None:
        pump_tot_hd_pa = openstudio.convert(60, 'ftH_{2}O', 'Pa').get()
    else:
        pump_tot_hd_pa = openstudio.convert(pump_tot_hd, 'ftH_{2}O', 'Pa').get()

    hw_pump.setRatedPumpHead(pump_tot_hd_pa)
    hw_pump.setMotorEfficiency(0.9)
    hw_pump.setPumpControlType('Intermittent')
    hw_pump.addToNode(hw_loop.supplyInletNode)
    # switch statement to handle district heating name change
    if openstudio_model.version() < openstudio.VersionString('3.7.0'):
        if boiler_fuel_type == 'DistrictHeatingWater' or boiler_fuel_type == 'DistrictHeatingSteam':
            boiler_fuel_type = 'DistrictHeating'
    else:
        if boiler_fuel_type == 'DistrictHeating':
            boiler_fuel_type = 'DistrictHeatingWater' 

    # create boiler and add to loop
    if boiler_fuel_type == 'DistrictHeating':
        district_heat = osmod.DistrictHeating(openstudio_model)
        district_heat.setName(hw_lp_name +  ' District Heating')
        district_heat.autosizeNominalCapacity()
        hw_loop.addSupplyBranchForComponent(district_heat)
    elif boiler_fuel_type == 'DistrictHeatingWater':
        district_heat = osmod.DistrictHeatingWater(openstudio_model)
        district_heat.setName(hw_lp_name + ' District Heating')
        district_heat.autosizeNominalCapacity()
        hw_loop.addSupplyBranchForComponent(district_heat)
    elif boiler_fuel_type == 'DistrictHeatingSteam':
        district_heat = osmod.DistrictHeatingSteam(openstudio_model)
        district_heat.setName(hw_lp_name + ' District Heating')
        district_heat.autosizeNominalCapacity()
        hw_loop.addSupplyBranchForComponent(district_heat)
    elif boiler_fuel_type == 'HeatPump' or boiler_fuel_type == 'AmbientLoop':
        # Ambient Loop
        water_to_water_hp = osmod.HeatPumpWaterToWaterEquationFitHeating(openstudio_model)
        water_to_water_hp.setName(hw_lp_name + ' Water to Water Heat Pump')
        hw_loop.addSupplyBranchForComponent(water_to_water_hp)
        # Get or add an ambient loop
        if ambient_loop == None:
            ambient_loop = get_or_add_ambient_water_loop(openstudio_model)
            
        ambient_loop.addDemandBranchForComponent(water_to_water_hp)
    # Central Air Source Heat Pump
    elif boiler_fuel_type == 'AirSourceHeatPump' or boiler_fuel_type == 'ASHP':
        create_central_air_source_heat_pump(openstudio_model, hw_loop)

    # Boiler
    elif  boiler_fuel_type == 'Electricity' or boiler_fuel_type == 'Gas' or boiler_fuel_type == 'NaturalGas'or boiler_fuel_type == 'Propane' or boiler_fuel_type == 'PropaneGas' or boiler_fuel_type == 'FuelOilNo1' or boiler_fuel_type ==  'FuelOilNo2':
        if boiler_lvg_temp_dsgn == None:
            lvg_temp_dsgn = dgn_sup_wtr_temp
        else:
            lvg_temp_dsgn = boiler_lvg_temp_dsgn

        if boiler_out_temp_lmt == None:
            out_temp_lmt = 95 #degC
        else:
            out_temp_lmt = boiler_out_temp_lmt

        boiler = create_boiler_hot_water(openstudio_model, hw_loop,
                                         fuel_type = boiler_fuel_type,
                                         draft_type = boiler_draft_type,
                                         nominal_thermal_efficiency = 0.78,
                                         eff_curve_temp_eval_var = boiler_eff_curve_temp_eval_var,
                                         lvg_temp_dsgn_c = lvg_temp_dsgn,
                                         out_temp_lmt_c = out_temp_lmt,
                                         max_plr = boiler_max_plr,
                                         sizing_factor = boiler_sizing_factor)
        
        # Adding temperature setpoint controller at boiler outlet causes simulation errors
        # boiler_stpt_manager = OpenStudio::Model::SetpointManagerScheduled.new(self, hw_temp_sch)
        # boiler_stpt_manager.setName("Boiler outlet setpoint manager")
        # boiler_stpt_manager.addToNode(boiler.outletModelObject.get.to_Node.get)
    else:
        print("Boiler fuel type is not valid, no boiler will be added.")

    # add hot water loop pipes
    supply_equipment_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_equipment_bypass_pipe.setName(f"{hw_lp_name} Supply Equipment Bypass")
    hw_loop.addSupplyBranchForComponent(supply_equipment_bypass_pipe)

    coil_bypass_pipe = openstudio_model.PipeAdiabatic.new(openstudio_model)
    coil_bypass_pipe.setName(f"{hw_lp_name} Coil Bypass")
    hw_loop.addDemandBranchForComponent(coil_bypass_pipe)

    supply_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_outlet_pipe.setName(f"{hw_lp_name} Supply Outlet")
    supply_outlet_pipe.addToNode(hw_loop.supplyOutletNode())

    demand_inlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_inlet_pipe.setName(f"{hw_lp_name} Demand Inlet")
    demand_inlet_pipe.addToNode(hw_loop.demandInletNode())

    demand_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_outlet_pipe.setName(f"{hw_lp_name} Demand Outlet")
    demand_outlet_pipe.addToNode(hw_loop.demandOutletNode())

    return hw_loop

def chw_sizing_control(openstudio_model: osmod, chilled_water_loop: osmod.PlantLoop, dsgn_sup_wtr_temp: float, dsgn_sup_wtr_temp_delt: float) -> bool:
    """
    Apply sizing and controls to chilled water loop.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:chw_sizing_control)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    condenser_water_loop : osmod.PlantLoop
        chilled water loop

    dsgn_sup_wtr_temp : float
        design chilled water supply T in degC

    dsgn_sup_wtr_temp_delt : float
        design chilled water supply delta T in degC

    Returns
    -------
    result : bool
        True if successful
    """
    # chilled water loop sizing and controls
    chilled_water_loop.setMinimumLoopTemperature(1.0)
    chilled_water_loop.setMaximumLoopTemperature(40.0)
    sizing_plant = chilled_water_loop.sizingPlant()
    sizing_plant.setLoopType('Cooling')
    sizing_plant.setDesignLoopExitTemperature(dsgn_sup_wtr_temp)
    sizing_plant.setLoopDesignTemperatureDifference(dsgn_sup_wtr_temp_delt)
    chw_temp_sch = add_constant_schedule_ruleset(openstudio_model, dsgn_sup_wtr_temp, name = f"{chilled_water_loop.name()} Temp - {dsgn_sup_wtr_temp}")
    chw_stpt_manager = osmod.SetpointManagerScheduled(openstudio_model, chw_temp_sch)
    chw_stpt_manager.setName(f"{chilled_water_loop.name()} Setpoint Manager")
    chw_stpt_manager.addToNode(chilled_water_loop.supplyOutletNode())
    # @todo check the CHW Setpoint from standards
    # @todo Should be a OutdoorAirReset, see the changes I've made in Standards.PlantLoop.apply_prm_baseline_temperatures

    return True

def kw_per_ton_to_cop(kw_per_ton: float) -> float:
    """
    A helper method to convert from kW/ton to COP
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:plant_loop_set_chw_pri_sec_configuration)
    
    Parameters
    ----------
    kw_per_ton : float
        kw_per_ton value.

    Returns
    -------
    cop : float
        the cop 
    """
    return 3.517 / kw_per_ton

def add_waterside_economizer(openstudio_model: osmod, chilled_water_loop: osmod.PlantLoop, condenser_water_loop: osmod.PlantLoop, 
                             integrated: bool = True) -> osmod.HeatExchangerFluidToFluid:
    """
    Creates a chilled water loop and adds it to the model.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_chw_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    chilled_water_loop : osmod.PlantLoop
        the chilled water loop
    
    condenser_water_loop : osmod.PlantLoop
        condenser water loop for water-cooled chillers.

    integrated : bool, optional
        - when set to true, models an integrated waterside economizer 
        - Integrated: in series with chillers, can run simultaneously with chillers 
        - Non-Integrated: in parallel with chillers, chillers locked out during operation

    Returns
    -------
    water_side_economizer : osmod.HeatExchangerFluidToFluid
        the resultant water_side_economizer
    """
    # make a new heat exchanger
    heat_exchanger = osmod.HeatExchangerFluidToFluid(openstudio_model)
    heat_exchanger.setHeatExchangeModelType('CounterFlow')
    # zero degree minimum necessary to allow both economizer and heat exchanger to operate in both integrated and non-integrated archetypes
    # possibly results from an EnergyPlus issue that didn't get resolved correctly https://github.com/NREL/EnergyPlus/issues/5626
    heat_exchanger.setMinimumTemperatureDifferencetoActivateHeatExchanger(openstudio.convert(0.0, 'R', 'K').get())
    heat_exchanger.setHeatTransferMeteringEndUseType('FreeCooling')
    heat_exchanger.setOperationMinimumTemperatureLimit(openstudio.convert(35.0, 'F', 'C').get())
    heat_exchanger.setOperationMaximumTemperatureLimit(openstudio.convert(72.0, 'F', 'C').get())
    heat_exchanger.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())

    # get the chillers on the chilled water loop
    chillers = chilled_water_loop.supplyComponents('OS:Chiller:Electric:EIR'.to_IddObjectType)

    if integrated:
        if chillers.empty():
            print(f"No chillers were found on {chilled_water_loop.name()}; only modeling waterside economizer")
        
        # set methods for integrated heat exchanger
        heat_exchanger.setName('Integrated Waterside Economizer Heat Exchanger')
        heat_exchanger.setControlType('CoolingDifferentialOnOff')

        # add the heat exchanger to the chilled water loop upstream of the chiller
        heat_exchanger.addToNode(chilled_water_loop.supplyInletNode())

        # Copy the setpoint managers from the plant's supply outlet node to the chillers and HX outlets.
        # This is necessary so that the correct type of operation scheme will be created.
        # Without this, OS will create an uncontrolled operation scheme and the chillers will never run.
        chw_spms = chilled_water_loop.supplyOutletNode().setpointManagers()
        objs = []
        objs = []
        for chiller in chillers:
            objs.append(chiller.to_ChillerElectricEIR().get())
        objs.append(heat_exchanger)

        for aobj in objs:
            outlet = aobj.supplyOutletModelObject().get().to_Node().get()

            for spm in chw_spms:
                new_spm = spm.clone().to_SetpointManager().get()
                new_spm.addToNode(outlet)
                print(f"Copied SPM {spm.name()} to the outlet of {aobj.name()}.")
    else:
        # non-integrated
        # if the heat exchanger can meet the entire load, the heat exchanger will run and the chiller is disabled.
        # In E+, only one chiller can be tied to a given heat exchanger, so if you have multiple chillers,
        # they will cannot be tied to a single heat exchanger without EMS.
        chiller = None
        # if chillers.empty():
        if len(chillers) == 0:
            print(f"No chillers were found on {chilled_water_loop.name()}; cannot add a non-integrated waterside economizer.")
            return None

        heat_exchanger.setControlType('CoolingSetpointOnOff')
        if len(chillers) > 1:
            chiller = chillers[0]
            print(f"More than one chiller was found on {chilled_water_loop.name()}.  EnergyPlus only allows a single chiller to be interlocked with the HX.  Chiller {chiller.name()} was selected.  Additional chillers will not be locked out during HX operation.")
        else: # 1 chiller
            chiller = chillers[0]
            print(f"Chiller '{chiller.name()}' will be locked out during HX operation.")

        chiller = chiller.to_ChillerElectricEIR().get()

        # set methods for non-integrated heat exchanger
        heat_exchanger.setName('Non-Integrated Waterside Economizer Heat Exchanger')
        heat_exchanger.setControlType('CoolingSetpointOnOffWithComponentOverride')

        # add the heat exchanger to a supply side branch of the chilled water loop parallel with the chiller(s)
        chilled_water_loop.addSupplyBranchForComponent(heat_exchanger)

        # Copy the setpoint managers from the plant's supply outlet node to the HX outlet.
        # This is necessary so that the correct type of operation scheme will be created.
        # Without this, the HX will never run
        chw_spms = chilled_water_loop.supplyOutletNode().setpointManagers()
        outlet = heat_exchanger.supplyOutletModelObject().get().to_Node().get()
        for spm in chw_spms:
            new_spm = spm.clone().to_SetpointManager().get()
            new_spm.addToNode(outlet)
            print(f"Copied SPM {spm.name()} to the outlet of {heat_exchanger.name()}.")

        # set the supply and demand inlet fields to interlock the heat exchanger with the chiller
        chiller_supply_inlet = chiller.supplyInletModelObject().get().to_Node().get()
        heat_exchanger.setComponentOverrideLoopSupplySideInletNode(chiller_supply_inlet)
        chiller_demand_inlet = chiller.demandInletModelObject().get().to_Node().get()
        heat_exchanger.setComponentOverrideLoopDemandSideInletNode(chiller_demand_inlet)

        # check if the chilled water pump is on a branch with the chiller.
        # if it is, move this pump before the splitter so that it can push water through either the chiller or the heat exchanger.
        pumps_on_branches = []
        # search for constant and variable speed pumps  between supply splitter and supply mixer.
        supply_comps = chilled_water_loop.supplyComponents(chilled_water_loop.supplySplitter(), chilled_water_loop.supplyMixer())
        for supply_comp in supply_comps:
            if supply_comp.to_PumpConstantSpeed().is_initialized():
                pumps_on_branches.append(supply_comp.to_PumpConstantSpeed().get())
            elif supply_comp.to_PumpVariableSpeed().is_initialized():
                pumps_on_branches.append(supply_comp.to_PumpVariableSpeed().get())

        # If only one pump is found, clone it, put the clone on the supply inlet node, and delete the original pump.
        # If multiple branch pumps, clone the first pump found, add it to the inlet of the heat exchanger, and warn user.
        if len(pumps_on_branches) == 1:
            pump = pumps_on_branches[0]
            pump_clone = pump.clone(openstudio_model).to_StraightComponent().get()
            pump_clone.addToNode(chilled_water_loop.supplyInletNode())
            pump.remove()
            print('Since you need a pump to move water through the HX, the pump serving the chiller was moved so that it can also serve the HX depending on the desired control sequence.')
        elif len(pumps_on_branches) > 1:
            hx_inlet_node = heat_exchanger.inletModelObject().get().to_Node().get()
            pump = pumps_on_branches[0]
            pump_clone = pump.clone(openstudio_model).to_StraightComponent().get()
            pump_clone.addToNode(hx_inlet_node)
            print('Found 2 or more pumps on branches.  Since you need a pump to move water through the HX, the first pump encountered was copied and placed in series with the HX.  This pump might not be reasonable for this duty, please check.')
        
    # add heat exchanger to condenser water loop
    condenser_water_loop.addDemandBranchForComponent(heat_exchanger)

    # change setpoint manager on condenser water loop to allow waterside economizing
    dsgn_sup_wtr_temp_f = 42.0
    dsgn_sup_wtr_temp_c = openstudio.convert(dsgn_sup_wtr_temp_f, 'F', 'C').get()
    spms = condenser_water_loop.supplyOutletNode().setpointManagers()
    for spm in spms:
        if spm.to_SetpointManagerFollowOutdoorAirTemperature().is_initialized():
            spm = spm.to_SetpointManagerFollowOutdoorAirTemperature().get()
            spm.setMinimumSetpointTemperature(dsgn_sup_wtr_temp_c)
        elif spm.to_SetpointManagerScheduled().is_initialized():
            spm = spm.to_SetpointManagerScheduled().get()
            cw_temp_sch = add_constant_schedule_ruleset(openstudio_model, dsgn_sup_wtr_temp_c,
                                                        name = f"#{chilled_water_loop.name()} Temp - {dsgn_sup_wtr_temp_c}C")
            spm.setSchedule(cw_temp_sch)
            print(f"Changing condenser water loop setpoint for '{condenser_water_loop.name()}' to '{cw_temp_sch.name()}' to account for the waterside economizer.")
        else:
            print(f"Condenser water loop '{condenser_water_loop.name()}' setpoint manager '{spm.name()}' is not a recognized setpoint manager type.  Cannot change to account for the waterside economizer.")

    print(f"Added {heat_exchanger.name()} to condenser water loop {condenser_water_loop.name()} and chilled water loop {chilled_water_loop.name()} to enable waterside economizing.")
    return heat_exchanger

def add_chw_loop(openstudio_model: osmod, system_name: str = 'Chilled Water Loop', cooling_fuel: str = 'Electricity', dsgn_sup_wtr_temp: float = 6.7, dsgn_sup_wtr_temp_delt: float = 5.6, 
                 chw_pumping_type: str = 'const_pri', chiller_cooling_type: str = None, chiller_condenser_type: str = None, chiller_compressor_type: str = None, num_chillers: int = 1, 
                 condenser_water_loop: osmod.PlantLoop = None, waterside_economizer: str = None) -> osmod.PlantLoop:
    """
    Creates a chilled water loop and adds it to the model.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_chw_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    system_name : str, optional
        the name of the system, defaulted to 'Chilled Water Loop'
    
    cooling_fuel : str, optional
        cooling fuel. Valid choices are: Electricity (default), DistrictCooling.

    dsgn_sup_wtr_temp : float, optional
        design supply water temperature in degC, default 6.7C

    dsgn_sup_wtr_temp_delt : float, optional
        design supply-return water temperature difference in degC, 5.6C

    chw_pumping_type : str, optional
        valid choices are const_pri, const_pri_var_sec
    
    chiller_cooling_type : str, optional
        valid choices are AirCooled, WaterCooled

    chiller_condenser_type : str, optional
        valid choices are WithCondenser, WithoutCondenser, nil
    
    chiller_compressor_type : str, optional
        valid choices are Centrifugal, Reciprocating, Rotary Screw, Scroll, nil

    num_chillers : int, optional
       the number of chillers
    
    condenser_water_loop : osmod.PlantLoop, optional
        optional condenser water loop for water-cooled chillers. If this is not passed in, the chillers will be air cooled.
    
    waterside_economizer : str, optional
        - Options are None, 'integrated', 'non-integrated'. If 'integrated' will add a heat exchanger to the supply inlet of the chilled water loop to provide waterside economizing whenever wet bulb temperatures allow 
        - If 'non-integrated'will add a heat exchanger in parallel with the chiller that will operate only when it can meet cooling demand exclusively with the waterside economizing.
    
    Returns
    -------
    chw_loop : osmod.PlantLoop
        the resultant chilled water loop 
    """
    # create chilled water loop
    chilled_water_loop = osmod.PlantLoop(openstudio_model)
    chilled_water_loop.setName(system_name)

    # chilled water loop sizing and controls
    chw_sizing_control(openstudio_model, chilled_water_loop, dsgn_sup_wtr_temp, dsgn_sup_wtr_temp_delt)

    # create chilled water pumps
    if chw_pumping_type == 'const_pri':
        # primary chilled water pump
        pri_chw_pump = osmod.PumpVariableSpeed(openstudio_model)
        pri_chw_pump.setName(f"{chilled_water_loop.name()} Pump")
        pri_chw_pump.setRatedPumpHead(openstudio.convert(60.0, 'ftH_{2}O', 'Pa').get())
        pri_chw_pump.setMotorEfficiency(0.9)
        # flat pump curve makes it behave as a constant speed pump
        pri_chw_pump.setFractionofMotorInefficienciestoFluidStream(0)
        pri_chw_pump.setCoefficient1ofthePartLoadPerformanceCurve(0)
        pri_chw_pump.setCoefficient2ofthePartLoadPerformanceCurve(1)
        pri_chw_pump.setCoefficient3ofthePartLoadPerformanceCurve(0)
        pri_chw_pump.setCoefficient4ofthePartLoadPerformanceCurve(0)
        pri_chw_pump.setPumpControlType('Intermittent')
        pri_chw_pump.addToNode(chilled_water_loop.supplyInletNode)
    elif chw_pumping_type == 'const_pri_var_sec':
        pri_sec_config = 'common_pipe'
        if pri_sec_config == 'common_pipe':
            # primary chilled water pump
            pri_chw_pump = osmod.PumpConstantSpeed(openstudio_model)
            pri_chw_pump.setName(f"{chilled_water_loop.name()} Primary Pump")
            pri_chw_pump.setRatedPumpHead(openstudio.convert(15.0, 'ftH_{2}O', 'Pa').get())
            pri_chw_pump.setMotorEfficiency(0.9)
            pri_chw_pump.setPumpControlType('Intermittent')
            pri_chw_pump.addToNode(chilled_water_loop.supplyInletNode())
            # secondary chilled water pump
            sec_chw_pump = osmod.PumpVariableSpeed(openstudio_model)
            sec_chw_pump.setName(f"{chilled_water_loop.name()} Secondary Pump")
            sec_chw_pump.setRatedPumpHead(openstudio.convert(45.0, 'ftH_{2}O', 'Pa').get())
            sec_chw_pump.setMotorEfficiency(0.9)
            # curve makes it perform like variable speed pump
            sec_chw_pump.setFractionofMotorInefficienciestoFluidStream(0)
            sec_chw_pump.setCoefficient1ofthePartLoadPerformanceCurve(0)
            sec_chw_pump.setCoefficient2ofthePartLoadPerformanceCurve(0.0205)
            sec_chw_pump.setCoefficient3ofthePartLoadPerformanceCurve(0.4101)
            sec_chw_pump.setCoefficient4ofthePartLoadPerformanceCurve(0.5753)
            sec_chw_pump.setPumpControlType('Intermittent')
            sec_chw_pump.addToNode(chilled_water_loop.demandInletNode())
            # Change the chilled water loop to have a two-way common pipes
            chilled_water_loop.setCommonPipeSimulation('CommonPipe')
        elif pri_sec_config == 'heat_exchanger':
            # NOTE: PRECONDITIONING for `const_pri_var_sec` pump type is only applicable for PRM routine and only applies to System Type 7 and System Type 8
            # See: model_add_prm_baseline_system under Model object.
            # In this scenario, we will need to create a primary and secondary configuration:
            # chilled_water_loop is the primary loop
            # Primary: demand: heat exchanger, supply: chillers, name: Chilled Water Loop_Primary, additionalProperty: secondary_loop_name
            # Secondary: demand: Coils, supply: heat exchanger, name: Chilled Water Loop, additionalProperty: is_secondary_loop
            secondary_chilled_water_loop = osmod.PlantLoop(openstudio_model)
            secondary_loop_name = 'Chilled Water Loop' 
            # Reset primary loop name
            chilled_water_loop.setName(f"{secondary_loop_name}_Primary")
            secondary_chilled_water_loop.setName(secondary_loop_name)
            chw_sizing_control(openstudio_model, secondary_chilled_water_loop, dsgn_sup_wtr_temp, dsgn_sup_wtr_temp_delt)
            chilled_water_loop.additionalProperties.setFeature('is_primary_loop', True)
            secondary_chilled_water_loop.additionalProperties.setFeature('is_secondary_loop', True)
            # primary chilled water pump
            # Add Constant pump, in plant loop, the number of chiller adjustment will assign pump to each chiller
            pri_chw_pump = osmod.PumpConstantSpeed(openstudio_model)
            pri_chw_pump.setName(f"{chilled_water_loop.name()} Primary Pump")
            # Will need to adjust the pump power after a sizing run
            pri_chw_pump.setRatedPumpHead(openstudio.convert(15.0, 'ftH_{2}O', 'Pa').get() / num_chillers)
            pri_chw_pump.setMotorEfficiency(0.9)
            pri_chw_pump.setPumpControlType('Intermittent')
            # chiller_inlet_node = chiller.connectedObject(chiller.supplyInletPort).get.to_Node.get
            pri_chw_pump.addToNode(chilled_water_loop.supplyInletNode())

            # secondary chilled water pump
            sec_chw_pump = osmod.PumpVariableSpeed(openstudio_model)
            sec_chw_pump.setName(f"{secondary_chilled_water_loop.name()} Pump")
            sec_chw_pump.setRatedPumpHead(openstudio.convert(45.0, 'ftH_{2}O', 'Pa').get())
            sec_chw_pump.setMotorEfficiency(0.9)
            # curve makes it perform like variable speed pump
            sec_chw_pump.setFractionofMotorInefficienciestoFluidStream(0)
            sec_chw_pump.setCoefficient1ofthePartLoadPerformanceCurve(0)
            sec_chw_pump.setCoefficient2ofthePartLoadPerformanceCurve(0.0205)
            sec_chw_pump.setCoefficient3ofthePartLoadPerformanceCurve(0.4101)
            sec_chw_pump.setCoefficient4ofthePartLoadPerformanceCurve(0.5753)
            sec_chw_pump.setPumpControlType('Intermittent')
            sec_chw_pump.addToNode(secondary_chilled_water_loop.demandInletNode())

            # Add HX to connect secondary and primary loop
            heat_exchanger = osmod.HeatExchangerFluidToFluid(openstudio_model)
            secondary_chilled_water_loop.addSupplyBranchForComponent(heat_exchanger)
            chilled_water_loop.addDemandBranchForComponent(heat_exchanger)

            # Clean up connections
            hx_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
            hx_bypass_pipe.setName(f"{secondary_chilled_water_loop.name()} HX Bypass")
            secondary_chilled_water_loop.addSupplyBranchForComponent(hx_bypass_pipe)
            outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
            outlet_pipe.setName(f"{secondary_chilled_water_loop.name()} Supply Outlet")
            outlet_pipe.addToNode(secondary_chilled_water_loop.supplyOutletNode())
        else:
            print('No primary/secondary configuration specified for the chilled water loop.')
    else:
        print('No pumping type specified for the chilled water loop.')

    # check for existence of condenser_water_loop if WaterCooled
    if chiller_cooling_type == 'WaterCooled':
        if condenser_water_loop == None:
            print('Requested chiller is WaterCooled but no condenser loop specified.')

    # check for non-existence of condenser_water_loop if AirCooled
    if chiller_cooling_type == 'AirCooled':
        if condenser_water_loop != None:
            print('Requested chiller is AirCooled but condenser loop specified.')
        
    if cooling_fuel == 'DistrictCooling':
        # DistrictCooling
        dist_clg = osmod.DistrictCooling(openstudio_model)
        dist_clg.setName('Purchased Cooling')
        dist_clg.autosizeNominalCapacity()
        chilled_water_loop.addSupplyBranchForComponent(dist_clg)
    else:
        # make the correct type of chiller based these properties
        chiller_sizing_factor = round(1.0 / num_chillers, 2)
        for i in range(num_chillers):
            chiller = osmod.ChillerElectricEIR(openstudio_model)
            chiller.setName(f"{chiller_cooling_type} {chiller_condenser_type} {chiller_compressor_type} Chiller {i}")
            chilled_water_loop.addSupplyBranchForComponent(chiller)
            dsgn_sup_wtr_temp_c = dsgn_sup_wtr_temp
            chiller.setReferenceLeavingChilledWaterTemperature(dsgn_sup_wtr_temp_c)
            chiller.setLeavingChilledWaterLowerTemperatureLimit(openstudio.convert(36.0, 'F', 'C').get())
            chiller.setReferenceEnteringCondenserFluidTemperature(openstudio.convert(95.0, 'F', 'C').get())
            chiller.setMinimumPartLoadRatio(0.15)
            chiller.setMaximumPartLoadRatio(1.0)
            chiller.setOptimumPartLoadRatio(1.0)
            chiller.setMinimumUnloadingRatio(0.25)
            chiller.setChillerFlowMode('ConstantFlow')
            chiller.setSizingFactor(chiller_sizing_factor)

            # use default efficiency from 90.1-2019
            # 1.188 kw/ton for a 150 ton AirCooled chiller
            # 0.66 kw/ton for a 150 ton Water Cooled positive displacement chiller
            if chiller_cooling_type == 'AirCooled':
                default_cop = kw_per_ton_to_cop(1.188)
            elif chiller_cooling_type == 'WaterCooled':
                default_cop = kw_per_ton_to_cop(0.66)
            else:
                default_cop = kw_per_ton_to_cop(0.66)

            chiller.setReferenceCOP(default_cop)

            # connect the chiller to the condenser loop if one was supplied
            if condenser_water_loop == None:
                chiller.setCondenserType('AirCooled')
            else:
                condenser_water_loop.addDemandBranchForComponent(chiller)
                chiller.setCondenserType('WaterCooled')

    # enable waterside economizer if requested
    if condenser_water_loop != None:
        if waterside_economizer == 'integrated':
            add_waterside_economizer(openstudio_model, chilled_water_loop, condenser_water_loop, integrated = True)
            
        elif waterside_economizer == 'non-integrated':
            add_waterside_economizer(openstudio_model, chilled_water_loop, condenser_water_loop, integrated = False)

    # chilled water loop pipes
    chiller_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    chiller_bypass_pipe.setName(f"{chilled_water_loop.name()} Chiller Bypass")
    chilled_water_loop.addSupplyBranchForComponent(chiller_bypass_pipe)

    coil_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    coil_bypass_pipe.setName(f"{chilled_water_loop.name()} Coil Bypass")
    chilled_water_loop.addDemandBranchForComponent(coil_bypass_pipe)

    supply_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_outlet_pipe.setName(f"{chilled_water_loop.name()} Supply Outlet")
    supply_outlet_pipe.addToNode(chilled_water_loop.supplyOutletNode)

    demand_inlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_inlet_pipe.setName(f"{chilled_water_loop.name()} Demand Inlet")
    demand_inlet_pipe.addToNode(chilled_water_loop.demandInletNode)

    demand_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_outlet_pipe.setName(f"{chilled_water_loop.name()} Demand Outlet")
    demand_outlet_pipe.addToNode(chilled_water_loop.demandOutletNode)

    return chilled_water_loop

def add_curve(openstudio_model: osmod, curve_name: str) -> osmod.Curve:
    """
    - Adds a curve from the OpenStudio-Standards dataset to the model based on the curve name.
    - It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_curve)
    - curves database https://github.com/NREL/openstudio-standards/blob/master/lib/openstudio-standards/standards/ashrae_90_1_prm/data/ashrae_90_1_prm.curves.json

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    curve_name : str
        the name of the system, defaulted to 'Condenser Water Loop'
    
    Returns
    -------
    res_curve : osmod.Curve
        the resultant curve
    """
    # First check model and return curve if it already exists
    existing_curves = []
    existing_curves += model.getCurveLinears
    existing_curves += model.getCurveCubics
    existing_curves += model.getCurveQuadratics
    existing_curves += model.getCurveBicubics
    existing_curves += model.getCurveBiquadratics
    existing_curves += model.getCurveQuadLinears
    existing_curves.sort.each do |curve|
        if curve.name.get.to_s == curve_name
        OpenStudio.logFree(OpenStudio::Debug, 'openstudio.standards.Model', "Already added curve: #{curve_name}")
        return curve
        end
    end

    # OpenStudio::logFree(OpenStudio::Info, "openstudio.prototype.addCurve", "Adding curve '#{curve_name}' to the model.")

    # Find curve data
    data = model_find_object(standards_data['curves'], 'name' => curve_name)
    if data.nil?
        OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', "Could not find a curve called '#{curve_name}' in the standards.")
        return nil
    end

    # Make the correct type of curve
    case data['form']
        when 'Linear'
        curve = OpenStudio::Model::CurveLinear.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'Cubic'
        curve = OpenStudio::Model::CurveCubic.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setCoefficient4xPOW3(data['coeff_4'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'Quadratic'
        curve = OpenStudio::Model::CurveQuadratic.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'BiCubic'
        curve = OpenStudio::Model::CurveBicubic.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setCoefficient4y(data['coeff_4'])
        curve.setCoefficient5yPOW2(data['coeff_5'])
        curve.setCoefficient6xTIMESY(data['coeff_6'])
        curve.setCoefficient7xPOW3(data['coeff_7'])
        curve.setCoefficient8yPOW3(data['coeff_8'])
        curve.setCoefficient9xPOW2TIMESY(data['coeff_9'])
        curve.setCoefficient10xTIMESYPOW2(data['coeff_10'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumValueofy(data['minimum_independent_variable_2']) if data['minimum_independent_variable_2']
        curve.setMaximumValueofy(data['maximum_independent_variable_2']) if data['maximum_independent_variable_2']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'BiQuadratic'
        curve = OpenStudio::Model::CurveBiquadratic.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setCoefficient4y(data['coeff_4'])
        curve.setCoefficient5yPOW2(data['coeff_5'])
        curve.setCoefficient6xTIMESY(data['coeff_6'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumValueofy(data['minimum_independent_variable_2']) if data['minimum_independent_variable_2']
        curve.setMaximumValueofy(data['maximum_independent_variable_2']) if data['maximum_independent_variable_2']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'BiLinear'
        curve = OpenStudio::Model::CurveBiquadratic.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient4y(data['coeff_3'])
        curve.setMinimumValueofx(data['minimum_independent_variable_1']) if data['minimum_independent_variable_1']
        curve.setMaximumValueofx(data['maximum_independent_variable_1']) if data['maximum_independent_variable_1']
        curve.setMinimumValueofy(data['minimum_independent_variable_2']) if data['minimum_independent_variable_2']
        curve.setMaximumValueofy(data['maximum_independent_variable_2']) if data['maximum_independent_variable_2']
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output']) if data['minimum_dependent_variable_output']
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) if data['maximum_dependent_variable_output']
        return curve
        when 'QuadLinear'
        curve = OpenStudio::Model::CurveQuadLinear.new(model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2w(data['coeff_2'])
        curve.setCoefficient3x(data['coeff_3'])
        curve.setCoefficient4y(data['coeff_4'])
        curve.setCoefficient5z(data['coeff_5'])
        curve.setMinimumValueofw(data['minimum_independent_variable_w'])
        curve.setMaximumValueofw(data['maximum_independent_variable_w'])
        curve.setMinimumValueofx(data['minimum_independent_variable_x'])
        curve.setMaximumValueofx(data['maximum_independent_variable_x'])
        curve.setMinimumValueofy(data['minimum_independent_variable_y'])
        curve.setMaximumValueofy(data['maximum_independent_variable_y'])
        curve.setMinimumValueofz(data['minimum_independent_variable_z'])
        curve.setMaximumValueofz(data['maximum_independent_variable_z'])
        curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        curve.setMaximumCurveOutput(data['maximum_dependent_variable_output'])
        return curve
        when 'MultiVariableLookupTable'
        num_ind_var = data['number_independent_variables'].to_i
        table = OpenStudio::Model::TableMultiVariableLookup.new(model, num_ind_var)
        table.setName(data['name'])
        table.setInterpolationMethod(data['interpolation_method'])
        table.setNumberofInterpolationPoints(data['number_of_interpolation_points'])
        table.setCurveType(data['curve_type'])
        table.setTableDataFormat('SingleLineIndependentVariableWithMatrix')
        table.setNormalizationReference(data['normalization_reference'].to_f)
        table.setOutputUnitType(data['output_unit_type'])
        table.setMinimumValueofX1(data['minimum_independent_variable_1'].to_f)
        table.setMaximumValueofX1(data['maximum_independent_variable_1'].to_f)
        table.setInputUnitTypeforX1(data['input_unit_type_x1'])
        if num_ind_var == 2
            table.setMinimumValueofX2(data['minimum_independent_variable_2'].to_f)
            table.setMaximumValueofX2(data['maximum_independent_variable_2'].to_f)
            table.setInputUnitTypeforX2(data['input_unit_type_x2'])
        end
        data_points = data.each.select { |key, value| key.include? 'data_point' }
        data_points.each do |key, value|
            if num_ind_var == 1
            table.addPoint(value.split(',')[0].to_f, value.split(',')[1].to_f)
            elsif num_ind_var == 2
            table.addPoint(value.split(',')[0].to_f, value.split(',')[1].to_f, value.split(',')[2].to_f)
            end
        end
        return table
        else
        OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model', "#{curve_name}' has an invalid form: #{data['form']}', cannot create this curve.")
        return nil
    end
    end
def add_cw_loop(openstudio_model: osmod, system_name: str = 'Condenser Water Loop', cooling_tower_type: str = 'Open Cooling Tower', cooling_tower_fan_type: str = 'Propeller or Axial', 
                cooling_tower_capacity_control: str = 'TwoSpeed Fan', number_of_cells_per_tower: int = 1, number_cooling_towers: int = 1, use_90_1_design_sizing: bool = True, 
                sup_wtr_temp: float = 21.1, dsgn_sup_wtr_temp: float = 29.4, dsgn_sup_wtr_temp_delt: float = 5.6, wet_bulb_approach: float = 3.9, pump_spd_ctrl: str = 'Constant', 
                pump_tot_hd: float = 49.7) -> osmod.PlantLoop:
    """
    Creates a condenser water loop and adds it to the model.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_cw_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    system_name : str, optional
        the name of the system, defaulted to 'Condenser Water Loop'
    
    cooling_tower_type : str, optional
        valid choices are Open Cooling Tower (default), Closed Cooling Tower

    cooling_tower_fan_type : str, optional
        valid choices are Centrifugal, “Propeller or Axial” (default)

    cooling_tower_capacity_control : str, optional
        valid choices are Fluid Bypass, Fan Cycling, TwoSpeed Fan (default), Variable Speed Fan

    number_of_cells_per_tower : int, optional
        the number of discrete cells per tower
    
    number_cooling_towers : int, optional
        number of cooling towers to be added (in parallel)

    use_90_1_design_sizing : bool, optional
        - will determine the design sizing temperatures based on the 90.1 Appendix G approach. 
        - Overrides sup_wtr_temp, dsgn_sup_wtr_temp, dsgn_sup_wtr_temp_delt, and wet_bulb_approach if true.
    
    sup_wtr_temp : float, optional
        supply water temperature in degC, default 21.1C

    dsgn_sup_wtr_temp : float, optional
       design supply water temperature in degrees C, default 29.4C
    
    dsgn_sup_wtr_temp_delt : float, optional
        design water range temperature in degrees C, default 5.6K
    
    wet_bulb_approach : float, optional
        design wet bulb approach temperature, default 3.9K

    pump_spd_ctrl : str, optional
        pump speed control type, Constant(default), Variable, HeaderedVariable, HeaderedConstant

    pump_tot_hd : float, optional
        pump head in ft H2O. Default = 49.7

    Returns
    -------
    cw_loop : osmod.PlantLoop
        the resultant condenser water loop
    """
    # create condenser water loop
    condenser_water_loop = osmod.PlantLoop(openstudio_model)
    condenser_water_loop.setName(system_name)
    
    # condenser water loop sizing and controls
    condenser_water_loop.setMinimumLoopTemperature(5.0)
    condenser_water_loop.setMaximumLoopTemperature(80.0)
    sizing_plant = condenser_water_loop.sizingPlant()
    sizing_plant.setLoopType('Condenser')
    sizing_plant.setDesignLoopExitTemperature(dsgn_sup_wtr_temp)
    sizing_plant.setLoopDesignTemperatureDifference(dsgn_sup_wtr_temp_delt)
    sizing_plant.setSizingOption('Coincident')
    sizing_plant.setZoneTimestepsinAveragingWindow(6)
    sizing_plant.setCoincidentSizingFactorMode('GlobalCoolingSizingFactor')

    # follow outdoor air wetbulb with given approach temperature
    cw_stpt_manager = osmod.SetpointManagerFollowOutdoorAirTemperature(openstudio_model)
    cw_stpt_manager.setName(f"{condenser_water_loop.name()} Setpoint Manager Follow OATwb with {wet_bulb_approach}K Approach")
    cw_stpt_manager.setReferenceTemperatureType('OutdoorAirWetBulb')
    cw_stpt_manager.setMaximumSetpointTemperature(dsgn_sup_wtr_temp)
    cw_stpt_manager.setMinimumSetpointTemperature(sup_wtr_temp)
    cw_stpt_manager.setOffsetTemperatureDifference(wet_bulb_approach)
    cw_stpt_manager.addToNode(condenser_water_loop.supplyOutletNode())

    # create condenser water pump
    if pump_spd_ctrl == 'Constant':
        cw_pump = osmod.PumpConstantSpeed(openstudio_model)
    elif pump_spd_ctrl == 'Variable':
        cw_pump = osmod.PumpVariableSpeed.new(openstudio_model)
    elif pump_spd_ctrl == 'HeaderedVariable':
        cw_pump = osmod.HeaderedPumpsVariableSpeed.new(openstudio_model)
        cw_pump.setNumberofPumpsinBank(2)
    elif pump_spd_ctrl == 'HeaderedConstant':
        cw_pump = osmod.HeaderedPumpsConstantSpeed.new(openstudio_model)
        cw_pump.setNumberofPumpsinBank(2)
    else:
        cw_pump = osmod.PumpConstantSpeed.new(openstudio_model)
    
    cw_pump.setName(f"{condenser_water_loop.name()} {pump_spd_ctrl} Pump")
    cw_pump.setPumpControlType('Intermittent')

    pump_tot_hd_pa =  openstudio.convert(pump_tot_hd, 'ftH_{2}O', 'Pa').get()

    cw_pump.setRatedPumpHead(pump_tot_hd_pa)
    cw_pump.addToNode(condenser_water_loop.supplyInletNode())

    # Cooling towers
    # Per PNNL PRM Reference Manual
    # number_cooling_towers.times do |_i|
    for i in range(number_cooling_towers):
        # Tower object depends on the control type
        cooling_tower = None

        if cooling_tower_capacity_control == 'Fluid Bypass' or cooling_tower_capacity_control == 'Fan Cycling':
            cooling_tower = osmod.CoolingTowerSingleSpeed(openstudio_model)
            if cooling_tower_capacity_control == 'Fluid Bypass':
                cooling_tower.setCellControl('FluidBypass')
            else:
                cooling_tower.setCellControl('FanCycling')
        elif cooling_tower_capacity_control == 'TwoSpeed Fan':
            cooling_tower = osmod.CoolingTowerTwoSpeed(openstudio_model)
            # @todo expose newer cooling tower sizing fields in API
            # cooling_tower.setLowFanSpeedAirFlowRateSizingFactor(0.5)
            # cooling_tower.setLowFanSpeedFanPowerSizingFactor(0.3)
            # cooling_tower.setLowFanSpeedUFactorTimesAreaSizingFactor
            # cooling_tower.setLowSpeedNominalCapacitySizingFactor
        elif cooling_tower_capacity_control == 'Variable Speed Fan':
            cooling_tower = osmod.CoolingTowerVariableSpeed(openstudio_model)
            cooling_tower.setDesignRangeTemperature(dsgn_sup_wtr_temp_delt)
            cooling_tower.setDesignApproachTemperature(wet_bulb_approach)
            cooling_tower.setFractionofTowerCapacityinFreeConvectionRegime(0.125)

            twr_fan_curve = model_add_curve(model, 'VSD-TWR-FAN-FPLR')
        #     cooling_tower.setFanPowerRatioFunctionofAirFlowRateRatioCurve(twr_fan_curve)
        else:
            print('openstudio.Prototype.hvac_systems', f"#{cooling_tower_capacity_control} is not a valid choice of cooling tower capacity control.  Valid choices are Fluid Bypass, Fan Cycling, TwoSpeed Fan, Variable Speed Fan.")
        
        # Set the properties that apply to all tower types and attach to the condenser loop.
        unless cooling_tower.nil?
        cooling_tower.setName("#{cooling_tower_fan_type} #{cooling_tower_capacity_control} #{cooling_tower_type}")
        cooling_tower.setSizingFactor(1 / number_cooling_towers)
        cooling_tower.setNumberofCells(number_of_cells_per_tower)
        condenser_water_loop.addSupplyBranchForComponent(cooling_tower)
        end
    end

    # apply 90.1 sizing temperatures
    if use_90_1_design_sizing
        # use the formulation in 90.1-2010 G3.1.3.11 to set the approach temperature
        OpenStudio.logFree(OpenStudio::Info, 'openstudio.Prototype.hvac_systems', "Using the 90.1-2010 G3.1.3.11 approach temperature sizing methodology for condenser loop #{condenser_water_loop.name}.")

        # first, look in the model design day objects for sizing information
        summer_oat_wbs_f = []
        condenser_water_loop.model.getDesignDays.sort.each do |dd|
        next unless dd.dayType == 'SummerDesignDay'
        next unless dd.name.get.to_s.include?('WB=>MDB')

        if dd.humidityIndicatingType == 'Wetbulb'
            summer_oat_wb_c = dd.humidityIndicatingConditionsAtMaximumDryBulb
            summer_oat_wbs_f << OpenStudio.convert(summer_oat_wb_c, 'C', 'F').get
        else
            OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', "For #{dd.name}, humidity is specified as #{dd.humidityIndicatingType}; cannot determine Twb.")
        end
        end

        # if no design day objects are present in the model, attempt to load the .ddy file directly
        if summer_oat_wbs_f.size.zero?
        OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', 'No valid WB=>MDB Summer Design Days were found in the model.  Attempting to load wet bulb sizing from the .ddy file directly.')
        if model.weatherFile.is_initialized && model.weatherFile.get.path.is_initialized
            weather_file = model.weatherFile.get.path.get.to_s
            # Run differently depending on whether running from embedded filesystem in OpenStudio CLI or not
            if weather_file[0] == ':' # Running from OpenStudio CLI
            # Attempt to load in the ddy file based on convention that it is in the same directory and has the same basename as the epw file.
            ddy_file = weather_file.gsub('.epw', '.ddy')
            if EmbeddedScripting.hasFile(ddy_file)
                ddy_string = EmbeddedScripting.getFileAsString(ddy_file)
                temp_ddy_path = "#{Dir.pwd}/in.ddy"
                File.open(temp_ddy_path, 'wb') do |f|
                f << ddy_string
                f.flush
                end
                ddy_model = OpenStudio::EnergyPlus.loadAndTranslateIdf(temp_ddy_path).get
                File.delete(temp_ddy_path) if File.exist?(temp_ddy_path)
            else
                OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', "Could not locate a .ddy file for weather file path #{weather_file}")
            end
            else
            # Attempt to load in the ddy file based on convention that it is in the same directory and has the same basename as the epw file.
            ddy_file = "#{File.join(File.dirname(weather_file), File.basename(weather_file, '.*'))}.ddy"
            if File.exist? ddy_file
                ddy_model = OpenStudio::EnergyPlus.loadAndTranslateIdf(ddy_file).get
            else
                OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', "Could not locate a .ddy file for weather file path #{weather_file}")
            end
            end

            unless ddy_model.nil?
            ddy_model.getDesignDays.sort.each do |dd|
                # Save the model wetbulb design conditions Condns WB=>MDB
                if dd.name.get.include? '4% Condns WB=>MDB'
                summer_oat_wb_c = dd.humidityIndicatingConditionsAtMaximumDryBulb
                summer_oat_wbs_f << OpenStudio.convert(summer_oat_wb_c, 'C', 'F').get
                end
            end
            end
        else
            OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', 'The model does not have a weather file object or path specified in the object. Cannot get .ddy file directory.')
        end
        end

        # if values are still absent, use the CTI rating condition 78F
        design_oat_wb_f = nil
        if summer_oat_wbs_f.size.zero?
        design_oat_wb_f = 78.0
        OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Prototype.hvac_systems', "For condenser loop #{condenser_water_loop.name}, no design day OATwb conditions found.  CTI rating condition of 78F OATwb will be used for sizing cooling towers.")
        else
        # Take worst case condition
        design_oat_wb_f = summer_oat_wbs_f.max
        OpenStudio.logFree(OpenStudio::Info, 'openstudio.Prototype.hvac_systems', "The maximum design wet bulb temperature from the Summer Design Day WB=>MDB is #{design_oat_wb_f} F")
        end
        design_oat_wb_c = OpenStudio.convert(design_oat_wb_f, 'F', 'C').get

        # call method to apply design sizing to the condenser water loop
        prototype_apply_condenser_water_temperatures(condenser_water_loop, design_wet_bulb_c: design_oat_wb_c)
    end

    # Condenser water loop pipes
    cooling_tower_bypass_pipe = OpenStudio::Model::PipeAdiabatic.new(model)
    cooling_tower_bypass_pipe.setName("#{condenser_water_loop.name} Cooling Tower Bypass")
    condenser_water_loop.addSupplyBranchForComponent(cooling_tower_bypass_pipe)

    chiller_bypass_pipe = OpenStudio::Model::PipeAdiabatic.new(model)
    chiller_bypass_pipe.setName("#{condenser_water_loop.name} Chiller Bypass")
    condenser_water_loop.addDemandBranchForComponent(chiller_bypass_pipe)

    supply_outlet_pipe = OpenStudio::Model::PipeAdiabatic.new(model)
    supply_outlet_pipe.setName("#{condenser_water_loop.name} Supply Outlet")
    supply_outlet_pipe.addToNode(condenser_water_loop.supplyOutletNode)

    demand_inlet_pipe = OpenStudio::Model::PipeAdiabatic.new(model)
    demand_inlet_pipe.setName("#{condenser_water_loop.name} Demand Inlet")
    demand_inlet_pipe.addToNode(condenser_water_loop.demandInletNode)

    demand_outlet_pipe = OpenStudio::Model::PipeAdiabatic.new(model)
    demand_outlet_pipe.setName("#{condenser_water_loop.name} Demand Outlet")
    demand_outlet_pipe.addToNode(condenser_water_loop.demandOutletNode)

    return condenser_water_loop


def add_low_temp_radiant():
    """
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_low_temp_radiant)
    """

    pass

def add_doas():
    """
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_doas)
    """
    pass

def add_rad_doas():
    add_hw_loop()
    add_cw_loop()
    add_chw_loop()

    add_doas()

    pass

def add_baseboard():
    """
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_baseboard)
    """
    pass

if __name__ == '__main__':
    std_dict = std_dgn_sizing_temps()
    # print(std_dict)
    pressure_rise = openstudio.convert(1.33, "inH_{2}O", 'Pa').get()
    # print(pressure_rise)
    m = osmod.Model()
    sch = m.alwaysOnDiscreteSchedule()
    # print(sch)
    # sch = m.getScheduleRulesetByName('test')
    # print(m.version())