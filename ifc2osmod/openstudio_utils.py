import os
import math
import json
import copy
from pathlib import Path
import datetime
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from dateutil.parser import parse
from distutils.dir_util import copy_tree

import geomie3d
import numpy as np
import openstudio
from openstudio import model as osmod
from ladybug.epw import EPW

import ifcopenshell_utils
import settings

PSET_DATA_DIR = settings.PSET_DATA_DIR
ASHRAE_DATA_DIR = settings.ASHRAE_DATA_DIR

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

def save_osw_project(proj_dir: str, openstudio_model: osmod, measure_list: list[dict], proj_name) -> str:
    # create all the necessary directory
    proj_path = Path(proj_dir)
    wrkflow_dir = Path(proj_dir).joinpath(proj_name + '_wrkflw')
    dir_ls = ['files', 'measures', 'run']
    for dir in dir_ls:
        dir_in_wrkflw = wrkflow_dir.joinpath(dir)
        dir_in_wrkflw.mkdir(parents=True, exist_ok=True)
    
    # create the osm file
    osm_filename = proj_name + '.osm'
    osm_path = proj_path.joinpath(osm_filename)
    openstudio_model.save(str(osm_path), True)

    # retrieve the osw file
    oswrkflw = openstudio_model.workflowJSON()
    oswrkflw.setSeedFile('../' + osm_filename)

    # create the result measure into the measures folder
    # measure type 0=ModelMeasure, 1=EnergyPlusMeasure, 2=UtilityMeasure, 3=ReportingMeasure
    msteps = {0: [], 1: [], 2: [], 3: []}
    for measure_folder in measure_list:
        measure_dir_orig = measure_folder['dir']

        foldername = Path(measure_dir_orig).stem
        measure_dir_dest = str(wrkflow_dir.joinpath('measures', foldername))
        copy_tree(measure_dir_orig, measure_dir_dest)
        # set measurestep
        mstep = openstudio.MeasureStep(measure_dir_dest)
        mstep.setName(foldername)
        # mstep.setDescription(measure_folder['description'])
        # mstep.setModelerDescription(measure_folder['modeler_description'])
        if 'arguments' in measure_folder.keys():
            arguments = measure_folder['arguments']
            for argument in arguments:
                mstep.setArgument(argument['argument'], argument['value'])

        # get the measure type of the measure by reading its xml 
        measure_xmlpath = str(Path(measure_dir_orig).joinpath('measure.xml'))
        tree = ET.parse(measure_xmlpath)
        root = tree.getroot()
        measure_type_int = None
        for child in root:
            child_name = child.tag
            if child_name == 'attributes':
                for child2 in child:
                    name = child2.find('name').text
                    if name == 'Measure Type':
                        measure_type_str = child2.find('value').text
                        
                        if measure_type_str == 'ModelMeasure':
                            measure_type_int = 0
                        
                        elif measure_type_str == 'EnergyPlusMeasure':
                            measure_type_int = 1

                        elif measure_type_str == 'UtilityMeasure':
                            measure_type_int = 2
                        
                        elif measure_type_str == 'ReportingMeasure':
                            measure_type_int = 3

        msteps[measure_type_int].append(mstep)
    
    for mt_val in msteps.keys():
        measure_type = openstudio.MeasureType(mt_val)
        measure_steps = msteps[mt_val]
        if len(measure_steps) != 0:
            oswrkflw.setMeasureSteps(measure_type, measure_steps)
    
    wrkflw_path = str(wrkflow_dir.joinpath(proj_name + '.osw'))
    oswrkflw.saveAs(wrkflw_path)
    with open(wrkflw_path) as wrkflw_f:
        data = json.load(wrkflw_f)
        steps = data['steps']
        for step in steps:
            dirname = step['measure_dir_name']
            foldername = Path(dirname).stem
            step['measure_dir_name'] = foldername

    with open(wrkflw_path, "w") as out_file:
        json.dump(data, out_file)

    return wrkflw_path

def save2idf(idf_path: str, openstudio_model: osmod):
    ft = openstudio.energyplus.ForwardTranslator()
    idf = ft.translateModel(openstudio_model)
    idf.save(idf_path, True)

def read_idf_file(idf_path: str) -> osmod:
    rt = openstudio.energyplus.ReverseTranslator()
    osmodel = rt.loadModel(idf_path)
    if osmodel.empty() == False:
        osmodel = osmodel.get()
    else:
        raise RuntimeError(f"Failed to load IDF file: {idf_path}")

    return osmodel

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

def apply_base_fan_variables(fan: osmod.StraightComponent, fan_name: str = None, fan_efficiency: float = None, 
                             pressure_rise: float = None, end_use_subcategory: str = None):
    """
    - apply base fan variables
    - https://www.rubydoc.info/gems/openstudio-standards/PrototypeFan.apply_base_fan_variables

    Parameters
    ----------
    fan : osmod.StraightComponent
        the fan object.
    
    fan_name : str, optional
        name of this fan.
    
    fan_efficiency : float, optional
        efficiency of the fan.
    
    pressure_rise : float, optional
         fan pressure rise in Pa.

    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.StraightComponent
        modified fan object.
    """
    if fan_name != None: fan.setName(fan_name)
    if fan_efficiency != None: fan.setFanEfficiency(fan_efficiency)
    if pressure_rise != None: fan.setPressureRise(pressure_rise)
    if end_use_subcategory != None: fan.setEndUseSubcategory(end_use_subcategory)
    return fan

def create_fan_constant_volume_from_json(openstudio_model: osmod, fan_json: dict, fan_name: str = None) -> osmod.FanConstantVolume:
    """
    - create a fan with properties for a fan name in the standards data. 
    - (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_constant_volume_from_json)

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_json : dict
        dictionary of the fan.
    
    fan_name : str, optional
        name of this fan.
    
    Returns
    -------
    fan : osmod.FanConstantVolume
        fan object.
    """
    # check values to use
    fan_efficiency = fan_json['fan_efficiency']
    pressure_rise = fan_json['pressure_rise']
    motor_efficiency = fan_json['motor_efficiency']
    motor_in_airstream_fraction = fan_json['motor_in_airstream_fraction']
    end_use_subcategory = fan_json['end_use_subcategory']

    # convert values
    pressure_rise = openstudio.convert(pressure_rise, 'inH_{2}O', 'Pa').get()

    # create fan
    fan = create_fan_constant_volume(openstudio_model,fan_name = fan_name, fan_efficiency = fan_efficiency, pressure_rise = pressure_rise,
                                     motor_efficiency = motor_efficiency, motor_in_airstream_fraction = motor_in_airstream_fraction, end_use_subcategory = end_use_subcategory)
    return fan

def create_fan_constant_volume(openstudio_model: osmod, fan_name: str = None, fan_efficiency: float = None, pressure_rise: float = None,
                               motor_efficiency: float = None, motor_in_airstream_fraction: float = None, 
                               end_use_subcategory: str = None) -> osmod.FanConstantVolume:
    """
    - create a fan with properties for a fan name in the standards data. 
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_constant_volume

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_name : str, optional
        name of this fan.
    
    fan_efficiency : float, optional
        efficiency of the fan.
    
    pressure_rise : float, optional
         fan pressure rise in Pa.

    motor_efficiency : float, optional
        fan motor efficiency.

    motor_in_airstream_fraction : float, optional
        fraction of motor heat in airstream.

    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.FanConstantVolume
        fan object.
    """
    fan = osmod.FanConstantVolume(openstudio_model)
    apply_base_fan_variables(fan, fan_name = fan_name, fan_efficiency = fan_efficiency,
                             pressure_rise = pressure_rise, end_use_subcategory = end_use_subcategory)
    
    if motor_efficiency != None: fan.setMotorEfficiency(motor_efficiency)
    if motor_in_airstream_fraction != None: fan.setMotorInAirstreamFraction(motor_in_airstream_fraction)
    return fan

def create_fan_on_off(openstudio_model: osmod, fan_name: str = None, fan_efficiency: float = None, pressure_rise: float = None,
                      motor_efficiency: float = None, motor_in_airstream_fraction: float = None, end_use_subcategory: float = None) -> osmod.FanOnOff:
    """
    - create a fan with properties for a fan name in the standards data. 
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_on_off

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_name : str, optional
        name of this fan.
    
    fan_efficiency : float, optional
        efficiency of the fan.
    
    pressure_rise : float, optional
         fan pressure rise in Pa.

    motor_efficiency : float, optional
        fan motor efficiency.

    motor_in_airstream_fraction : float, optional
        fraction of motor heat in airstream.

    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.FanOnOff
        fan object.
    """
    fan = osmod.FanOnOff(openstudio_model)
    apply_base_fan_variables(fan, fan_name = fan_name, fan_efficiency = fan_efficiency,
                             pressure_rise = pressure_rise, end_use_subcategory = end_use_subcategory)
    if motor_efficiency != None: fan.setMotorEfficiency(motor_efficiency)
    if motor_in_airstream_fraction != None: fan.setMotorInAirstreamFraction(motor_in_airstream_fraction)
    return fan

def create_fan_on_off_from_json(openstudio_model: osmod, fan_json: dict, fan_name: str = None, end_use_subcategory: str = None) -> osmod.FanOnOff:
    """
    - create a fan with properties for a fan name in the standards data. 
    - (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_on_off_from_json)

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_json : dict
        dictionary of the fan.
    
    fan_name : str, optional
        name of this fan.
    
    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.FanOnOff
        fan object.
    """
    # check values to use
    fan_efficiency = fan_json['fan_efficiency']
    pressure_rise = fan_json['pressure_rise']
    motor_efficiency = fan_json['motor_efficiency']
    motor_in_airstream_fraction = fan_json['motor_in_airstream_fraction']

    # convert values
    pressure_rise = openstudio.convert(pressure_rise, 'inH_{2}O', 'Pa').get()

    # create fan
    fan = create_fan_on_off(openstudio_model, fan_name = fan_name, fan_efficiency = fan_efficiency,
                            pressure_rise = pressure_rise, motor_efficiency = motor_efficiency,
                            motor_in_airstream_fraction = motor_in_airstream_fraction,
                            end_use_subcategory = end_use_subcategory)
    return fan

def lookup_fan_curve_coefficients_from_json(fan_curve: str) -> list[float]:
    """
    Lookup fan curve coefficients.

    Parameters
    ----------
    fan_curve : str
        name of the fan curve.
    
    Returns
    -------
    coeffs : list[float]
        coefficients of the curve.
    """
    crv_json = ASHRAE_DATA_DIR.joinpath('ashrae_90_1_prm.curves.json')
    fan_curve = find_obj_frm_json_based_on_type_name(crv_json, 'curves', fan_curve)

    return [fan_curve['coeff_1'], fan_curve['coeff_2'], fan_curve['coeff_3'], fan_curve['coeff_4'], fan_curve['coeff_5']]

def create_fan_variable_volume(openstudio_model: osmod, fan_name: str = None, fan_efficiency: float = None, pressure_rise: float = None,
                               motor_efficiency: float = None, motor_in_airstream_fraction: float = None, 
                               fan_power_minimum_flow_rate_input_method: str = None, fan_power_minimum_flow_rate_fraction: float = None,
                               fan_power_coefficient_1: float = None, fan_power_coefficient_2: float = None, fan_power_coefficient_3: float = None,
                               fan_power_coefficient_4: float = None, fan_power_coefficient_5: float = None, 
                               end_use_subcategory: str = None) -> osmod.FanVariableVolume:
    """
    - create a fan with properties for a fan name in the standards data. 
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_variable_volume

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_name : str, optional
        name of this fan.
    
    fan_efficiency : float, optional
        efficiency of the fan.
    
    pressure_rise : float, optional
         fan pressure rise in Pa.

    motor_efficiency : float, optional
        fan motor efficiency.

    motor_in_airstream_fraction : float, optional
        fraction of motor heat in airstream.

    fan_power_minimum_flow_rate_input_method : str, optional
        options are Fraction, FixedFlowRate.

    fan_power_minimum_flow_rate_fraction : float, optional
        minimum flow rate fraction.

    fan_power_coefficient_1 : float, optional
        fan power coefficient 1.
    
    fan_power_coefficient_2 : float, optional
        fan power coefficient 2.
    
    fan_power_coefficient_3 : float, optional
        fan power coefficient 3.
    
    fan_power_coefficient_4 : float, optional
        fan power coefficient 4.
    
    fan_power_coefficient_5 : float, optional
        fan power coefficient 5.
    
    end_use_subcategory : str, optional
        end use subcategory name.
    Returns
    -------
    fan : osmod.FanVariableVolume
        fan object.
    """
    fan = osmod.FanVariableVolume(openstudio_model)
    apply_base_fan_variables(fan, fan_name = fan_name, fan_efficiency = fan_efficiency, pressure_rise = pressure_rise, 
                             end_use_subcategory = end_use_subcategory)
    
    if motor_efficiency != None: fan.setMotorEfficiency(motor_efficiency)
    if motor_in_airstream_fraction != None: fan.setMotorInAirstreamFraction(motor_in_airstream_fraction)
    if fan_power_minimum_flow_rate_input_method != None: fan.setFanPowerMinimumFlowRateInputMethod(fan_power_minimum_flow_rate_input_method)
    if fan_power_minimum_flow_rate_fraction != None: fan.setFanPowerMinimumFlowFraction(fan_power_minimum_flow_rate_fraction)
    if fan_power_coefficient_1 != None: fan.setFanPowerCoefficient1(fan_power_coefficient_1)
    if fan_power_coefficient_2 != None: fan.setFanPowerCoefficient2(fan_power_coefficient_2)
    if fan_power_coefficient_3 != None: fan.setFanPowerCoefficient3(fan_power_coefficient_3)
    if fan_power_coefficient_4 != None: fan.setFanPowerCoefficient4(fan_power_coefficient_4)
    if fan_power_coefficient_5 != None: fan.setFanPowerCoefficient5(fan_power_coefficient_5)
    return fan

def create_fan_variable_volume_from_json(openstudio_model: osmod, fan_json: dict, fan_name: str = None, 
                                         end_use_subcategory: str = None) -> osmod.FanVariableVolume:
    """
    - create a fan with properties for a fan name in the standards data. 
    - (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_constant_volume_from_json)

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_json : dict
        dictionary of the fan.
    
    fan_name : str, optional
        name of this fan.

    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.FanVariableVolume
        fan object.
    """
    # check values to use
    fan_efficiency = fan_json['fan_efficiency']
    pressure_rise = fan_json['pressure_rise']
    motor_efficiency = fan_json['motor_efficiency']
    motor_in_airstream_fraction = fan_json['motor_in_airstream_fraction']
    fan_power_minimum_flow_rate_input_method = fan_json['fan_power_minimum_flow_rate_input_method']
    fan_power_minimum_flow_rate_fraction = fan_json['fan_power_minimum_flow_rate_fraction']
    fan_power_coefficient_1 = fan_json['fan_power_coefficient_1']
    fan_power_coefficient_2 = fan_json['fan_power_coefficient_2']
    fan_power_coefficient_3 = fan_json['fan_power_coefficient_3']
    fan_power_coefficient_4 = fan_json['fan_power_coefficient_4']
    fan_power_coefficient_5 = fan_json['fan_power_coefficient_5']

    # convert values
    if pressure_rise != None: 
        pressure_rise_pa = openstudio.convert(pressure_rise, 'inH_{2}O', 'Pa').get()
    else:
        pressure_rise_pa = pressure_rise

    # create fan
    fan = create_fan_variable_volume(openstudio_model, fan_name = fan_name, fan_efficiency = fan_efficiency,
                                    pressure_rise = pressure_rise_pa, motor_efficiency = motor_efficiency, 
                                    motor_in_airstream_fraction = motor_in_airstream_fraction,
                                    fan_power_minimum_flow_rate_input_method = fan_power_minimum_flow_rate_input_method,
                                    fan_power_minimum_flow_rate_fraction = fan_power_minimum_flow_rate_fraction,
                                    end_use_subcategory = end_use_subcategory,
                                    fan_power_coefficient_1 = fan_power_coefficient_1,
                                    fan_power_coefficient_2 = fan_power_coefficient_2,
                                    fan_power_coefficient_3 = fan_power_coefficient_3,
                                    fan_power_coefficient_4 = fan_power_coefficient_4,
                                    fan_power_coefficient_5 = fan_power_coefficient_5)
    return fan

def create_fan_zone_exhaust(openstudio_model: osmod, fan_name: str = None, fan_efficiency: str = None, pressure_rise: str = None, 
                            system_availability_manager_coupling_mode: str = None, end_use_subcategory: str = None):
    """
    - create a fan with properties for a fan name in the standards data. 
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_zone_exhaust

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_name : str, optional
        name of this fan.
    
    fan_efficiency : float, optional
        efficiency of the fan.
    
    pressure_rise : float, optional
         fan pressure rise in Pa.

    system_availability_manager_coupling_mode : str, optional
        coupling mode, options are Coupled, Decoupled.

    end_use_subcategory : str, optional
        end use subcategory name.

    Returns
    -------
    fan : osmod.FanVariableVolume
        fan object.
    """

    fan = osmod.FanZoneExhaust(openstudio_model)
    apply_base_fan_variables(fan, fan_name = fan_name, fan_efficiency = fan_efficiency, pressure_rise = pressure_rise, 
                             end_use_subcategory = end_use_subcategory)
    if system_availability_manager_coupling_mode != None: fan.setSystemAvailabilityManagerCouplingMode(system_availability_manager_coupling_mode)
    return fan

def create_fan_zone_exhaust_from_json(openstudio_model: osmod, fan_json: dict, fan_name: str = None, 
                                      end_use_subcategory: str = None) -> osmod.FanZoneExhaust:
    """
    - create a fan with properties for a fan name in the standards data. 
    - (https://www.rubydoc.info/gems/openstudio-standards/Standard:create_fan_zone_exhaust_from_json)

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    fan_json : dict
        dictionary of the fan.
    
    fan_name : str, optional
        name of this fan.

    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.FanZoneExhaust
        fan object.
    """
    # check values to use
    fan_efficiency = fan_json['fan_efficiency']
    pressure_rise = fan_json['pressure_rise']
    system_availability_manager_coupling_mode = fan_json['system_availability_manager_coupling_mode']

    # convert values
    if pressure_rise != None:
        pressure_rise = openstudio.convert(pressure_rise, 'inH_{2}O', 'Pa').get()

    # create fan
    fan = create_fan_zone_exhaust(openstudio_model, fan_name = fan_name, fan_efficiency = fan_efficiency, pressure_rise = pressure_rise, 
                                  system_availability_manager_coupling_mode = system_availability_manager_coupling_mode, 
                                  end_use_subcategory = end_use_subcategory)
    return fan

def create_fan_by_name(openstudio_model: osmod, standards_name: str, fan_name: str = None, end_use_subcategory: str = None) -> osmod.StraightComponent:
    """
    create a fan with properties for a fan name in the standards data. (https://www.rubydoc.info/gems/openstudio-standards/PrototypeFan:create_fan_by_name)

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    standards_name : str
        name of the standard fan.
    
    fan_name : str, optional
        name of this fan.
    
    end_use_subcategory : str, optional
        end use subcategory name.
    
    Returns
    -------
    fan : osmod.StraightComponent
        fan object.
    """
    fan_json_path = ASHRAE_DATA_DIR.joinpath('ashrae_90_1.fans.json')
    fan_json = find_obj_frm_json_based_on_type_name(fan_json_path, 'fans', standards_name)

    if fan_json['type'] == 'ConstantVolume':
        fan = create_fan_constant_volume_from_json(openstudio_model, fan_json, fan_name = fan_name)

    elif fan_json['type'] == 'OnOff':
        fan = create_fan_on_off_from_json(openstudio_model, fan_json, fan_name = fan_name, end_use_subcategory = end_use_subcategory)

    elif fan_json['type'] == 'VariableVolume':
        fan = create_fan_variable_volume_from_json(openstudio_model, fan_json, fan_name = fan_name, end_use_subcategory = end_use_subcategory)
    
    elif fan_json['type'] == 'ZoneExhaust':
        fan = create_fan_zone_exhaust_from_json(openstudio_model, fan_json, fan_name = fan_name, end_use_subcategory = end_use_subcategory)

    return fan

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

def create_coil_heating_dx_single_speed(openstudio_model: osmod, air_loop_node: osmod.Node = None, name: str = '1spd DX Htg Coil', 
                                        schedule: osmod.Schedule = None, type: str = None, cop: float = 3.3, 
                                        defrost_strategy: str = 'ReverseCycle') -> osmod.CoilHeatingDXSingleSpeed:
    """
    create CoilHeatingDXSingleSpeed object Enters in default curves for coil by type of coil

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
        - the type of 1 speed DX coil, used for referencing the correct curve set, 
        - choices: ['Residential Central Air Source HP', 'Residential Minisplit HP', 'PSZ-AC']

    cop : float, optional
        default to 3.3. Rated heating coefficient of performance.

    defrost_strategy : str, optional
        defaults to: 'ReverseCycle'. type of defrost strategy. options are ReverseCycle or Resistive

    Returns
    -------
    CoilHeatingDXSingleSpeed : osmod.CoilHeatingDXSingleSpeed
        osmod.CoilHeatingDXSingleSpeed object.
    """

    htg_coil = osmod.CoilHeatingDXSingleSpeed(openstudio_model)

    # add to air loop if specified
    if air_loop_node != None: htg_coil.addToNode(air_loop_node)

    # set coil name
    htg_coil.setName(name)

    # set coil availability schedule
    if schedule == None:
        # default always on
        coil_availability_schedule = openstudio_model.alwaysOnDiscreteSchedule()
    
    else:
        coil_availability_schedule = schedule

    htg_coil.setAvailabilitySchedule(coil_availability_schedule)

    # set coil cop
    htg_coil.setRatedCOP(cop)

    htg_cap_f_of_temp = None
    htg_cap_f_of_flow = None
    htg_energy_input_ratio_f_of_temp = None
    htg_energy_input_ratio_f_of_flow = None
    htg_part_load_fraction = None
    def_eir_f_of_temp = None

    # curve sets
    if type == 'Residential Central Air Source HP':
        # Performance curves
        # These coefficients are in IP UNITS
        heat_cap_ft_coeffs_ip = [0.566333415, -0.000744164, -0.0000103, 0.009414634, 0.0000506, -0.00000675]
        heat_eir_ft_coeffs_ip = [0.718398423, 0.003498178, 0.000142202, -0.005724331, 0.00014085, -0.000215321]
        heat_cap_fflow_coeffs = [0.694045465, 0.474207981, -0.168253446]
        heat_eir_fflow_coeffs = [2.185418751, -1.942827919, 0.757409168]
        heat_plf_fplr_coeffs = [0.8, 0.2, 0]
        defrost_eir_coeffs = [0.1528, 0, 0, 0, 0, 0]

        # Convert coefficients from IP to SI
        heat_cap_ft_coeffs_si = convert_curve_biquadratic(heat_cap_ft_coeffs_ip)
        heat_eir_ft_coeffs_si = convert_curve_biquadratic(heat_eir_ft_coeffs_ip)

        htg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, heat_cap_ft_coeffs_si, 'Heat-Cap-fT', 0, 100, 0, 100)
        htg_cap_f_of_flow = create_curve_quadratic(openstudio_model, heat_cap_fflow_coeffs, 'Heat-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        htg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, heat_eir_ft_coeffs_si, 'Heat-EIR-fT', 0, 100, 0, 100)
        htg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, heat_eir_fflow_coeffs, 'Heat-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        htg_part_load_fraction = create_curve_quadratic(openstudio_model, heat_plf_fplr_coeffs, 'Heat-PLF-fPLR', 0, 1, 0, 1, is_dimensionless = True)

        # Heating defrost curve for reverse cycle
        def_eir_f_of_temp = create_curve_biquadratic(openstudio_model, defrost_eir_coeffs, 'DefrostEIR', -100, 100, -100, 100)
    elif type == 'Residential Minisplit HP':
        # Performance curves
        # These coefficients are in SI UNITS
        heat_cap_ft_coeffs_si = [1.14715889038462, -0.010386676170938, 0, 0.00865384615384615, 0, 0]
        heat_eir_ft_coeffs_si = [0.9999941697687026, 0.004684593830254383, 5.901286675833333e-05, -0.0028624467783091973, 1.3041120194135802e-05, -0.00016172918478765433]
        heat_cap_fflow_coeffs = [1, 0, 0]
        heat_eir_fflow_coeffs = [1, 0, 0]
        heat_plf_fplr_coeffs = [0.89, 0.11, 0]
        defrost_eir_coeffs = [0.1528, 0, 0, 0, 0, 0]

        htg_cap_f_of_temp = create_curve_biquadratic(openstudio_model, heat_cap_ft_coeffs_si, 'Heat-Cap-fT', -100, 100, -100, 100)
        htg_cap_f_of_flow = create_curve_quadratic(openstudio_model, heat_cap_fflow_coeffs, 'Heat-Cap-fFF', 0, 2, 0, 2, is_dimensionless = True)
        htg_energy_input_ratio_f_of_temp = create_curve_biquadratic(openstudio_model, heat_eir_ft_coeffs_si, 'Heat-EIR-fT', -100, 100, -100, 100)
        htg_energy_input_ratio_f_of_flow = create_curve_quadratic(openstudio_model, heat_eir_fflow_coeffs, 'Heat-EIR-fFF', 0, 2, 0, 2, is_dimensionless = True)
        htg_part_load_fraction = create_curve_quadratic(openstudio_model, heat_plf_fplr_coeffs, 'Heat-PLF-fPLR', 0, 1, 0.6, 1, is_dimensionless = True)

        # Heating defrost curve for reverse cycle
        def_eir_f_of_temp = create_curve_biquadratic(openstudio_model, defrost_eir_coeffs, 'Defrost EIR', -100, 100, -100, 100)
    else: # default curve set
        htg_cap_f_of_temp = osmod.CurveCubic(openstudio_model)
        htg_cap_f_of_temp.setName(f"#{htg_coil.name()} Htg Cap Func of Temp Curve")
        htg_cap_f_of_temp.setCoefficient1Constant(0.758746)
        htg_cap_f_of_temp.setCoefficient2x(0.027626)
        htg_cap_f_of_temp.setCoefficient3xPOW2(0.000148716)
        htg_cap_f_of_temp.setCoefficient4xPOW3(0.0000034992)
        htg_cap_f_of_temp.setMinimumValueofx(-20.0)
        htg_cap_f_of_temp.setMaximumValueofx(20.0)

        htg_cap_f_of_flow = osmod.CurveCubic(openstudio_model)
        htg_cap_f_of_flow.setName(f"#{htg_coil.name()} Htg Cap Func of Flow Frac Curve")
        htg_cap_f_of_flow.setCoefficient1Constant(0.84)
        htg_cap_f_of_flow.setCoefficient2x(0.16)
        htg_cap_f_of_flow.setCoefficient3xPOW2(0.0)
        htg_cap_f_of_flow.setCoefficient4xPOW3(0.0)
        htg_cap_f_of_flow.setMinimumValueofx(0.5)
        htg_cap_f_of_flow.setMaximumValueofx(1.5)

        htg_energy_input_ratio_f_of_temp = osmod.CurveCubic(openstudio_model)
        htg_energy_input_ratio_f_of_temp.setName(f"#{htg_coil.name()} EIR Func of Temp Curve")
        htg_energy_input_ratio_f_of_temp.setCoefficient1Constant(1.19248)
        htg_energy_input_ratio_f_of_temp.setCoefficient2x(-0.0300438)
        htg_energy_input_ratio_f_of_temp.setCoefficient3xPOW2(0.00103745)
        htg_energy_input_ratio_f_of_temp.setCoefficient4xPOW3(-0.000023328)
        htg_energy_input_ratio_f_of_temp.setMinimumValueofx(-20.0)
        htg_energy_input_ratio_f_of_temp.setMaximumValueofx(20.0)

        htg_energy_input_ratio_f_of_flow = osmod.CurveQuadratic(openstudio_model)
        htg_energy_input_ratio_f_of_flow.setName(f"#{htg_coil.name()} EIR Func of Flow Frac Curve")
        htg_energy_input_ratio_f_of_flow.setCoefficient1Constant(1.3824)
        htg_energy_input_ratio_f_of_flow.setCoefficient2x(-0.4336)
        htg_energy_input_ratio_f_of_flow.setCoefficient3xPOW2(0.0512)
        htg_energy_input_ratio_f_of_flow.setMinimumValueofx(0.0)
        htg_energy_input_ratio_f_of_flow.setMaximumValueofx(1.0)

        htg_part_load_fraction = osmod.CurveQuadratic(openstudio_model)
        htg_part_load_fraction.setName(f"#{htg_coil.name()} PLR Correlation Curve")
        htg_part_load_fraction.setCoefficient1Constant(0.85)
        htg_part_load_fraction.setCoefficient2x(0.15)
        htg_part_load_fraction.setCoefficient3xPOW2(0.0)
        htg_part_load_fraction.setMinimumValueofx(0.0)
        htg_part_load_fraction.setMaximumValueofx(1.0)

        if defrost_strategy != 'Resistive':
            def_eir_f_of_temp = osmod.CurveBiquadratic.new(openstudio_model)
            def_eir_f_of_temp.setName(f"#{htg_coil.name()} Defrost EIR Func of Temp Curve")
            def_eir_f_of_temp.setCoefficient1Constant(0.297145)
            def_eir_f_of_temp.setCoefficient2x(0.0430933)
            def_eir_f_of_temp.setCoefficient3xPOW2(-0.000748766)
            def_eir_f_of_temp.setCoefficient4y(0.00597727)
            def_eir_f_of_temp.setCoefficient5yPOW2(0.000482112)
            def_eir_f_of_temp.setCoefficient6xTIMESY(-0.000956448)
            def_eir_f_of_temp.setMinimumValueofx(-23.33333)
            def_eir_f_of_temp.setMaximumValueofx(29.44444)
            def_eir_f_of_temp.setMinimumValueofy(-23.33333)
            def_eir_f_of_temp.setMaximumValueofy(29.44444)

    if type == 'PSZ-AC':
        htg_coil.setMinimumOutdoorDryBulbTemperatureforCompressorOperation(-12.2)
        htg_coil.setMaximumOutdoorDryBulbTemperatureforDefrostOperation(1.67)
        htg_coil.setCrankcaseHeaterCapacity(50.0)
        htg_coil.setMaximumOutdoorDryBulbTemperatureforCrankcaseHeaterOperation(4.4)
        htg_coil.setDefrostControl('OnDemand')

        def_eir_f_of_temp = osmod.CurveBiquadratic(openstudio_model)
        def_eir_f_of_temp.setName(f"#{htg_coil.name()} Defrost EIR Func of Temp Curve")
        def_eir_f_of_temp.setCoefficient1Constant(0.297145)
        def_eir_f_of_temp.setCoefficient2x(0.0430933)
        def_eir_f_of_temp.setCoefficient3xPOW2(-0.000748766)
        def_eir_f_of_temp.setCoefficient4y(0.00597727)
        def_eir_f_of_temp.setCoefficient5yPOW2(0.000482112)
        def_eir_f_of_temp.setCoefficient6xTIMESY(-0.000956448)
        def_eir_f_of_temp.setMinimumValueofx(-23.33333)
        def_eir_f_of_temp.setMaximumValueofx(29.44444)
        def_eir_f_of_temp.setMinimumValueofy(-23.33333)
        def_eir_f_of_temp.setMaximumValueofy(29.44444)

    if htg_cap_f_of_temp != None: htg_coil.setTotalHeatingCapacityFunctionofTemperatureCurve(htg_cap_f_of_temp) 
    if htg_cap_f_of_flow != None: htg_coil.setTotalHeatingCapacityFunctionofFlowFractionCurve(htg_cap_f_of_flow)
    if htg_energy_input_ratio_f_of_temp != None: htg_coil.setEnergyInputRatioFunctionofTemperatureCurve(htg_energy_input_ratio_f_of_temp)
    if htg_energy_input_ratio_f_of_flow != None: htg_coil.setEnergyInputRatioFunctionofFlowFractionCurve(htg_energy_input_ratio_f_of_flow)
    if htg_part_load_fraction != None: htg_coil.setPartLoadFractionCorrelationCurve(htg_part_load_fraction)
    if def_eir_f_of_temp != None: htg_coil.setDefrostEnergyInputRatioFunctionofTemperatureCurve(def_eir_f_of_temp)
    htg_coil.setDefrostStrategy(defrost_strategy)
    htg_coil.setDefrostControl('OnDemand')

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

def create_coil_cooling_water(openstudio_model: osmod, chilled_water_loop: osmod.PlantLoop, air_loop_node: osmod.Node = None,
                              name: str = 'Clg Coil', schedule: osmod.Schedule = None, design_inlet_water_temperature: float = None,
                              design_inlet_air_temperature: float = None, design_outlet_air_temperature: float = None) -> osmod.CoilCoolingWater:
    """
    Create a CoilCoolingWater object.
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    chilled_water_loop : osmod.PlantLoop
        he coil will be placed on the demand side of this plant loop.

    air_loop_node : osmod.Node, optional
        default: None, the coil will be placed on this node of the air loop

    name : str, optional
        default: 'Clg Coil', name of the coil.

    schedule : osmod.Schedule, optional
        default: None, availability schedule of the coil, if None = always on.
    
    design_inlet_water_temperature : float, optional
        design inlet water temperature in degrees Celsius, default is nil.
    
    design_inlet_air_temperature : float, optional
        design inlet air temperature in degrees Celsius, default is nil

    design_outlet_air_temperature : float, optional
        design inlet air temperature in degrees Celsius, default is nil.

    Returns
    -------
    CoilCoolingWater : osmod.CoilCoolingWater
        osmod.CoilCoolingWater object.
    """
    clg_coil = osmod.CoilCoolingWater(openstudio_model)

    # add to chilled water loop
    chilled_water_loop.addDemandBranchForComponent(clg_coil)

    # add to air loop if specified
    if air_loop_node != None: clg_coil.addToNode(air_loop_node)

    # set coil name
    clg_coil.setName(name)

    # set coil availability schedule
    if schedule == None:
        # default always on
        coil_availability_schedule = openstudio_model.alwaysOnDiscreteSchedule()
    else:
        coil_availability_schedule = schedule
    
    clg_coil.setAvailabilitySchedule(coil_availability_schedule)

    # rated temperatures
    if design_inlet_water_temperature == None:
        clg_coil.autosizeDesignInletWaterTemperature()
    else:
        clg_coil.setDesignInletWaterTemperature(design_inlet_water_temperature)

    if design_inlet_air_temperature != None: clg_coil.setDesignInletAirTemperature(design_inlet_air_temperature)
    if design_outlet_air_temperature != None: clg_coil.setDesignOutletAirTemperature(design_outlet_air_temperature)

    # defaults
    clg_coil.setHeatExchangerConfiguration('CrossFlow')

    # coil controller properties
    # @note These inputs will get overwritten if addToNode or addDemandBranchForComponent is called on the htg_coil object after this
    clg_coil_controller = clg_coil.controllerWaterCoil().get()
    clg_coil_controller.setName(f"#{clg_coil.name()} Controller")
    clg_coil_controller.setAction('Reverse')
    clg_coil_controller.setMinimumActuatedFlow(0.0)

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

def add_one_ruleset_sch_rule(sch_ruleset: osmod.ScheduleRuleset, start_date: openstudio.Date, end_date: openstudio.Date, values: list[float], 
                             sch_name: str, day_names: list[str]) -> osmod.ScheduleDay:
    '''
    - Create a ScheduleRules object from an hourly array of values for a week
    - It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:add_one_ruleset_sch_rule)
    
    Parameters
    ----------
    sch_ruleset : osmod.ScheduleRuleset
        ScheduleRuleset object
    
    start_date : openstudio.Date
        start date of week period

    end_date : openstudio.Date
        end date of week period

    values : list[float]
        array of hourly values for day (24)

    sch_name : str
        name of ScheduleDay object
    
    day_names : list[str]
        list of days of week for which this day type is applicable

    Returns
    -------
    osmod.ScheduleDay
        ScheduleDay object.
    '''
    # sch_rule is a sub-component of the ScheduleRuleset
    sch_rule = osmod.ScheduleRule(sch_ruleset)
    # Set the dates when the rule applies
    sch_rule.setStartDate(openstudio.Date(openstudio.MonthOfYear(int(start_date.monthOfYear().value())), int(start_date.dayOfMonth())))
    sch_rule.setStartDate(start_date)
    sch_rule.setEndDate(end_date)

    # Set the days for which the rule applies
    for day_of_week in day_names:
        if day_of_week == 'Sunday': sch_rule.setApplySunday(True) 
        if day_of_week == 'Monday': sch_rule.setApplyMonday(True) 
        if day_of_week == 'Tuesday': sch_rule.setApplyTuesday(True) 
        if day_of_week == 'Wednesday': sch_rule.setApplyWednesday(True) 
        if day_of_week == 'Thursday': sch_rule.setApplyThursday(True) 
        if day_of_week == 'Friday': sch_rule.setApplyFriday(True) 
        if day_of_week == 'Saturday': sch_rule.setApplySaturday(True) 

    # Create the day schedule and add hourly values
    day_sch = sch_rule.daySchedule()
    # day_sch = OpenStudio::Model::ScheduleDay.new(model)
    day_sch.setName(sch_name)
    for ihr in range(24):
        if values[ihr] == values[ihr + 1]:
            continue
        day_sch.addValue(openstudio.Time(0, ihr + 1, 0, 0), values[ihr])

    return sch_rule

def make_week_ruleset_sched_from_168(sch_ruleset: osmod.ScheduleRuleset, values: list[float], start_date: openstudio.Date, 
                                     end_date: openstudio.Date, sch_name: str) -> list[osmod.ScheduleRule]:
    '''
    - Create a ScheduleRules object from an hourly array of values for a week
    - It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard#make_week_ruleset_sched_from_168-instance_method)
    
    Parameters
    ----------
    sch_ruleset : osmod.ScheduleRuleset
        ScheduleRuleset object
    
    values : list[float]
        array of hourly values for week (168)
    
    start_date : openstudio.Date
        start date of week period

    end_date : openstudio.Date
        end date of week period

    sch_name : str
        name of parent ScheduleRuleset object.

    Returns
    -------
    list[osmod.ScheduleRule]
        the resultant ruleset.
    '''
    one_day = openstudio.Time(1.0)
    now_date = start_date - one_day
    days_of_week = []
    values_by_day = []
    # Organize data into days
    # create a 2-D array values_by_day[iday][ihr]
    hr_of_wk = -1
    for iday in range(7):
        hr_values = []
        for hr_of_day in range(24):
            hr_of_wk += 1
            hr_values.append(values[hr_of_wk])
        values_by_day.append(hr_values)
        now_date += one_day
        days_of_week.append(now_date.dayOfWeek().valueName())

    # Make list of unique day schedules
    # First one is automatically unique
    # Store indexes to days with the same sched in array of arrays
    # day_sched_idays[0] << 0
    day_sched = {}
    day_sched['day_idx_list'] = [0]
    day_sched['hr_values'] = values_by_day[0]
    day_scheds = []
    day_scheds.append(day_sched)

    # Check each day with the cumulative list of day_scheds and add new, if unique
    for iday in range(7):
        match_was_found = False
        for day_sched in day_scheds:
            # Compare each jday to the current iday and check for a match
            is_a_match = True
            for ihr in range(24):
                if day_sched['hr_values'][ihr] != values_by_day[iday][ihr]:
                    # this hour is not a match
                    is_a_match = False
                    break

            if is_a_match:
                # Add the day index to the list for this day_sched
                day_sched['day_idx_list'].append(iday)
                match_was_found = True
                break

            if match_was_found == False:
                # Add a new day type
                day_sched = {}
                day_sched['day_idx_list'] = [iday]
                day_sched['hr_values'] = values_by_day[iday]
                day_scheds.append(day_sched)
        
    # Add the Rule and Day objects
    sch_rules = []
    iday_sch = 0
    for day_sched in day_scheds:
        iday_sch += 1

        day_names = []
        for idx in day_sched['day_idx_list']:
            day_names.append(days_of_week[idx])
        
        day_sch_name = f"{sch_name} Day {iday_sch}"
        day_sch_values = day_sched['hr_values']
        sch_rule = add_one_ruleset_sch_rule(sch_ruleset, start_date, end_date, day_sch_values, day_sch_name, day_names)

        sch_rules.append(sch_rule)
    return sch_rules

def make_ruleset_sched_from_8760(openstudio_model: osmod, values: list[float], sch_name: str, sch_type_limits: osmod.ScheduleTypeLimits) -> osmod.ScheduleRuleset:
    '''
    - Create a ScheduleRuleset object from an 8760 sequential array of values for a Values array will actually include 24 extra values if model year is a leap year 
    - Values array will also include 24 values at end of array representing the holiday day schedule
    - It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:make_ruleset_sched_from_8760)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    value : list[float]
        array of annual values (8760 / 24) holiday values (24)
    
    sch_name : sch_name
        schedule name.

    sch_type_limits : osmod.ScheduleTypeLimits
        ScheduleTypeLimits object

    Returns
    -------
    osmod.ScheduleRuleset
        the resultant ruleset.
    '''
    # Build array of arrays: each top element is a week, each sub element is an hour of week
    all_week_values = []
    hr_of_yr = -1
    for iweek in range(52):
        week_values = []
        for hr_of_wk in range(168):
            hr_of_yr += 1
            week_values[hr_of_wk] = values[hr_of_yr]
        all_week_values.append(week_values)

    # Extra week for days 365 and 366 (if applicable) of year
    # since 52 weeks is 364 days
    hr_of_yr += 1
    last_hr = len(values) - 1
    iweek = 52
    week_values = []
    hr_of_wk = -1
    for ihr_of_yr in range(hr_of_yr, last_hr + 1):
        hr_of_wk += 1
        week_values[hr_of_wk] = values[ihr_of_yr]
    all_week_values.append(week_values)

    # Build ruleset schedules for first week
    yd = openstudio_model.getYearDescription()
    start_date = yd.makeDate(1, 1)
    one_day = openstudio.Time(1.0)
    seven_days = openstudio.Time(7.0)
    end_date = start_date + seven_days - one_day

    # Create new ruleset schedule
    sch_ruleset = osmod.ScheduleRuleset(openstudio_model)
    sch_ruleset.setName(sch_name)
    sch_ruleset.setScheduleTypeLimits(sch_type_limits)

    # Make week schedule for first week
    num_week_scheds = 1
    week_sch_name = sch_name + '_ws' + str(num_week_scheds)
    week_1_rules = make_week_ruleset_sched_from_168(sch_ruleset, all_week_values[1], start_date, end_date, week_sch_name)
    week_n_rules = week_1_rules
    all_week_rules = []
    all_week_rules << week_1_rules
    iweek_previous_week_rule = 0

    # temporary loop for debugging
    for sch_rule in week_n_rules:
        day_rule = sch_rule.daySchedule()
        xtest = 1

    # For each subsequent week, check if it is same as previous
    # If same, then append to Schedule:Rule of previous week
    # If different, then create new Schedule:Rule
    for iweek in range(52):
        is_a_match = True
        start_date = end_date + one_day
        end_date += seven_days
        for ihr in range(168):
            if all_week_values[iweek][ihr] != all_week_values[iweek_previous_week_rule][ihr]:
                is_a_match = False
                break

        if is_a_match:
            # Update the end date for the Rules of the previous week to include this week
            for sch_rule in all_week_rules[iweek_previous_week_rule]:
                sch_rule.setEndDate(end_date)
        else:
            # Create a new week schedule for this week
            num_week_scheds += 1
            week_sch_name = sch_name + '_ws' + str(num_week_scheds)
            week_n_rules = make_week_ruleset_sched_from_168(sch_ruleset, all_week_values[iweek], start_date, end_date, week_sch_name)
            all_week_rules.append(week_n_rules)
            # Set this week as the reference for subsequent weeks
            iweek_previous_week_rule = iweek

    # temporary loop for debugging
    for sch_rule in week_n_rules:
        day_rule = sch_rule.daySchedule()
        xtest = 1

    # Need to handle week 52 with days 365 and 366
    # For each of these days, check if it matches a day from the previous week
    iweek = 52
    # First handle day 365
    end_date += one_day
    start_date = end_date
    match_was_found = False
    # week_n is the previous week
    for sch_rule in week_n_rules:
        day_rule = sch_rule.daySchedule()
        is_match = True
        # Need a 24 hour array of values for the day rule
        ihr_start = 0
        day_values = []
        for timex in day_rule.times():
            now_value = float(day_rule.getValue(timex))
            until_ihr = int(timex.totalHours()) - 1
            for ihr in range(ihr_start, until_ihr+1):
                day_values.append(now_value)
        
        for ihr in range(24):
            if day_values[ihr] != all_week_values[iweek][ihr + ihr_start]:
                # not matching for this day_rule
                is_match = False
                break
            
        if is_match:
            match_was_found = True
            # Extend the schedule period to include this day
            sch_rule.setEndDate(end_date)
            break

    if match_was_found == False:
        # Need to add a new rule
        day_of_week = start_date.dayOfWeek().valueName()
        day_names = [day_of_week]
        day_sch_name = sch_name + '_Day_365'
        day_sch_values = []
        for ihr in range(24):
            day_sch_values.append(all_week_values[iweek][ihr])
        # sch_rule is a sub-component of the ScheduleRuleset
        sch_rule = add_one_ruleset_sch_rule(sch_ruleset, start_date, end_date, day_sch_values, day_sch_name, day_names)
        week_n_rules = sch_rule
    

    # Handle day 366, if leap year
    # Last day in this week is the holiday schedule
    # If there are three days in this week, then the second is day 366
    if len(all_week_values[iweek]) == 24 * 3:
        ihr_start = 23
        end_date += one_day
        start_date = end_date
        match_was_found = False
        # week_n is the previous week
        # which would be the week based on day 356, if that was its own week
        for sch_rule in week_n_rules:
            day_rule = sch_rule.daySchedule
            is_match = True
            for ihr in day_rule.times():
                if float(day_rule.getValue(ihr)) != all_week_values[iweek][ihr + ihr_start]:
                    # not matching for this day_rule
                    is_match = False
                    break
                
            if is_match:
                match_was_found = True
                # Extend the schedule period to include this day
                sch_rule.setEndDate(openstudio.Date(openstudio.MonthOfYear(int(end_date.month())), int(end_date.day())))
                break

        if match_was_found == False:
        # Need to add a new rule
        # sch_rule is a sub-component of the ScheduleRuleset
            day_of_week = start_date.dayOfWeek().valueName()
            day_names = [day_of_week]
            day_sch_name = sch_name + '_Day_366'
            day_sch_values = []
            for ihr in range(24):
                day_sch_values.append(all_week_values[iweek][ihr])
            
            sch_rule = add_one_ruleset_sch_rule(sch_ruleset, start_date, end_date, day_sch_values, day_sch_name, day_names)
            week_n_rules = sch_rule
        # Last day in values array is the holiday schedule
        # @todo add holiday schedule when implemented in OpenStudio SDK

    # Need to handle design days
    # Find schedule with the most operating hours in a day,
    # and apply that to both cooling and heating design days
    hr_of_yr = -1
    max_eflh = 0
    ihr_max = -1
    for iday in range(365):
        eflh = 0
        ihr_start = hr_of_yr + 1
        for ihur in range(24):
            hr_of_yr += 1
            if values[hr_of_yr] > 0:
                eflh += 1 
        
        if eflh > max_eflh:
            max_eflh = eflh
            # store index to first hour of day with max on hours
            ihr_max = ihr_start
            
    # Create the schedules for the design days
    day_sch = osmod.ScheduleDay(openstudio_model)
    day_sch.setName(sch_name + 'Winter Design Day')
    for ihr in range(24):
        hr_of_yr = ihr_max + ihr
        if values[hr_of_yr] == values[hr_of_yr + 1]:
            continue
        day_sch.addValue(openstudio.Time(0, ihr + 1, 0, 0), values[hr_of_yr])
    
    sch_ruleset.setWinterDesignDaySchedule(day_sch)

    day_sch = osmod.ScheduleDay(openstudio_model)
    day_sch.setName(sch_name + 'Summer Design Day')
    for ihr in range(24):
        hr_of_yr = ihr_max + ihr
        if values[hr_of_yr] == values[hr_of_yr + 1]:
            continue

        day_sch.addValue(openstudio.Time(0, ihr + 1, 0, 0), values[hr_of_yr])
    
    sch_ruleset.setSummerDesignDaySchedule(day_sch)

    return sch_ruleset

def add_vals_to_sch(day_sch: osmod.ScheduleDay, sch_type: str, values: list[float]):
    """
    fill in hourly values of schedules

    Parameters
    ----------
    day_sch : osmod.ScheduleDay
        the day schedule to fill in the values.
    
    sch_type : str
        Constant or Hourly.
    
    values : list[float]
        Values to fill in.
    
    """
    if sch_type == 'Constant':
      day_sch.addValue(openstudio.Time(0, 24, 0, 0), values[0])
    elif sch_type == 'Hourly':
      for i in range(24):
        if i <= 22:      
            if values[i] == values[i + 1]:
                continue

        day_sch.addValue(openstudio.Time(0, i + 1, 0, 0), values[i])
    else:
      print('openstudio.standards.Model', f"Schedule type: #{sch_type} is not recognized.  Valid choices are 'Constant' and 'Hourly'.")

def add_schedule(openstudio_model: osmod, schedule_name: str) -> osmod.ScheduleRuleset:
    """
    Create a schedule from the openstudio standards dataset and add it to the model.

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    schedule_name : str
        name of the schedule.
    
    Returns
    -------
    schedule : osmod.ScheduleRuleset
        the resultant schedule ruleset.
    """
    # First check model and return schedule if it already exists
    mod_schedules = openstudio_model.getSchedules()
    for schedule in mod_schedules:
        if str(schedule.name().get()) == schedule_name:
            print('openstudio.standards.Model', f"Already added schedule: #{schedule_name}")
        return schedule
    
    # Find all the schedule rules that match the name
    sch_json_path = ASHRAE_DATA_DIR.joinpath('ashrae_90_1.schedules.json')
    rules = find_obj_frm_json_based_on_type_name(sch_json_path, 'schedules', schedule_name)
    if rules == None:
        print('openstudio.standards.Model', f"Cannot find data for schedule: #{schedule_name}, will not be created.")
        return openstudio_model.alwaysOnDiscreteSchedule()
    
    # Make a schedule ruleset
    sch_ruleset = osmod.ScheduleRuleset(openstudio_model)
    sch_ruleset.setName(schedule_name)

    # Loop through the rules, making one for each row in the spreadsheet
    for rule in rules:
        day_types = rule['day_types']
        start_date = parse(rule['start_date'])
        end_date = parse(rule['end_date'])
        sch_type = rule['type']
        values = rule['values']

        # Day Type choices: Wkdy, Wknd, Mon, Tue, Wed, Thu, Fri, Sat, Sun, WntrDsn, SmrDsn, Hol
        # Default
        if 'Default' in day_types:
            day_sch = sch_ruleset.defaultDaySchedule()
            day_sch.setName(f"#{schedule_name} Default")
            add_vals_to_sch(day_sch, sch_type, values)

        # Winter Design Day
        if 'WntrDsn' in day_types:
            day_sch = osmod.ScheduleDay(openstudio_model)
            sch_ruleset.setWinterDesignDaySchedule(day_sch)
            day_sch = sch_ruleset.winterDesignDaySchedule()
            day_sch.setName(f"#{schedule_name} Winter Design Day")
            add_vals_to_sch(day_sch, sch_type, values)

        # Summer Design Day
        if 'SmrDsn' in day_types:
            day_sch = osmod.ScheduleDay(openstudio_model)
            sch_ruleset.setSummerDesignDaySchedule(day_sch)
            day_sch = sch_ruleset.summerDesignDaySchedule()
            day_sch.setName(f"#{schedule_name} Summer Design Day")
            add_vals_to_sch(day_sch, sch_type, values)
        
        # Other days (weekdays, weekends, etc)
        if ('Wknd' in day_types or 'Wkdy' in day_types or 'Sat' in day_types or 'Sun' in day_types or 'Mon' in day_types 
            or 'Tue' in day_types or 'Wed' in day_types or 'Thu' in day_types or 'Fri' in day_types):
            # Make the Rule
            sch_rule = osmod.ScheduleRule(sch_ruleset)
            day_sch = sch_rule.daySchedule()
            day_sch.setName(f"#{schedule_name} #{day_types} Day")
            add_vals_to_sch(day_sch, sch_type, values)

            # Set the dates when the rule applies
            sch_rule.setStartDate(openstudio.Date(openstudio.MonthOfYear(start_date.month), start_date.day))
            sch_rule.setEndDate(openstudio.Date(openstudio.MonthOfYear(end_date.month), end_date.day))

            # Set the days when the rule applies
            # Weekends
            if 'Wknd' in day_types:
                sch_rule.setApplySaturday(True)
                sch_rule.setApplySunday(True)

            # Weekdays
            if 'Wkdy' in day_types:
                sch_rule.setApplyMonday(True)
                sch_rule.setApplyTuesday(True)
                sch_rule.setApplyWednesday(True)
                sch_rule.setApplyThursday(True)
                sch_rule.setApplyFriday(True)

            # Individual Days
            if 'Mon' in day_types: sch_rule.setApplyMonday(True) 
            if 'Tue' in day_types: sch_rule.setApplyTuesday(True)
            if 'Wed' in day_types: sch_rule.setApplyWednesday(True)
            if 'Thu' in day_types: sch_rule.setApplyThursday(True)
            if 'Fri' in day_types: sch_rule.setApplyFriday(True)
            if 'Sat' in day_types: sch_rule.setApplySaturday(True)
            if 'Sun' in day_types: sch_rule.setApplySunday(True)

    return sch_ruleset

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

def condenser_water_temperatures(design_oat_wb_c: float) -> list[float]:
    """
    Determine the performance rating method specified design condenser water temperature, approach, and range
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:prototype_condenser_water_temperatures)

    Parameters
    ----------
    design_oat_wb_c : float
        the design OA wetbulb temperature degC

    Returns
    -------
    res_temperatures : list[float]
        leaving_cw_t_c, approach_k, range_k
    """
    design_oat_wb_f = openstudio.convert(design_oat_wb_c, 'C', 'F').get()

    # 90.1-2010 G3.1.3.11 - CW supply temp = 85F or 10F approaching design wet bulb temperature, whichever is lower.
    # Design range = 10F
    # Design Temperature rise of 10F => Range: 10F
    range_r = 10.0

    # Determine the leaving CW temp
    max_leaving_cw_t_f = 85.0
    leaving_cw_t_10f_approach_f = design_oat_wb_f + 10.0
    leaving_cw_t_f = min([max_leaving_cw_t_f, leaving_cw_t_10f_approach_f])

    # Calculate the approach
    approach_r = leaving_cw_t_f - design_oat_wb_f

    # Convert to SI units
    leaving_cw_t_c = openstudio.convert(leaving_cw_t_f, 'F', 'C').get()
    approach_k = openstudio.convert(approach_r, 'R', 'K').get()
    range_k = openstudio.convert(range_r, 'R', 'K').get()

    return [leaving_cw_t_c, approach_k, range_k]

def apply_condenser_water_temperatures(condenser_loop: osmod.PlantLoop, design_wet_bulb_c: float = 25.6) -> bool:
    """
    Apply approach temperature sizing criteria to a condenser water loop
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:prototype_apply_condenser_water_temperatures)
    
    Parameters
    ----------
    condenser_loop : osmod.PlantLoop
        condenser loop
    
    design_wet_bulb_c : float
        design wet bulb temperature in degC. default is 25.6C
    
    Returns
    -------
    success : bool
        True if successful
    """
    sizing_plant = condenser_loop.sizingPlant()
    loop_type = sizing_plant.loopType()
    if loop_type == 'Condenser':
        return False

    # EnergyPlus has a minimum limit of 20C and maximum limit of 26.7C for cooling towers
    if design_wet_bulb_c > 26.7:
        design_wet_bulb_c = 26.7
        print(f"For condenser loop #{condenser_loop.name()}, reduced design OATwb to max limit of 26.7C.")
    elif design_wet_bulb_c < 20.0:
        design_wet_bulb_c = 20
        print(f"For condenser loop #{condenser_loop.name()}, increased design OATwb to min limit of 20.0C ")

    # Determine the design CW temperature, approach, and range
    leaving_cw_t_c, approach_k, range_k = condenser_water_temperatures(design_wet_bulb_c)

    # Report out design conditions
    print('openstudio.Prototype.CoolingTower', 
          f"For condenser loop #{condenser_loop.name()}, design OATwb = #{design_wet_bulb_c}C, approach = #{approach_k} deltaK, range = #{range_k} deltaK, leaving condenser water temperature = #{leaving_cw_t_c}C.")

    # Set Cooling Tower sizing parameters.
    # Only the variable speed cooling tower in E+ allows you to set the design temperatures.
    #
    # Per the documentation
    # http://bigladdersoftware.com/epx/docs/8-4/input-output-reference/group-condenser-equipment.html#field-design-u-factor-times-area-value
    # for CoolingTowerSingleSpeed and CoolingTowerTwoSpeed
    # E+ uses the following values during sizing:
    # 95F entering water temp
    # 95F OATdb
    # 78F OATwb
    # range = loop design delta-T aka range (specified above)
    for sc in condenser_loop.supplyComponents():
        if sc.to_CoolingTowerVariableSpeed().empty() == False:
            ct = sc.to_CoolingTowerVariableSpeed().get()
            ct.setDesignInletAirWetBulbTemperature(design_wet_bulb_c)
            ct.setDesignApproachTemperature(approach_k)
            ct.setDesignRangeTemperature(range_k)

    # Set the CW sizing parameters
    # EnergyPlus autosizing routine assumes 85F and 10F temperature difference
    energyplus_design_loop_exit_temperature_c = openstudio.convert(85.0, 'F', 'C').get()
    sizing_plant.setDesignLoopExitTemperature(energyplus_design_loop_exit_temperature_c)
    sizing_plant.setLoopDesignTemperatureDifference(openstudio.convert(10.0, 'R', 'K').get())

    # Cooling Tower operational controls
    # G3.1.3.11 - Tower shall be controlled to maintain a 70F LCnWT where weather permits,
    # floating up to leaving water at design conditions.
    float_down_to_f = 70.0
    float_down_to_c = openstudio.convert(float_down_to_f, 'F', 'C').get()

    # get or create a setpoint manager
    cw_t_stpt_manager = None
    for spm in condenser_loop.supplyOutletNode().setpointManagers():
        if spm.to_SetpointManagerFollowOutdoorAirTemperature().empty() == False:
            if 'Setpoint Manager Follow OATwb' in spm.name().get(): 
                cw_t_stpt_manager = spm.to_SetpointManagerFollowOutdoorAirTemperature().get()

    if cw_t_stpt_manager == None:
        cw_t_stpt_manager = osmod.SetpointManagerFollowOutdoorAirTemperature(condenser_loop.model())
        cw_t_stpt_manager.addToNode(condenser_loop.supplyOutletNode())

    cw_t_stpt_manager.setName(f"#{condenser_loop.name()} Setpoint Manager Follow OATwb with #{round(approach_k, 1)}K Approach")
    cw_t_stpt_manager.setReferenceTemperatureType('OutdoorAirWetBulb')
    # At low design OATwb, it is possible to calculate
    # a maximum temperature below the minimum.  In this case,
    # make the maximum and minimum the same.
    if leaving_cw_t_c < float_down_to_c:
        print('openstudio.standards.PlantLoop', f"For #{condenser_loop.name()}, the maximum leaving temperature of #{leaving_cw_t_c}C is below the minimum of #{float_down_to_c}C.  The maximum will be set to the same value as the minimum.")
        leaving_cw_t_c = float_down_to_c

    cw_t_stpt_manager.setMaximumSetpointTemperature(leaving_cw_t_c)
    cw_t_stpt_manager.setMinimumSetpointTemperature(float_down_to_c)
    cw_t_stpt_manager.setOffsetTemperatureDifference(approach_k)

    return True

def find_obj_frm_json_based_on_type_name(json_path: str, objtype: str, name: str) -> dict:
    """
    find an object based on object name of a json file.

    Parameters
    ----------
    json_path : str
        the path to the json file to search for.

    objtype : str
        the obj type e.g. 'curves', 'schedules'.
    
    name : str
        the name of the object to find.
    
    Returns
    -------
    found_obj : dict
        the found object
    """
    found_obj = None
    with open(json_path) as json_f:
        data = json.load(json_f)
        obj_datas = data[objtype]
        for obj_data in obj_datas:
            if obj_data['name'] == name:
                found_obj = obj_data
                break
    return found_obj

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
        the name of the curve.
    
    Returns
    -------
    res_curve : osmod.Curve
        the resultant curve
    """
    # First check model and return curve if it already exists
    existing_curves = []
    existing_curves += openstudio_model.getCurveLinears()
    existing_curves += openstudio_model.getCurveCubics()
    existing_curves += openstudio_model.getCurveQuadratics()
    existing_curves += openstudio_model.getCurveBicubics()
    existing_curves += openstudio_model.getCurveBiquadratics()
    existing_curves += openstudio_model.getCurveQuadLinears()
    for curve in existing_curves:
        if str(curve.name().get()) == curve_name:
            print(f"Already added curve: #{curve_name}")
            return curve

    # Find curve data
    crv_json_path = ASHRAE_DATA_DIR.joinpath('ashrae_90_1_prm.curves.json')
    data = find_obj_frm_json_based_on_type_name(crv_json_path, 'curves', curve_name)
    if data == None:
        print(f"Could not find a curve called '#{curve_name}' in the standards.")
        return None

    # Make the correct type of curve
    crv_form = data['form']
    if crv_form == 'Linear':
        curve = osmod.CurveLinear(openstudio_model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        if data['minimum_independent_variable_1'] != None:
            curve.setMinimumValueofx(data['minimum_independent_variable_1'])
        if data['maximum_independent_variable_1'] != None:
            curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_dependent_variable_output'] != None:
            curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output'] != None:
            curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) 
        return curve
    elif crv_form == 'Cubic':
        curve = osmod.CurveCubic(openstudio_model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setCoefficient4xPOW3(data['coeff_4'])
        if data['minimum_independent_variable_1']: curve.setMinimumValueofx(data['minimum_independent_variable_1']) 
        if data['maximum_independent_variable_1']: curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_dependent_variable_output']: curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output']: curve.setMaximumCurveOutput(data['maximum_dependent_variable_output'])
        return curve
    elif crv_form == 'Quadratic':
        curve = osmod.CurveQuadratic(openstudio_model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        if data['minimum_independent_variable_1'] != None:
            curve.setMinimumValueofx(data['minimum_independent_variable_1'])
        if data['maximum_independent_variable_1'] != None: 
            curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_dependent_variable_output'] != None: 
            curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output'] != None: 
            curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) 
        return curve
    elif crv_form == 'BiCubic':
        curve = osmod.CurveBicubic(openstudio_model)
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
        if data['minimum_independent_variable_1'] != None:
            curve.setMinimumValueofx(data['minimum_independent_variable_1'])
        if data['maximum_independent_variable_1'] != None: 
            curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_independent_variable_2'] != None: 
            curve.setMinimumValueofy(data['minimum_independent_variable_2'])
        if data['maximum_independent_variable_2'] != None: 
            curve.setMaximumValueofy(data['maximum_independent_variable_2'])
        if data['minimum_dependent_variable_output'] != None:
            curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output'] != None: 
            curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) 
        return curve
    elif crv_form == 'BiQuadratic':
        curve = osmod.CurveBiquadratic(openstudio_model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient3xPOW2(data['coeff_3'])
        curve.setCoefficient4y(data['coeff_4'])
        curve.setCoefficient5yPOW2(data['coeff_5'])
        curve.setCoefficient6xTIMESY(data['coeff_6'])
        if data['minimum_independent_variable_1'] != None:
            curve.setMinimumValueofx(data['minimum_independent_variable_1'])
        if data['maximum_independent_variable_1'] != None: 
            curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_independent_variable_2'] != None: 
            curve.setMinimumValueofy(data['minimum_independent_variable_2'])
        if data['maximum_independent_variable_2'] != None: 
            curve.setMaximumValueofy(data['maximum_independent_variable_2'])
        if data['minimum_dependent_variable_output'] != None:
            curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output'] != None: 
            curve.setMaximumCurveOutput(data['maximum_dependent_variable_output'])
        return curve
    elif crv_form == 'BiLinear':
        curve = osmod.CurveBiquadratic(openstudio_model)
        curve.setName(data['name'])
        curve.setCoefficient1Constant(data['coeff_1'])
        curve.setCoefficient2x(data['coeff_2'])
        curve.setCoefficient4y(data['coeff_3'])
        if data['minimum_independent_variable_1'] != None:
            curve.setMinimumValueofx(data['minimum_independent_variable_1'])
        if data['maximum_independent_variable_1'] != None: 
            curve.setMaximumValueofx(data['maximum_independent_variable_1'])
        if data['minimum_independent_variable_2'] != None: 
            curve.setMinimumValueofy(data['minimum_independent_variable_2'])
        if data['maximum_independent_variable_2'] != None: 
            curve.setMaximumValueofy(data['maximum_independent_variable_2'])
        if data['minimum_dependent_variable_output'] != None:
            curve.setMinimumCurveOutput(data['minimum_dependent_variable_output'])
        if data['maximum_dependent_variable_output'] != None: 
            curve.setMaximumCurveOutput(data['maximum_dependent_variable_output']) 
        return curve
    elif crv_form == 'QuadLinear':
        curve = osmod.CurveQuadLinear(openstudio_model)
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
    else:
        print(f"#{curve_name}' has an invalid form: #{crv_form}', cannot create this curve.")
        return None

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

            twr_fan_curve = add_curve(openstudio_model, 'VSD-TWR-FAN-FPLR')
            cooling_tower.setFanPowerRatioFunctionofAirFlowRateRatioCurve(twr_fan_curve)
        else:
            print('openstudio.Prototype.hvac_systems', f"#{cooling_tower_capacity_control} is not a valid choice of cooling tower capacity control.  Valid choices are Fluid Bypass, Fan Cycling, TwoSpeed Fan, Variable Speed Fan.")
        
        # Set the properties that apply to all tower types and attach to the condenser loop.
        if cooling_tower != None:
            cooling_tower.setName(f"#{cooling_tower_fan_type} #{cooling_tower_capacity_control} #{cooling_tower_type}")
            cooling_tower.setSizingFactor(1 / number_cooling_towers)
            cooling_tower.setNumberofCells(number_of_cells_per_tower)
            condenser_water_loop.addSupplyBranchForComponent(cooling_tower)

    # apply 90.1 sizing temperatures
    if use_90_1_design_sizing:
        # use the formulation in 90.1-2010 G3.1.3.11 to set the approach temperature
        print('openstudio.Prototype.hvac_systems', f"Using the 90.1-2010 G3.1.3.11 approach temperature sizing methodology for condenser loop #{condenser_water_loop.name()}.")

        # first, look in the model design day objects for sizing information
        summer_oat_wbs_f = []
        ddays = condenser_water_loop.model().getDesignDays()
        for dd in ddays:
            if dd.dayType() == 'SummerDesignDay':
                if 'WB=>MDB' in str(dd.name().get()):
                    if dd.humidityIndicatingType() == 'Wetbulb':
                        summer_oat_wb_c = dd.humidityIndicatingConditionsAtMaximumDryBulb()
                        summer_oat_wbs_f.append(openstudio.convert(summer_oat_wb_c, 'C', 'F').get())
            else:
                print('openstudio.Prototype.hvac_systems', f"For #{dd.name()}, humidity is specified as #{dd.humidityIndicatingType()}; cannot determine Twb.")

        # if no design day objects are present in the model, attempt to load the .ddy file directly
        if len(summer_oat_wbs_f) == 0:
            print('openstudio.Prototype.hvac_systems', 'No valid WB=>MDB Summer Design Days were found in the model.  Attempting to load wet bulb sizing from the .ddy file directly.')
        if openstudio_model.weatherFile().empty() == False and openstudio_model.weatherFile().get().path().empty() == False:
            weather_file = str(openstudio_model.weatherFile().get().path().get())
            # Run differently depending on whether running from embedded filesystem in OpenStudio CLI or not
            # Attempt to load in the ddy file based on convention that it is in the same directory and has the same basename as the epw file.
            ddy_file = weather_file.replace('.epw', '.ddy')
            if os.path.isfile(ddy_file):
                rev_translate = openstudio.energyplus.ReverseTranslator()
                ddy_model = rev_translate.loadModel(ddy_file)
            else:
                print('openstudio.Prototype.hvac_systems', f"Could not locate a .ddy file for weather file path #{weather_file}")

            if ddy_model.empty() == False:
                designday_objs = ddy_model.getObjectsByType('OS:SizingPeriod:DesignDay')
                for dd in designday_objs:
                    ddy_name = dd.name().get()
                    if '4% Condns WB=>MDB' in ddy_name:
                        summer_oat_wb_c = dd.humidityIndicatingConditionsAtMaximumDryBulb()
                        summer_oat_wbs_f.append(openstudio.convert(summer_oat_wb_c, 'C', 'F').get())
        else:
            print('openstudio.Prototype.hvac_systems', 'The model does not have a weather file object or path specified in the object. Cannot get .ddy file directory.')

        # if values are still absent, use the CTI rating condition 78F
        design_oat_wb_f = None
        if len(summer_oat_wbs_f) == 0:
            design_oat_wb_f = 78.0
            print('openstudio.Prototype.hvac_systems', f"For condenser loop #{condenser_water_loop.name()}, no design day OATwb conditions found.  CTI rating condition of 78F OATwb will be used for sizing cooling towers.")
        else:
            # Take worst case condition
            design_oat_wb_f = max(summer_oat_wbs_f)
            print('openstudio.Prototype.hvac_systems', f"The maximum design wet bulb temperature from the Summer Design Day WB=>MDB is #{design_oat_wb_f} F")
    
        design_oat_wb_c = openstudio.convert(design_oat_wb_f, 'F', 'C').get()

        # call method to apply design sizing to the condenser water loop
        apply_condenser_water_temperatures(condenser_water_loop, design_wet_bulb_c = design_oat_wb_c)

    # Condenser water loop pipes
    cooling_tower_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    cooling_tower_bypass_pipe.setName(f"#{condenser_water_loop.name()} Cooling Tower Bypass")
    condenser_water_loop.addSupplyBranchForComponent(cooling_tower_bypass_pipe)

    chiller_bypass_pipe = osmod.PipeAdiabatic(openstudio_model)
    chiller_bypass_pipe.setName(f"#{condenser_water_loop.name()} Chiller Bypass")
    condenser_water_loop.addDemandBranchForComponent(chiller_bypass_pipe)

    supply_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    supply_outlet_pipe.setName(f"#{condenser_water_loop.name()} Supply Outlet")
    supply_outlet_pipe.addToNode(condenser_water_loop.supplyOutletNode())

    demand_inlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_inlet_pipe.setName(f"#{condenser_water_loop.name()} Demand Inlet")
    demand_inlet_pipe.addToNode(condenser_water_loop.demandInletNode())

    demand_outlet_pipe = osmod.PipeAdiabatic(openstudio_model)
    demand_outlet_pipe.setName(f"#{condenser_water_loop.name()} Demand Outlet")
    demand_outlet_pipe.addToNode(condenser_water_loop.demandOutletNode)()

    return condenser_water_loop

def find_standard_climate_zone_frm_osmod(openstudio_model: osmod) -> str:
    """
    - Find and Converts the climate zone in the model into the format used by the openstudio-standards lookup tables.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_standards_climate_zone

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    Returns
    -------
    climate_zone : str
        string specifying the climate zone.
    """
    climate_zone = ''
    osmod_czs = openstudio_model.getClimateZones()#.climateZones
    for cz in osmod_czs:
        if cz.institution() == 'ASHRAE':
            if cz.value() == '':
                continue

            if cz.value == '7' or cz.value == '8':
                climate_zone = f"ASHRAE 169-2013-#{cz.value}A"
            else:
                climate_zone = f"ASHRAE 169-2013-#{cz.value}"
        
        elif cz.institution == 'CEC':
            if cz.value == '': # Skip blank ASHRAE climate zones put in by OpenStudio Application
                continue

            climate_zone = f"CEC T24-CEC#{cz.value}"

    return climate_zone

def find_climate_zone_set(openstudio_model: osmod, climate_zone: str) -> str:
    """
    - Helper method to find out which climate zone set contains a specific climate zone. Returns climate zone set name as String if success, nil if not found
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_find_climate_zone_set

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    climate_zone : str
        name of the climate zone.
    
    Returns
    -------
    climate zone set : str
        climate zone set.
    """
    result = None
    climate_zone_sets_path = ASHRAE_DATA_DIR.joinpath('ashrae_90_1.climate_zone_sets.json')

    with open(climate_zone_sets_path) as json_f:
        data = json.load(json_f)
        climate_zone_sets = data['climate_zone_sets']

    possible_climate_zone_sets = []
    for climate_zone_set in climate_zone_sets:
        if climate_zone in climate_zone_set['climate_zones']:
            possible_climate_zone_sets.append(climate_zone_set['name'])

    # Check the results
    if len(possible_climate_zone_sets) == 0:
        print('openstudio.standards.Model', f"Cannot find a climate zone set containing #{climate_zone}.  Make sure to use ASHRAE standards with ASHRAE climate zones and DEER or CA Title 24 standards with CEC climate zones.")
    elif len(possible_climate_zone_sets) > 2:
        print('openstudio.standards.Model', f"Found more than 2 climate zone sets containing #{climate_zone}; will return last matching climate zone set.")

    # Get the climate zone from the possible set
    climate_zone_set = min(possible_climate_zone_sets)
    return climate_zone_set

def ems_friendly_name(name: str) -> str:
    """
    change str to ems friendly

    Parameters
    ----------
    name : str
        str to convert.

    Returns
    -------
    new_name : str
        converted string.
    """
    # replace white space and special characters with underscore
    # \W is equivalent to [^a-zA-Z0-9_]
    new_name = name.replace(' ', '_')

    # prepend ems_ in case the name starts with a number
    new_name = 'ems_' + new_name

    return new_name

def add_zone_heat_cool_request_count_program(openstudio_model: osmod, thermal_zones: list[osmod.ThermalZone]):
    """
    - Helper method to find out which climate zone set contains a specific climate zone. Returns climate zone set name as String if success, nil if not found
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_zone_heat_cool_request_count_program

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    thermal_zones : list[osmod.ThermalZone]
        array of zones.
    
    """
    # create container schedules to hold number of zones needing heating and cooling
    sch_zones_needing_heating = add_constant_schedule_ruleset(openstudio_model, 0, name = 'Zones Needing Heating Count Schedule', 
                                                              sch_type_limit = 'Dimensionless')

    zone_needing_heating_actuator = osmod.EnergyManagementSystemActuator(sch_zones_needing_heating, 'Schedule:Year', 'Schedule Value')
    zone_needing_heating_actuator.setName('Zones_Needing_Heating')

    sch_zones_needing_cooling = add_constant_schedule_ruleset(openstudio_model, 0, name = 'Zones Needing Cooling Count Schedule',
                                                              sch_type_limit = 'Dimensionless')

    zone_needing_cooling_actuator = osmod.EnergyManagementSystemActuator(sch_zones_needing_cooling, 'Schedule:Year', 'Schedule Value')
    zone_needing_cooling_actuator.setName('Zones_Needing_Cooling')

    # create container schedules to hold ratio of zones needing heating and cooling
    sch_zones_needing_heating_ratio = add_constant_schedule_ruleset(openstudio_model, 0, name = 'Zones Needing Heating Ratio Schedule',
                                                                    sch_type_limit = 'Dimensionless')

    zone_needing_heating_ratio_actuator = osmod.EnergyManagementSystemActuator(sch_zones_needing_heating_ratio,'Schedule:Year',
                                                                               'Schedule Value')
    zone_needing_heating_ratio_actuator.setName('Zone_Heating_Ratio')

    sch_zones_needing_cooling_ratio = add_constant_schedule_ruleset(openstudio_model, 0, name = 'Zones Needing Cooling Ratio Schedule',
                                                                    sch_type_limit = 'Dimensionless')

    zone_needing_cooling_ratio_actuator = osmod.EnergyManagementSystemActuator(sch_zones_needing_cooling_ratio, 'Schedule:Year', 'Schedule Value')
    zone_needing_cooling_ratio_actuator.setName('Zone_Cooling_Ratio')

    #####
    # Create EMS program to check comfort exceedances
    ####

    # initalize inner body for heating and cooling requests programs
    determine_zone_cooling_needs_prg_inner_body = ''
    determine_zone_heating_needs_prg_inner_body = ''
    for zone in thermal_zones:
        # get existing 'sensors'
        exisiting_ems_sensors = openstudio_model.getEnergyManagementSystemSensors()
        exisiting_ems_sensors_names = []
        for sensor in exisiting_ems_sensors:
            sensor_name = sensor.name().get() + '-' + sensor.outputVariableOrMeterName()
            exisiting_ems_sensors_names.append(sensor_name)    
        # exisiting_ems_sensors_names = exisiting_ems_sensors.collect { |sensor| sensor.name.get + '-' + sensor.outputVariableOrMeterName }

        # Create zone air temperature 'sensor' for the zone.
        zone_name = ems_friendly_name(zone.name())
        zone_air_sensor_name = f"{zone_name}_ctrl_temperature"

        if zone_air_sensor_name + '-Zone Air Temperature' not in exisiting_ems_sensors_names:
            # unless exisiting_ems_sensors_names.include? zone_air_sensor_name + '-Zone Air Temperature'
            zone_ctrl_temperature = osmod.EnergyManagementSystemSensor(openstudio_model, 'Zone Air Temperature')
            zone_ctrl_temperature.setName(zone_air_sensor_name)
            zone_ctrl_temperature.setKeyName(zone.name().get())

        # check for zone thermostats
        zone_thermostat = zone.thermostatSetpointDualSetpoint()
        if zone_thermostat.is_initialized() == False:
            print('openstudio.model.Model', f"Zone #{zone.name()} does not have thermostats.")
            return False

        zone_thermostat = zone.thermostatSetpointDualSetpoint().get()
        zone_clg_thermostat = zone_thermostat.coolingSetpointTemperatureSchedule().get()
        zone_htg_thermostat = zone_thermostat.heatingSetpointTemperatureSchedule().get()

        # create new sensor for zone thermostat if it does not exist already
        zone_clg_thermostat_sensor_name = f"{zone_name}_upper_comfort_limit"
        zone_htg_thermostat_sensor_name = f"{zone_name}_lower_comfort_limit"

        if zone_clg_thermostat_sensor_name + '-Schedule Value' not in exisiting_ems_sensors_names:
            # unless exisiting_ems_sensors_names.include? zone_clg_thermostat_sensor_name + '-Schedule Value'
            # Upper comfort limit for the zone. Taken from existing thermostat schedules in the zone.
            zone_upper_comfort_limit = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
            zone_upper_comfort_limit.setName(zone_clg_thermostat_sensor_name)
            zone_upper_comfort_limit.setKeyName(zone_clg_thermostat.name().get())

        if zone_htg_thermostat_sensor_name + '-Schedule Value' not in exisiting_ems_sensors_names:
            # unless exisiting_ems_sensors_names.include? zone_htg_thermostat_sensor_name + '-Schedule Value'
            # Lower comfort limit for the zone. Taken from existing thermostat schedules in the zone.
            zone_lower_comfort_limit = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
            zone_lower_comfort_limit.setName(zone_htg_thermostat_sensor_name)
            zone_lower_comfort_limit.setKeyName(zone_htg_thermostat.name().get())

        # create program inner body for determining zone cooling needs
        determine_zone_cooling_needs_prg_inner_body += f"IF {zone_air_sensor_name} > {zone_clg_thermostat_sensor_name},\
                                                        SET Zones_Needing_Cooling = Zones_Needing_Cooling + 1,\
                                                        ENDIF,\n"

        # create program inner body for determining zone cooling needs
        determine_zone_heating_needs_prg_inner_body += f"IF {zone_air_sensor_name} < {zone_htg_thermostat_sensor_name},\
                                                        SET Zones_Needing_Heating = Zones_Needing_Heating + 1,\
                                                        ENDIF,\n"

    # create program for determining zone cooling needs
    determine_zone_cooling_needs_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    determine_zone_cooling_needs_prg.setName('Determine_Zone_Cooling_Needs')
    determine_zone_cooling_needs_prg_body = f"SET Zones_Needing_Cooling = 0,\
        {determine_zone_cooling_needs_prg_inner_body}\
        SET Total_Zones = {len(thermal_zones)},\
        SET Zone_Cooling_Ratio = Zones_Needing_Cooling/Total_Zones"
    
    determine_zone_cooling_needs_prg.setBody(determine_zone_cooling_needs_prg_body)

    # create program for determining zone heating needs
    determine_zone_heating_needs_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    determine_zone_heating_needs_prg.setName('Determine_Zone_Heating_Needs')
    determine_zone_heating_needs_prg_body = f"SET Zones_Needing_Heating = 0,\
        {determine_zone_heating_needs_prg_inner_body}\
        SET Total_Zones = {len(thermal_zones)},\
        SET Zone_Heating_Ratio = Zones_Needing_Heating/Total_Zones"
    determine_zone_heating_needs_prg.setBody(determine_zone_heating_needs_prg_body)

    # create EMS program manager objects
    programs_at_beginning_of_timestep = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
    programs_at_beginning_of_timestep.setName('Heating_Cooling_Request_Programs_At_End_Of_Timestep')
    programs_at_beginning_of_timestep.setCallingPoint('EndOfZoneTimestepAfterZoneReporting')
    programs_at_beginning_of_timestep.addProgram(determine_zone_cooling_needs_prg)
    programs_at_beginning_of_timestep.addProgram(determine_zone_heating_needs_prg)

def model_two_pipe_loop(openstudio_model: osmod, hot_water_loop: osmod.PlantLoop, chilled_water_loop: osmod.PlantLoop, 
                        control_strategy: str = 'outdoor_air_lockout', lockout_temperature: float = 18.3,
                        thermal_zones: list[osmod.ThermalZone] = []) -> osmod.ScheduleRuleset:
    """
    - Model a 2-pipe plant loop, where the loop is either in heating or cooling. For sizing reasons, this method keeps separate hot water and chilled water loops, and connects them together with a common inverse schedule.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_two_pipe_loop

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    hot_water_loop : osmod.PlantLoop
        the hot water loop
    
    chilled_water_loop : osmod.PlantLoop
        the chilled water loop
    
    control_strategy : str, optional
        - Method to determine whether the loop is in heating or cooling mode 'outdoor_air_lockout' 
        - The system will be in heating below the lockout_temperature variable, and cooling above the lockout_temperature. 
        - Requires the lockout_temperature variable.
        - 'zone_demand' - Heating or cooling determined by preponderance of zone demand. Requires thermal_zones defined.
    
    lockout_temperature : float, optional
        lockout temperature in degreesC, default 18.3C.
    
    thermal_zones : list[osmod.ThermalZone]
        array of zones.

    Returns
    -------
    loop_schedule : osmod.ScheduleRuleset
        resultant loop schedule.
    """

    if control_strategy == 'outdoor_air_lockout':
        # get or create outdoor sensor node to be used in plant availability managers if needed
        outdoor_airnode = openstudio_model.outdoorAirNode()

        # create availability managers based on outdoor temperature
        # create hot water plant availability manager
        hot_water_loop_lockout_manager = osmod.AvailabilityManagerHighTemperatureTurnOff(openstudio_model)
        hot_water_loop_lockout_manager.setName(f"{hot_water_loop.name()} Lockout Manager")
        hot_water_loop_lockout_manager.setSensorNode(outdoor_airnode)
        hot_water_loop_lockout_manager.setTemperature(lockout_temperature)

        # set availability manager to hot water plant
        hot_water_loop.addAvailabilityManager(hot_water_loop_lockout_manager)

        # create chilled water plant availability manager
        chilled_water_loop_lockout_manager = osmod.AvailabilityManagerLowTemperatureTurnOff(openstudio_model)
        chilled_water_loop_lockout_manager.setName(f"{chilled_water_loop.name} Lockout Manager")
        chilled_water_loop_lockout_manager.setSensorNode(outdoor_airnode)
        chilled_water_loop_lockout_manager.setTemperature(lockout_temperature)

        # set availability manager to hot water plant
        chilled_water_loop.addAvailabilityManager(chilled_water_loop_lockout_manager)
    else:
        # create availability managers based on zone heating and cooling demand
        hot_water_loop_name = hot_water_loop.name()
        chilled_water_loop_name = chilled_water_loop.name()

        # create hot water plant availability schedule managers and create an EMS acuator
        sch_hot_water_availability = add_constant_schedule_ruleset(openstudio_model, 0, 
                                                                   name = f"{hot_water_loop.name()} Availability Schedule", 
                                                                   sch_type_limit = 'OnOff')

        hot_water_loop_manager = osmod.AvailabilityManagerScheduled(openstudio_model)
        hot_water_loop_manager.setName(f"{hot_water_loop.name()} Availability Manager")
        hot_water_loop_manager.setSchedule(sch_hot_water_availability)

        hot_water_plant_ctrl = osmod.EnergyManagementSystemActuator(sch_hot_water_availability, 'Schedule:Year', 'Schedule Value')
        hot_water_plant_ctrl.setName(f"{hot_water_loop_name}_availability_control")

        # set availability manager to hot water plant
        hot_water_loop.addAvailabilityManager(hot_water_loop_manager)

        # create chilled water plant availability schedule managers and create an EMS acuator
        sch_chilled_water_availability = add_constant_schedule_ruleset(openstudio_model, 0, name = f"#{chilled_water_loop.name()} Availability Schedule", 
                                                                       sch_type_limit = 'OnOff')

        chilled_water_loop_manager = osmod.AvailabilityManagerScheduled(openstudio_model)
        chilled_water_loop_manager.setName(f"{chilled_water_loop.name()} Availability Manager")
        chilled_water_loop_manager.setSchedule(sch_chilled_water_availability)

        chilled_water_plant_ctrl = osmod.EnergyManagementSystemActuator(sch_chilled_water_availability, 'Schedule:Year', 'Schedule Value')
        chilled_water_plant_ctrl.setName(f"{chilled_water_loop_name}_availability_control")

        # set availability manager to chilled water plant
        chilled_water_loop.addAvailabilityManager(chilled_water_loop_manager)

        # check if zone heat and cool requests program exists, if not create it
        determine_zone_cooling_needs_prg = openstudio_model.getEnergyManagementSystemProgramByName('Determine_Zone_Cooling_Needs')
        determine_zone_heating_needs_prg = openstudio_model.getEnergyManagementSystemProgramByName('Determine_Zone_Heating_Needs')

        if determine_zone_cooling_needs_prg.is_initialized() == False and determine_zone_heating_needs_prg.is_initialized() == False:
            add_zone_heat_cool_request_count_program(openstudio_model, thermal_zones)

        # create program to determine plant heating or cooling mode
        determine_plant_mode_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
        determine_plant_mode_prg.setName('Determine_Heating_Cooling_Plant_Mode')
        determine_plant_mode_prg_body = f"IF Zone_Heating_Ratio > 0.5,\
            SET {hot_water_loop_name}_availability_control = 1,\
            SET {chilled_water_loop_name}_availability_control = 0,\
            ELSEIF Zone_Cooling_Ratio > 0.5,\
                SET {hot_water_loop_name}_availability_control = 0,\
                SET {chilled_water_loop_name}_availability_control = 1,\
                ELSE,\
                    SET {hot_water_loop_name}_availability_control = #{hot_water_loop_name}_availability_control,\
                    SET {chilled_water_loop_name}_availability_control = #{chilled_water_loop_name}_availability_control,\
                    ENDIF"
        
        determine_plant_mode_prg.setBody(determine_plant_mode_prg_body)

        # create EMS program manager objects
        programs_at_beginning_of_timestep = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
        programs_at_beginning_of_timestep.setName('Heating_Cooling_Demand_Based_Plant_Availability_At_Beginning_Of_Timestep')
        programs_at_beginning_of_timestep.setCallingPoint('BeginTimestepBeforePredictor')
        programs_at_beginning_of_timestep.addProgram(determine_plant_mode_prg)

def add_plant_supply_water_temperature_control(openstudio_model: osmod, plant_water_loop: osmod.PlantLoop, control_strategy: str = 'outdoor_air',
                                               sp_at_oat_low: float = None, oat_low: float = None, sp_at_oat_high: float = None, 
                                               oat_high: float = None, thermal_zones: list[osmod.ThermalZone] = []):
    """
    - Adds supply water temperature control on specified plant water loops.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_plant_supply_water_temperature_control

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    plant_water_loop : osmod.PlantLoop
        plant water loop to add supply water temperature control.
    
    control_strategy : str, optional
        - Method to determine how to control the plant's supply water temperature (swt). 
        - 'outdoor_air' (default) - The plant's swt will be proportional to the outdoor air based on the next 4 parameters. 
        - 'zone_demand' - The plant's swt will be determined by preponderance of zone demand.
        - Requires thermal_zone defined.
    
    sp_at_oat_low : float, optional
        supply water temperature setpoint, in C, at the outdoor low temperature.
    
    oat_low : float, optional
        outdoor drybulb air temperature, in C, for low setpoint.
    
    sp_at_oat_high : float, optional
        supply water temperature setpoint, in C, at the outdoor high temperature.
    
    oat_high : float, optional
        outdoor drybulb air temperature, in C, for high setpoint.

    thermal_zones : list[osmod.ThermalZone]
        array of zones.

    """
    # check that all required temperature parameters are defined
    if sp_at_oat_low == None and oat_low == None and sp_at_oat_high == None and oat_high == None:
        print('openstudio.model.Model', 'At least one of the required temperature parameter is nil.')

    # remove any existing setpoint manager on the plant water loop
    exisiting_setpoint_managers = plant_water_loop.loopTemperatureSetpointNode().setpointManagers()
    for esm in exisiting_setpoint_managers:
        esm.disconnect()

    if control_strategy == 'outdoor_air':
        # create supply water temperature setpoint managers for plant based on outdoor temperature
        water_loop_setpoint_manager = osmod.SetpointManagerOutdoorAirReset(openstudio_model)
        water_loop_setpoint_manager.setName(f"{plant_water_loop.name().get()} Supply Water Temperature Control")
        water_loop_setpoint_manager.setControlVariable('Temperature')
        water_loop_setpoint_manager.setSetpointatOutdoorLowTemperature(sp_at_oat_low)
        water_loop_setpoint_manager.setOutdoorLowTemperature(oat_low)
        water_loop_setpoint_manager.setSetpointatOutdoorHighTemperature(sp_at_oat_high)
        water_loop_setpoint_manager.setOutdoorHighTemperature(oat_high)
        water_loop_setpoint_manager.addToNode(plant_water_loop.loopTemperatureSetpointNode())
    else:
        # create supply water temperature setpoint managers for plant based on zone heating and cooling demand
        # check if zone heat and cool requests program exists, if not create it
        determine_zone_cooling_needs_prg = openstudio_model.getEnergyManagementSystemProgramByName('Determine_Zone_Cooling_Needs')
        determine_zone_heating_needs_prg = openstudio_model.getEnergyManagementSystemProgramByName('Determine_Zone_Heating_Needs')
        if determine_zone_cooling_needs_prg.is_initialized() == False and determine_zone_heating_needs_prg.is_initialized() == False:
            add_zone_heat_cool_request_count_program(openstudio_model, thermal_zones)
        

        plant_water_loop_name = ems_friendly_name(plant_water_loop.name())

        if plant_water_loop.componentType().valueName() == 'Heating':
            if sp_at_oat_low == None:
                swt_upper_limit = 48.9
            else:
                swt_upper_limit = sp_at_oat_low
            
            if sp_at_oat_high == None:
                swt_lower_limit = 26.7
            else:
                swt_lower_limit = sp_at_oat_high
            
            swt_init = 37.8
            zone_demand_var = 'Zone_Heating_Ratio'
            swt_inc_condition_var = '> 0.70'
            swt_dec_condition_var = '< 0.30'
        else:
            if sp_at_oat_low == None:
                swt_upper_limit = 21.1
            else:
                swt_upper_limit = sp_at_oat_low
            
            if sp_at_oat_high == None:
                swt_lower_limit = 128
            else:
                swt_lower_limit = sp_at_oat_high

            swt_init = 16.7
            zone_demand_var = 'Zone_Cooling_Ratio'
            swt_inc_condition_var = '< 0.30'
            swt_dec_condition_var = '> 0.70'

        # plant loop supply water control actuator
        sch_plant_swt_ctrl = add_constant_schedule_ruleset(openstudio_model, swt_init,
                                                           name = f"{plant_water_loop_name}_Sch_Supply_Water_Temperature")

        cmd_plant_water_ctrl = osmod.EnergyManagementSystemActuator(sch_plant_swt_ctrl, 'Schedule:Year', 'Schedule Value')
        cmd_plant_water_ctrl.setName(f"{plant_water_loop_name}_supply_water_ctrl")

        # create plant loop setpoint manager
        water_loop_setpoint_manager = osmod.SetpointManagerScheduled.new(openstudio_model, sch_plant_swt_ctrl)
        water_loop_setpoint_manager.setName(f"{plant_water_loop.name().get()} Supply Water Temperature Control")
        water_loop_setpoint_manager.setControlVariable('Temperature')
        water_loop_setpoint_manager.addToNode(plant_water_loop.loopTemperatureSetpointNode())

        # add uninitialized variables into constant program
        set_constant_values_prg_body = f"SET {plant_water_loop_name}_supply_water_ctrl = {swt_init}"
        
        set_constant_values_prg = openstudio_model.getEnergyManagementSystemProgramByName('Set_Plant_Constant_Values')
        if set_constant_values_prg.is_initialized():
            set_constant_values_prg = set_constant_values_prg.get()
            set_constant_values_prg.addLine(set_constant_values_prg_body)
        else:
            set_constant_values_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
            set_constant_values_prg.setName('Set_Plant_Constant_Values')
            set_constant_values_prg.setBody(set_constant_values_prg_body)
        
        # program for supply water temperature control in the plot
        determine_plant_swt_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
        determine_plant_swt_prg.setName(f"Determine_{plant_water_loop_name}_Supply_Water_Temperature")
        determine_plant_swt_prg_body = f"SET SWT_Increase = 1,\
            SET SWT_Decrease = 1,\
            SET SWT_upper_limit = {swt_upper_limit},\
            SET SWT_lower_limit = {swt_lower_limit},\
            IF {zone_demand_var} {swt_inc_condition_var} && (@Mod CurrentTime 1) == 0,\
            SET {plant_water_loop_name}_supply_water_ctrl = {plant_water_loop_name}_supply_water_ctrl + SWT_Increase,\
            ELSEIF {zone_demand_var} {swt_dec_condition_var} && (@Mod CurrentTime 1) == 0,\
            SET {plant_water_loop_name}_supply_water_ctrl = {plant_water_loop_name}_supply_water_ctrl - SWT_Decrease,\
            ELSE,\
            SET {plant_water_loop_name}_supply_water_ctrl = {plant_water_loop_name}_supply_water_ctrl,\
            ENDIF,\
            IF {plant_water_loop_name}_supply_water_ctrl > SWT_upper_limit,\
            SET {plant_water_loop_name}_supply_water_ctrl = SWT_upper_limit\
            ENDIF,\
            IF {plant_water_loop_name}_supply_water_ctrl < SWT_lower_limit,\
            SET {plant_water_loop_name}_supply_water_ctrl = SWT_lower_limit\
            ENDIF"
        
        determine_plant_swt_prg.setBody(determine_plant_swt_prg_body)

        # create EMS program manager objects
        programs_at_beginning_of_timestep = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
        programs_at_beginning_of_timestep.setName(f"{plant_water_loop_name}_Demand_Based_Supply_Water_Temperature_At_Beginning_Of_Timestep")
        programs_at_beginning_of_timestep.setCallingPoint('BeginTimestepBeforePredictor')
        programs_at_beginning_of_timestep.addProgram(determine_plant_swt_prg)

        initialize_constant_parameters = openstudio_model.getEnergyManagementSystemProgramCallingManagerByName('Initialize_Constant_Parameters')
        if initialize_constant_parameters.is_initialized():
            initialize_constant_parameters = initialize_constant_parameters.get()
            # add program if it does not exist in manager
            programs = initialize_constant_parameters.programs()
            existing_program_names = []
            for prg in programs:
                prg_name = prg.name().get().lower()
                existing_program_names.append(prg_name)

            if set_constant_values_prg.name().get().lower() not in existing_program_names:
                initialize_constant_parameters.addProgram(set_constant_values_prg)
        else:
            initialize_constant_parameters = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
            initialize_constant_parameters.setName('Initialize_Constant_Parameters')
            initialize_constant_parameters.setCallingPoint('BeginNewEnvironment')
            initialize_constant_parameters.addProgram(set_constant_values_prg)
        
        initialize_constant_parameters_after_warmup = openstudio_model.getEnergyManagementSystemProgramCallingManagerByName('Initialize_Constant_Parameters_After_Warmup')
        if initialize_constant_parameters_after_warmup.is_initialized():
            initialize_constant_parameters_after_warmup = initialize_constant_parameters_after_warmup.get()
            # add program if it does not exist in manager
            programs = initialize_constant_parameters_after_warmup.programs()
            existing_program_names = []
            for prg in programs:
                prg_name = prg.name().get().lower()
                existing_program_names.append(prg_name)
            if set_constant_values_prg.name().get().lower() not in existing_program_names:
                initialize_constant_parameters_after_warmup.addProgram(set_constant_values_prg)
        else:
            initialize_constant_parameters_after_warmup = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
            initialize_constant_parameters_after_warmup.setName('Initialize_Constant_Parameters_After_Warmup')
            initialize_constant_parameters_after_warmup.setCallingPoint('AfterNewEnvironmentWarmUpIsComplete')
            initialize_constant_parameters_after_warmup.addProgram(set_constant_values_prg)

def rename_plant_loop_nodes(openstudio_model: osmod) -> osmod:
    """
    - renames plant loop nodes to readable values
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:rename_plant_loop_nodes

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.

    Returns
    -------
    returned_model : osmod
        model with rename nodes.

    """
    # rename all hvac components on plant loops
    for component in openstudio_model.getHVACComponents():
        if component.to_Node().is_initialized(): # skip nodes
            continue

        if component.plantLoop().empty() == False:
            # rename straight component nodes
            # some inlet or outlet nodes may get renamed again
            if component.to_StraightComponent().is_initialized():
                if component.to_StraightComponent().get().inletModelObject().empty() == False:
                    component_inlet_object = component.to_StraightComponent().get().inletModelObject().get()
                    if component_inlet_object.to_Node().is_initialized() == False:
                        continue

                    component_inlet_object.setName(f"{component.name()} Inlet Water Node")
                
                if component.to_StraightComponent().get().outletModelObject().empty() == False:
                    component_outlet_object = component.to_StraightComponent().get().outletModelObject().get()
                    if component_outlet_object.to_Node().is_initialized() == False:
                        continue
                    component_outlet_object.setName(f"{component.name()} Outlet Water Node")

        # rename water to air component nodes
        if component.to_WaterToAirComponent().is_initialized():
            component = component.to_WaterToAirComponent().get()
            if component.waterInletModelObject().empty() == False:
                component_inlet_object = component.waterInletModelObject().get()
                if component_inlet_object.to_Node().is_initialized() == False:
                    continue

                component_inlet_object.setName(f"{component.name()} Inlet Water Node")
            if component.waterOutletModelObject().empty() == False:
                component_outlet_object = component.waterOutletModelObject().get()
                if component_outlet_object.to_Node().is_initialized() == False:
                    continue
                component_outlet_object.setName(f"{component.name()} Outlet Water Node")

        # rename water to water component nodes
        if component.to_WaterToWaterComponent().is_initialized():
            component = component.to_WaterToWaterComponent().get()
            if component.demandInletModelObject().empty() == False:
                demand_inlet_object = component.demandInletModelObject().get()
                if demand_inlet_object.to_Node().is_initialized() == False:
                    continue
                demand_inlet_object.setName(f"{component.name()} Demand Inlet Water Node")
            if component.demandOutletModelObject().empty() == False:
                demand_outlet_object = component.demandOutletModelObject().get()
                if demand_outlet_object.to_Node().is_initialized() == False:
                    continue
                demand_outlet_object.setName(f"{component.name()} Demand Outlet Water Node")
            
            if component.supplyInletModelObject().empty() == False:
                supply_inlet_object = component.supplyInletModelObject().get()
                if supply_inlet_object.to_Node().is_initialized() == False:
                    continue
                supply_inlet_object.setName(f"{component.name()} Supply Inlet Water Node")
            
            if component.supplyOutletModelObject().empty() == False:
                supply_outlet_object = component.supplyOutletModelObject().get()
                if supply_outlet_object.to_Node().is_initialized() == False:
                    continue
                supply_outlet_object.setName(f"{component.name()} Supply Outlet Water Node")

    # rename plant nodes
    plps = openstudio_model.getPlantLoops()
    for plant_loop in plps:
        plant_loop_name = str(plant_loop.name())
        plant_loop.demandInletNode().setName(f"{plant_loop_name} Demand Inlet Node")
        plant_loop.demandOutletNode().setName(f"{plant_loop_name} Demand Outlet Node")
        plant_loop.supplyInletNode().setName(f"{plant_loop_name} Supply Inlet Node")
        plant_loop.supplyOutletNode().setName(f"{plant_loop_name} Supply Outlet Node")

    return openstudio_model

def schedule_ruleset_annual_min_max_value(schedule_ruleset: osmod.ScheduleRuleset) -> dict:
    """
    - Returns the min and max value for this schedule. It doesn't evaluate design days only run-period conditions
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:schedule_ruleset_annual_min_max_value

    Parameters
    ----------
    schedule_ruleset : osmod.ScheduleRuleset
        schedule ruleset object.

    Returns
    -------
    dict
        two keys, min and max.

    """
    # gather profiles
    profiles = []
    profiles.append(schedule_ruleset.defaultDaySchedule())
    rules = schedule_ruleset.scheduleRules()
    for rule in rules:
        profiles.append(rule.daySchedule())

    # test profiles
    min = None
    max = None
    for profile in profiles:
        for value in profile.values():
            if min == None:
                min = value
            else:
                if min > value:
                    min = value 
            if max == None:
                max = value
            else:
                if max < value:
                    max = value

    result = { 'min': min, 'max': max }

    return result

def spaces_get_occupancy_schedule(spaces: list[osmod.Space], sch_name: str = None, occupied_percentage_threshold: float = None, threshold_calc_method: str = 'value') -> osmod.ScheduleRuleset:
    """
    - This method creates a new fractional schedule ruleset. If occupied_percentage_threshold is set, this method will return a discrete on/off fractional 
    - schedule with a value of one when occupancy across all spaces is greater than or equal to the occupied_percentage_threshold, and zero all other times. 
    - Otherwise the method will return the weighted fractional occupancy schedule.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:spaces_get_occupancy_schedule

    Parameters
    ----------
    spaces : list[osmod.Space]
        openstudio.

    sch_name : str, optional
        openstudio.
    
    occupied_percentage_threshold : float, optional
        openstudio.

    threshold_calc_method : str, optional
        openstudio.

    Returns
    -------
    osmod.ScheduleRuleset
        a ScheduleRuleset of fractional or discrete occupancy.

    """
    if len(spaces) == 0:
        print('openstudio.Standards.ThermalZone', 'Empty spaces array passed to spaces_get_occupancy_schedule method.')
        return False

    annual_normalized_tol = None
    if threshold_calc_method == 'normalized_annual_range':
        # run this method without threshold to get annual min and max
        temp_merged = spaces_get_occupancy_schedule(spaces)
        tem_min_max = schedule_ruleset_annual_min_max_value(temp_merged)
        annual_normalized_tol = tem_min_max['min'] + (tem_min_max['max'] - tem_min_max['min']) * occupied_percentage_threshold
        temp_merged.remove()

    # Get all the occupancy schedules in spaces.
    # Include people added via the SpaceType and hard-assigned to the Space itself.
    occ_schedules_num_occ = {}
    max_occ_in_spaces = 0
    for space in spaces:
        # From the space type
        if space.spaceType().is_initialized():
            peoples = space.spaceType().get().people()
            for people in peoples:
                num_ppl_sch = people.numberofPeopleSchedule()
                if num_ppl_sch.is_initialized():
                    num_ppl_sch = num_ppl_sch.get()
                    num_ppl_sch = num_ppl_sch.to_ScheduleRuleset()
                    if num_ppl_sch.empty(): # Skip non-ruleset schedules
                        continue
                    num_ppl_sch = num_ppl_sch.get()
                    num_ppl = people.getNumberOfPeople(space.floorArea())
                    if num_ppl_sch not in occ_schedules_num_occ.keys():
                        occ_schedules_num_occ[num_ppl_sch] = num_ppl
                    else:
                        occ_schedules_num_occ[num_ppl_sch] += num_ppl

                    max_occ_in_spaces += num_ppl
        # From the space
        for people in space.people():
            num_ppl_sch = people.numberofPeopleSchedule()
            if num_ppl_sch.is_initialized():
                num_ppl_sch = num_ppl_sch.get()
                num_ppl_sch = num_ppl_sch.to_ScheduleRuleset()
                if num_ppl_sch.empty(): # Skip non-ruleset schedules
                    continue
                num_ppl_sch = num_ppl_sch.get()
                num_ppl = people.getNumberOfPeople(space.floorArea())
                if num_ppl_sch not in occ_schedules_num_occ.keys():
                    occ_schedules_num_occ[num_ppl_sch] = num_ppl
                else:
                    occ_schedules_num_occ[num_ppl_sch] += num_ppl
                max_occ_in_spaces += num_ppl

    # Store arrays of 365 day schedules used by each occ schedule once for later
    # Store arrays of day schedule times for later
    occ_schedules_day_schedules = {}
    day_schedule_times = {}
    year = spaces[0].model().getYearDescription()
    first_date_of_year = year.makeDate(1)
    end_date_of_year = year.makeDate(365)
    for occ_sch in occ_schedules_num_occ:
        # Store array of day schedules
        day_schedules = occ_sch.getDaySchedules(first_date_of_year, end_date_of_year)
        occ_schedules_day_schedules[occ_sch] = day_schedules
        for day_sch in day_schedules:
            # Skip schedules that have been stored previously
            if day_sch in day_schedule_times.keys():
                continue
            # Store times
            times = []
            for time in day_sch.times():
                times.append(time.toString())
            
            day_schedule_times[day_sch] = times

    # For each day of the year, determine time_value_pairs = []
    yearly_data = []
    for i in range(365):
        i +=1
        times_on_this_day = []
        os_date = year.makeDate(i)
        day_of_week = os_date.dayOfWeek().valueName()

        # Get the unique time indices and corresponding day schedules
        day_sch_num_occ = {}
        for occ_sch, num_occ in occ_schedules_num_occ.items():
            daily_sch = occ_schedules_day_schedules[occ_sch][i - 1]
            times_on_this_day.extend(day_schedule_times[daily_sch])
            day_sch_num_occ[daily_sch] = num_occ
        
        daily_normalized_tol = None
        if threshold_calc_method == 'normalized_daily_range':
            # pre-process day to get daily min and max
            daily_spaces_occ_frac = []
            for timex in times_on_this_day:
                os_time = openstudio.Time(timex)
                # Total number of people at each time
                tot_occ_at_time = 0
                for day_sch, num_occ in day_sch_num_occ.items():
                    occ_frac = day_sch.getValue(os_time)
                    tot_occ_at_time += occ_frac * num_occ
                # Total fraction for the spaces at each time
                daily_spaces_occ_frac.append(tot_occ_at_time / max_occ_in_spaces)
                daily_normalized_tol = min(daily_spaces_occ_frac) + (max(daily_spaces_occ_frac) - min(daily_spaces_occ_frac)) * occupied_percentage_threshold

        # Determine the total fraction for the spaces at each time
        daily_times = []
        daily_os_times = []
        daily_values = []
        daily_occs = []
        for timex in times_on_this_day:
            os_time = openstudio.Time(timex)
            # Total number of people at each time
            tot_occ_at_time = 0
            for day_sch, num_occ in day_sch_num_occ.items():
                occ_frac = day_sch.getValue(os_time)
                tot_occ_at_time += occ_frac * num_occ

        # Total fraction for the spaces at each time,
        # rounded to avoid decimal precision issues
        spaces_occ_frac = round((tot_occ_at_time / max_occ_in_spaces), 3)

        # If occupied_percentage_threshold is specified, schedule values are boolean
        # Otherwise use the actual spaces_occ_frac
        if occupied_percentage_threshold == None:
            occ_status = spaces_occ_frac
        elif threshold_calc_method == 'normalized_annual_range':
            occ_status = 0 # unoccupied
            if spaces_occ_frac >= annual_normalized_tol:
                occ_status = 1
        elif threshold_calc_method == 'normalized_daily_range':
            occ_status = 0 # unoccupied
            if spaces_occ_frac > daily_normalized_tol:
                occ_status = 1
        else:
            occ_status = 0 # unoccupied
            if spaces_occ_frac >= occupied_percentage_threshold:
                occ_status = 1

        # Add this data to the daily arrays
        daily_times.append(time)
        daily_os_times.append(os_time)
        daily_values.append(occ_status)
        daily_occs.append(round(spaces_occ_frac, 2))

        # Simplify the daily times to eliminate intermediate points with the same value as the following point
        simple_daily_times = []
        simple_daily_os_times = []
        simple_daily_values = []
        simple_daily_occs = []
        for j, value in enumerate(daily_values):
            if value == daily_values[j + 1]:
                continue

            simple_daily_times.append(daily_times[j])
            simple_daily_os_times.append(daily_os_times[j])
            simple_daily_values.append(daily_values[j])
            simple_daily_occs.append(daily_occs[j])

        # Store the daily values
        yearly_data.append({'date': os_date, 'day_of_week': day_of_week, 'times': simple_daily_times, 'values': simple_daily_values, 'daily_os_times' : simple_daily_os_times, 
                            'daily_occs': simple_daily_occs })

    # Create a TimeSeries from the data
    # time_series = OpenStudio::TimeSeries.new(times, values, 'unitless')
    # Make a schedule ruleset
    if sch_name == None:
        sch_name = f"{len(spaces)} space(s) Occ Sch"

    sch_ruleset = osmod.ScheduleRuleset(spaces[0].model())
    sch_ruleset.setName(sch_name)
    # add properties to schedule
    props = sch_ruleset.additionalProperties()
    props.setFeature('max_occ_in_spaces', max_occ_in_spaces)
    props.setFeature('number_of_spaces_included', len(spaces))
    # nothing uses this but can make user be aware if this may be out of sync with current state of occupancy profiles
    props.setFeature('date_parent_object_last_edited', datetime.datetime.now(datetime.UTC).isoformat())
    props.setFeature('date_parent_object_created', datetime.datetime.now(datetime.UTC).isoformat())

    # Default - All Occupied
    day_sch = sch_ruleset.defaultDaySchedule()
    day_sch.setName(f"{sch_name} Default")
    day_sch.addValue(openstudio.Time(0, 24, 0, 0), 1)

    # Winter Design Day - All Occupied
    day_sch = osmod.ScheduleDay(spaces[0].model())
    sch_ruleset.setWinterDesignDaySchedule(day_sch)
    day_sch = sch_ruleset.winterDesignDaySchedule()
    day_sch.setName(f"{sch_name} Winter Design Day")
    day_sch.addValue(openstudio.Time(0, 24, 0, 0), 1)

    # Summer Design Day - All Occupied
    day_sch = osmod.ScheduleDay(spaces[0].model())
    sch_ruleset.setSummerDesignDaySchedule(day_sch)
    day_sch = sch_ruleset.summerDesignDaySchedule()
    day_sch.setName(f"{sch_name} Summer Design Day")
    day_sch.addValue(openstudio.Time(0, 24, 0, 0), 1)

    # Create ruleset schedules, attempting to create the minimum number of unique rules
    for weekday in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        end_of_prev_rule = yearly_data[0]['date']
        for k, daily_data in enumerate(yearly_data):
            # Skip unless it is the day of week
            # currently under inspection
            day = daily_data['day_of_week']
            if day != weekday:
                continue
            date = daily_data['date']
            times = daily_data['times']
            values = daily_data['values']
            daily_os_times = daily_data['daily_os_times']

            # If the next (Monday, Tuesday, etc.) is the same as today, keep going
            # If the next is different, or if we've reached the end of the year, create a new rule
            if k + 7 <= 364:
                next_day_times = yearly_data[k + 7]['times']
                next_day_values = yearly_data[k + 7]['values']
                if times == next_day_times and values == next_day_values:
                    continue

            # If here, we need to make a rule to cover from the previous rule to today
            print('openstudio.Standards.ThermalZone', f"Making a new rule for {weekday} from {end_of_prev_rule} to {date}")
            sch_rule = osmod.ScheduleRule(sch_ruleset)
            sch_rule.setName(f"{sch_name} {weekday} Rule")
            day_sch = sch_rule.daySchedule()
            day_sch.setName(f"{sch_name} {weekday}")
            for t, timex in enumerate(daily_os_times):
                value = values[t]
                if t < len(daily_os_times) - 1:
                    if value == values[t + 1]: # Don't add breaks if same value
                        continue
                day_sch.addValue(timex, value)

        # Set the dates when the rule applies
        sch_rule.setStartDate(end_of_prev_rule)
        # for end dates in last week of year force it to use 12/31. Avoids issues if year or start day of week changes
        start_of_last_week = openstudio.Date(openstudio.MonthOfYear('December'), 25, year.assumedYear())
        if date >= start_of_last_week:
            year_end_date = openstudio.Date(openstudio.MonthOfYear('December'), 31, year.assumedYear())
            sch_rule.setEndDate(year_end_date)
        else:
            sch_rule.setEndDate(date)

        # Individual Days
        if weekday == 'Monday': sch_rule.setApplyMonday(True)
        if weekday == 'Tuesday': sch_rule.setApplyTuesday(True)
        if weekday == 'Wednesday': sch_rule.setApplyWednesday(True)
        if weekday == 'Thursday': sch_rule.setApplyThursday(True)
        if weekday == 'Friday': sch_rule.setApplyFriday(True) 
        if weekday == 'Saturday': sch_rule.setApplySaturday(True) 
        if weekday == 'Sunday': sch_rule.setApplySunday(True) 

        # Reset the previous rule end date
        end_of_prev_rule = date + openstudio.Time(0, 24, 0, 0)

    # utilize default profile and common similar days of week for same date range
    # todo - if move to method in Standards.ScheduleRuleset.rb udpate code to check if default profile is used before replacing it with lowest priority rule.
    # todo - also merging non adjacent priority rules without getting rid of any rules between the two could create unexpected reults
    prior_rules = []
    for rule in sch_ruleset.scheduleRules():
        if len(prior_rules) == 0:
            prior_rules.append(rule)
            continue
        else:
            rules_combined = False
            for prior_rule in prior_rules:
                # see if they are similar
                if rules_combined:
                    continue
                # @todo update to combine adjacent date ranges vs. just matching date ranges
                if prior_rule.startDate().get() != rule.startDate().get():
                    continue
                if prior_rule.endDate().get() != rule.endDate().get():
                    continue
                if prior_rule.daySchedule().times() != rule.daySchedule().times():
                    continue
                if prior_rule.daySchedule().values() != rule.daySchedule().values():
                    continue
                # combine dates of week
                if rule.applyMonday():
                    prior_rule.setApplyMonday(True)
                    rules_combined = True
                if rule.applyTuesday():
                    prior_rule.setApplyTuesday(True) 
                    rules_combined = True
                if rule.applyWednesday(): 
                    prior_rule.setApplyWednesday(True) 
                    rules_combined = True
                if rule.applyThursday(): 
                    prior_rule.setApplyThursday(True)
                    rules_combined = True
                if rule.applyFriday(): 
                    prior_rule.setApplyFriday(True) 
                    rules_combined = True
                if rule.applySaturday(): 
                    prior_rule.setApplySaturday(True)  
                    rules_combined = True
                if rule.applySunday(): 
                    prior_rule.setApplySunday(True)  
                    rules_combined = True
            if rules_combined:
                rule.remove()
            else:
                prior_rules.append(rule)

    # replace unused default profile with lowest priority rule
    values = prior_rules[-1].daySchedule().values()
    times = prior_rules[-1].daySchedule().times()
    prior_rules[-1].remove()
    sch_ruleset.defaultDaySchedule().clearValues()
    for i in range(len(values)):
        sch_ruleset.defaultDaySchedule.addValue(times[i], values[i])

    return sch_ruleset

def thermal_zone_get_occupancy_schedule(thermal_zone: osmod.ThermalZone, sch_name: str = None, occupied_percentage_threshold: float = None) -> osmod.ScheduleRuleset:
    """
    - This method creates a new fractional schedule ruleset. If occupied_percentage_threshold is set, this method will return a discrete on/off fractional schedule with a value of one
    - when occupancy across all spaces is greater than or equal to the occupied_percentage_threshold, and zero all other times. 
    - Otherwise the method will return the weighted fractional occupancy schedule.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:thermal_zone_get_occupancy_schedule

    Parameters
    ----------
    thermal_zone : osmod.ThermalZone
        thermal zone.
    
    sch_name : str,  optional
         the name of the generated occupancy schedule.

    occupied_percentage_threshold : float, optional
        - the minimum fraction (0 to 1) that counts as occupied if this parameter is set, 
        - the returned ScheduleRuleset will be 0 = unoccupied, 1 = occupied otherwise the ScheduleRuleset will be the weighted fractional occupancy schedule.

    Returns
    -------
    new_schedule : osmod.ScheduleRuleset
        the created schedule.
    """    
    if sch_name == None:
        sch_name = f"{thermal_zone.name()} Occ Sch"

    # Get the occupancy schedule for all spaces in thermal_zone
    sch_ruleset = spaces_get_occupancy_schedule(thermal_zone.spaces, sch_name = sch_name, occupied_percentage_threshold = occupied_percentage_threshold)
    return sch_ruleset

def add_radiant_proportional_controls(openstudio_model: osmod, zone: osmod.ThermalZone, radiant_loop: osmod.ZoneHVACLowTempRadiantVarFlow, 
                                            radiant_temperature_control_type: str = 'SurfaceFaceTemperature', 
                                            use_zone_occupancy_for_control: bool = True, occupied_percentage_threshold: float = 0.10,
                                            model_occ_hr_start: float = 6.0, model_occ_hr_end: float = 18.0, proportional_gain: float = 0.3,
                                            switch_over_time: float = 24.0):
    
    """
    - These EnergyPlus objects implement a proportional control for a single thermal zone with a radiant system.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_radiant_proportional_controls

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    zone : osmod.ThermalZone
        zone to add radiant controls.

    radiant_loop : osmod.ZoneHVACLowTempRadiantVarFlow
        radiant loop in thermal zone

    radiant_temperature_control_type : str, optional
        - (defaults to: 'SurfaceFaceTemperature') — determines the controlled temperature for the radiant system options are
        - 'SurfaceFaceTemperature', 'SurfaceInteriorTemperature'

    use_zone_occupancy_for_control : bool, optional
        - Set to true if radiant system is to use specific zone occupancy objects for CBE control strategy. 
        - If false, then it will use values in model_occ_hr_start and model_occ_hr_end for all radiant zones. default to true.

    occupied_percentage_threshold : float, optional
        - (defaults to: 0.10) — the minimum fraction (0 to 1) that counts as occupied if this parameter is set, 
        - the returned ScheduleRuleset will be 0 = unoccupied, 1 = occupied otherwise the ScheduleRuleset will be the weighted fractional occupancy schedule

    model_occ_hr_start : float, optional
        Starting decimal hour of whole building occupancy

    model_occ_hr_end : float, optional
        Ending decimal hour of whole building occupancy

    proportional_gain : float, optional
        Proportional gain constant (recommended 0.3 or less).

    switch_over_time : float, optional
        Time limitation for when the system can switch between heating and cooling

    """
    zone_name = ems_friendly_name(zone.name())
    zone_timestep = openstudio_model.getTimestep().numberOfTimestepsPerHour()

    if openstudio_model.version() < openstudio.VersionString('3.1.1'):
        coil_cooling_radiant = radiant_loop.coolingCoil().to_CoilCoolingLowTempRadiantVarFlow().get()
        coil_heating_radiant = radiant_loop.heatingCoil().to_CoilHeatingLowTempRadiantVarFlow().get()
    else:
        coil_cooling_radiant = radiant_loop.coolingCoil().get().to_CoilCoolingLowTempRadiantVarFlow().get()
        coil_heating_radiant = radiant_loop.heatingCoil().get().to_CoilHeatingLowTempRadiantVarFlow().get()

    #####
    # Define radiant system parameters
    ####
    # set radiant system temperature and setpoint control type
    if radiant_temperature_control_type.lower() not in ['surfacefacetemperature', 'surfaceinteriortemperature']:
        print('openstudio.Model.Model',
              f"Control sequences not compatible with '{radiant_temperature_control_type}' radiant system control. Defaulting to 'SurfaceFaceTemperature'.")
        radiant_temperature_control_type = 'SurfaceFaceTemperature'

    radiant_loop.setTemperatureControlType(radiant_temperature_control_type)

    #####
    # List of schedule objects used to hold calculation results
    ####

    # get existing switchover time schedule or create one if needed
    sch_radiant_switchover = openstudio_model.getScheduleRulesetByName('Radiant System Switchover')
    if sch_radiant_switchover.is_initialized():
        sch_radiant_switchover = sch_radiant_switchover.get()
    else:
        sch_radiant_switchover = add_constant_schedule_ruleset(openstudio_model, switch_over_time, name = 'Radiant System Switchover', 
                                                               sch_type_limit = 'Dimensionless')

    # set radiant system switchover schedule
    radiant_loop.setChangeoverDelayTimePeriodSchedule(sch_radiant_switchover.to_Schedule().get())

    # Calculated active slab heating and cooling temperature setpoint.
    # radiant system cooling control actuator
    sch_radiant_clgsetp = add_constant_schedule_ruleset(openstudio_model, 26.0, name = f"{zone_name}_Sch_Radiant_ClgSetP")
    coil_cooling_radiant.setCoolingControlTemperatureSchedule(sch_radiant_clgsetp)
    cmd_cold_water_ctrl = osmod.EnergyManagementSystemActuator(sch_radiant_clgsetp, 'Schedule:Year', 'Schedule Value')
    cmd_cold_water_ctrl.setName(f"{zone_name}_cmd_cold_water_ctrl")

    # radiant system heating control actuator
    sch_radiant_htgsetp = add_constant_schedule_ruleset(openstudio_model, 20.0, name = f"{zone_name}_Sch_Radiant_HtgSetP")
    coil_heating_radiant.setHeatingControlTemperatureSchedule(sch_radiant_htgsetp)
    cmd_hot_water_ctrl = osmod.EnergyManagementSystemActuator(sch_radiant_htgsetp, 'Schedule:Year', 'Schedule Value')
    cmd_hot_water_ctrl.setName(f"{zone_name}_cmd_hot_water_ctrl")

    # Calculated cooling setpoint error. Calculated from upper comfort limit minus setpoint offset and 'measured' controlled zone temperature.
    sch_csp_error = add_constant_schedule_ruleset(openstudio_model, 0.0, name = f"{zone_name}_Sch_CSP_Error")
    cmd_csp_error = osmod.EnergyManagementSystemActuator(sch_csp_error, 'Schedule:Year', 'Schedule Value')
    cmd_csp_error.setName(f"{zone_name}_cmd_csp_error")

    # Calculated heating setpoint error. Calculated from lower comfort limit plus setpoint offset and 'measured' controlled zone temperature.
    sch_hsp_error = add_constant_schedule_ruleset(openstudio_model, 0.0, name = f"{zone_name}_Sch_HSP_Error")
    cmd_hsp_error = osmod.EnergyManagementSystemActuator(sch_hsp_error, 'Schedule:Year', 'Schedule Value')
    cmd_hsp_error.setName(f"{zone_name}_cmd_hsp_error")

    #####
    # List of global variables used in EMS scripts
    ####

    # Proportional  gain constant (recommended 0.3 or less).
    prp_k = openstudio_model.getEnergyManagementSystemGlobalVariableByName('prp_k')
    if prp_k.is_initialized():
        prp_k = prp_k.get()
    else:
        prp_k = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, 'prp_k')

    # Upper slab temperature setpoint limit (recommended no higher than 29C (84F))
    upper_slab_sp_lim = openstudio_model.getEnergyManagementSystemGlobalVariableByName('upper_slab_sp_lim')
    if upper_slab_sp_lim.is_initialized():
        upper_slab_sp_lim = upper_slab_sp_lim.get()
    else:
        upper_slab_sp_lim = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, 'upper_slab_sp_lim')

    # Lower slab temperature setpoint limit (recommended no lower than 19C (66F))
    lower_slab_sp_lim = openstudio_model.getEnergyManagementSystemGlobalVariableByName('lower_slab_sp_lim')
    if lower_slab_sp_lim.is_initialized():
        lower_slab_sp_lim = lower_slab_sp_lim.get()
    else:
        lower_slab_sp_lim = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, 'lower_slab_sp_lim')

    # Temperature offset used as a safety factor for thermal control (recommend 0.5C (1F)).
    ctrl_temp_offset = openstudio_model.getEnergyManagementSystemGlobalVariableByName('ctrl_temp_offset')
    if ctrl_temp_offset.is_initialized():
        ctrl_temp_offset = ctrl_temp_offset.get()
    else:
        ctrl_temp_offset = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, 'ctrl_temp_offset')

    # Hour where slab setpoint is to be changed
    hour_of_slab_sp_change = openstudio_model.getEnergyManagementSystemGlobalVariableByName('hour_of_slab_sp_change')
    if hour_of_slab_sp_change.is_initialized():
        hour_of_slab_sp_change = hour_of_slab_sp_change.get()
    else:
        hour_of_slab_sp_change = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, 'hour_of_slab_sp_change')

    #####
    # List of zone specific variables used in EMS scripts
    ####

    # Maximum 'measured' temperature in zone during occupied times. Default setup uses mean air temperature.
    # Other possible choices are operative and mean radiant temperature.
    zone_max_ctrl_temp = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, f"{zone_name}_max_ctrl_temp")

    # Minimum 'measured' temperature in zone during occupied times. Default setup uses mean air temperature.
    # Other possible choices are operative and mean radiant temperature.
    zone_min_ctrl_temp = osmod.EnergyManagementSystemGlobalVariable(openstudio_model, f"{zone_name}_min_ctrl_temp")

    #####
    # List of 'sensors' used in the EMS programs
    ####

    # Controlled zone temperature for the zone.
    zone_ctrl_temperature = osmod.EnergyManagementSystemSensor(openstudio_model, 'Zone Air Temperature')
    zone_ctrl_temperature.setName(f"{zone_name}_ctrl_temperature")
    zone_ctrl_temperature.setKeyName(zone.name().get())

    # check for zone thermostat and replace heat/cool schedules for radiant system control
    # if there is no zone thermostat, then create one
    zone_thermostat = zone.thermostatSetpointDualSetpoint()

    if zone_thermostat.is_initialized():
        print('openstudio.Model.Model', f"Replacing thermostat schedules in zone #{zone.name()} for radiant system control.")
        zone_thermostat = zone.thermostatSetpointDualSetpoint().get()
    else:
        print('openstudio.Model.Model', f"Zone {zone.name()} does not have a thermostat. Creating a thermostat for radiant system control.")
        zone_thermostat = osmod.ThermostatSetpointDualSetpoint(openstudio_model)
        zone_thermostat.setName(f"{zone_name}_Thermostat_DualSetpoint")

    # create new heating and cooling schedules to be used with all radiant systems
    zone_htg_thermostat = openstudio_model.getScheduleRulesetByName('Radiant System Heating Setpoint')
    if zone_htg_thermostat.is_initialized():
        zone_htg_thermostat = zone_htg_thermostat.get()
    else:
        zone_htg_thermostat = add_constant_schedule_ruleset(openstudio_model, 20.0, name = 'Radiant System Heating Setpoint', 
                                                            sch_type_limit = 'Temperature')

    zone_clg_thermostat = openstudio_model.getScheduleRulesetByName('Radiant System Cooling Setpoint')
    if zone_clg_thermostat.is_initialized():
        zone_clg_thermostat = zone_clg_thermostat.get()
    else:
        zone_clg_thermostat = add_constant_schedule_ruleset(openstudio_model, 26.0, name = 'Radiant System Cooling Setpoint', 
                                                            sch_type_limit = 'Temperature')

    # implement new heating and cooling schedules
    zone_thermostat.setHeatingSetpointTemperatureSchedule(zone_htg_thermostat)
    zone_thermostat.setCoolingSetpointTemperatureSchedule(zone_clg_thermostat)

    # Upper comfort limit for the zone. Taken from existing thermostat schedules in the zone.
    zone_upper_comfort_limit = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
    zone_upper_comfort_limit.setName(f"{zone_name}_upper_comfort_limit")
    zone_upper_comfort_limit.setKeyName(zone_clg_thermostat.name().get())

    # Lower comfort limit for the zone. Taken from existing thermostat schedules in the zone.
    zone_lower_comfort_limit = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
    zone_lower_comfort_limit.setName(f"{zone_name}_lower_comfort_limit")
    zone_lower_comfort_limit.setKeyName(zone_htg_thermostat.name().get())

    # Radiant system water flow rate used to determine if there is active hydronic cooling in the radiant system.
    zone_rad_cool_operation = osmod.EnergyManagementSystemSensor(openstudio_model, 'System Node Mass Flow Rate')
    zone_rad_cool_operation.setName(f"{zone_name}_rad_cool_operation")
    zone_rad_cool_operation.setKeyName(coil_cooling_radiant.to_StraightComponent().get().inletModelObject().get().name().get())

    # Radiant system water flow rate used to determine if there is active hydronic heating in the radiant system.
    zone_rad_heat_operation = osmod.EnergyManagementSystemSensor(openstudio_model, 'System Node Mass Flow Rate')
    zone_rad_heat_operation.setName(f"{zone_name}_rad_heat_operation")
    zone_rad_heat_operation.setKeyName(coil_heating_radiant.to_StraightComponent().get().inletModelObject().get().name().get())

    # Radiant system switchover delay time period schedule
    # used to determine if there is active hydronic cooling/heating in the radiant system.
    zone_rad_switch_over = openstudio_model.getEnergyManagementSystemSensorByName('radiant_switch_over_time')

    if zone_rad_switch_over.is_initialized() == False:
        zone_rad_switch_over = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
        zone_rad_switch_over.setName('radiant_switch_over_time')
        zone_rad_switch_over.setKeyName(sch_radiant_switchover.name().get())

    # Last 24 hours trend for radiant system in cooling mode.
    zone_rad_cool_operation_trend = osmod.EnergyManagementSystemTrendVariable(openstudio_model, zone_rad_cool_operation)
    zone_rad_cool_operation_trend.setName(f"{zone_name}_rad_cool_operation_trend")
    zone_rad_cool_operation_trend.setNumberOfTimestepsToBeLogged(zone_timestep * 48)

    # Last 24 hours trend for radiant system in heating mode.
    zone_rad_heat_operation_trend = osmod.EnergyManagementSystemTrendVariable(openstudio_model, zone_rad_heat_operation)
    zone_rad_heat_operation_trend.setName(f"{zone_name}_rad_heat_operation_trend")
    zone_rad_heat_operation_trend.setNumberOfTimestepsToBeLogged(zone_timestep * 48)

    # use zone occupancy objects for radiant system control if selected
    if use_zone_occupancy_for_control:
        # get annual occupancy schedule for zone
        occ_schedule_ruleset = thermal_zone_get_occupancy_schedule(zone, sch_name = f"{zone.name} Radiant System Occupied Schedule",
                                                                occupied_percentage_threshold = occupied_percentage_threshold)
    else:
        occ_schedule_ruleset = openstudio_model.getScheduleRulesetByName('Whole Building Radiant System Occupied Schedule')
        if occ_schedule_ruleset.is_initialized():
            occ_schedule_ruleset = occ_schedule_ruleset.get()
        else:
            # create occupancy schedules
            occ_schedule_ruleset = osmod.ScheduleRuleset(openstudio_model)
            occ_schedule_ruleset.setName('Whole Building Radiant System Occupied Schedule')

            start_hour = int(model_occ_hr_end)
            start_minute = int(((model_occ_hr_end % 1) * 60))
            end_hour = int(model_occ_hr_start)
            end_minute = int(((model_occ_hr_start % 1) * 60))

            if end_hour > start_hour:
                occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, start_hour, start_minute, 0), 1.0)
                occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, end_hour, end_minute, 0), 0.0)
                if end_hour < 24: occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
            elif start_hour > end_hour:
                occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, end_hour, end_minute, 0), 0.0)
                occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, start_hour, start_minute, 0), 1.0)
                if start_hour < 24: occ_schedule_ruleset.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 0.0)
            else:
                occ_schedule_ruleset.defaultDaySchedule.addValue(openstudio.Time.new(0, 24, 0, 0), 1.0)

    # create ems sensor for zone occupied status
    zone_occupied_status = osmod.EnergyManagementSystemSensor(openstudio_model, 'Schedule Value')
    zone_occupied_status.setName(f"{zone_name}_occupied_status")
    zone_occupied_status.setKeyName(occ_schedule_ruleset.name().get())

    # Last 24 hours trend for zone occupied status
    zone_occupied_status_trend = osmod.EnergyManagementSystemTrendVariable(openstudio_model, zone_occupied_status)
    zone_occupied_status_trend.setName(f"{zone_name}_occupied_status_trend")
    zone_occupied_status_trend.setNumberOfTimestepsToBeLogged(zone_timestep * 48)

    #####
    # List of EMS programs to implement the proportional control for the radiant system.
    ####

    # Initialize global constant values used in EMS programs.
    set_constant_values_prg_body =f"SET prp_k              = {proportional_gain},\
        SET ctrl_temp_offset   = 0.5,\
        SET upper_slab_sp_lim  = 29,\
        SET lower_slab_sp_lim  = 19,\
        SET hour_of_slab_sp_change = 18" 
        
    set_constant_values_prg = openstudio_model.getEnergyManagementSystemProgramByName('Set_Constant_Values')
    if set_constant_values_prg.is_initialized():
        set_constant_values_prg = set_constant_values_prg.get()
    else:
        set_constant_values_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
        set_constant_values_prg.setName('Set_Constant_Values')
        set_constant_values_prg.setBody(set_constant_values_prg_body)

    # Initialize zone specific constant values used in EMS programs.
    set_constant_zone_values_prg_body = f"SET {zone_name}_max_ctrl_temp      = {zone_name}_lower_comfort_limit,\
        SET {zone_name}_min_ctrl_temp      = {zone_name}_upper_comfort_limit,\
        SET {zone_name}_cmd_csp_error      = 0,\
        SET {zone_name}_cmd_hsp_error      = 0,\
        SET {zone_name}_cmd_cold_water_ctrl = {zone_name}_upper_comfort_limit,\
        SET {zone_name}_cmd_hot_water_ctrl  = {zone_name}_lower_comfort_limit" 

    set_constant_zone_values_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    set_constant_zone_values_prg.setName(f"{zone_name}_Set_Constant_Values")
    set_constant_zone_values_prg.setBody(set_constant_zone_values_prg_body)

    # Calculate maximum and minimum 'measured' controlled temperature in the zone
    calculate_minmax_ctrl_temp_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    calculate_minmax_ctrl_temp_prg.setName(f"{zone_name}_Calculate_Extremes_In_Zone")

    calculate_minmax_ctrl_temp_prg_body = f"IF ({zone_name}_occupied_status == 1),\
            IF {zone_name}_ctrl_temperature > {zone_name}_max_ctrl_temp,\
                SET {zone_name}_max_ctrl_temp = {zone_name}_ctrl_temperature,\
            ENDIF,\
            IF {zone_name}_ctrl_temperature < {zone_name}_min_ctrl_temp,\
                SET {zone_name}_min_ctrl_temp = {zone_name}_ctrl_temperature,\
            ENDIF,\
            ELSE,\
                SET {zone_name}_max_ctrl_temp = {zone_name}_lower_comfort_limit,\
                SET {zone_name}_min_ctrl_temp = {zone_name}_upper_comfort_limit,\
            ENDIF" 

    calculate_minmax_ctrl_temp_prg.setBody(calculate_minmax_ctrl_temp_prg_body)

    # Calculate errors from comfort zone limits and 'measured' controlled temperature in the zone.
    calculate_errors_from_comfort_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    calculate_errors_from_comfort_prg.setName(f"{zone_name}_Calculate_Errors_From_Comfort")
    
    calculate_errors_from_comfort_prg_body = f"IF (CurrentTime == (hour_of_slab_sp_change - ZoneTimeStep)),\
        SET {zone_name}_cmd_csp_error = ({zone_name}_upper_comfort_limit - ctrl_temp_offset) - {zone_name}_max_ctrl_temp,\
        SET {zone_name}_cmd_hsp_error = ({zone_name}_lower_comfort_limit + ctrl_temp_offset) - {zone_name}_min_ctrl_temp,\
        ENDIF"

    calculate_errors_from_comfort_prg.setBody(calculate_errors_from_comfort_prg_body)

    # Calculate the new active slab temperature setpoint for heating and cooling
    calculate_slab_ctrl_setpoint_prg = osmod.EnergyManagementSystemProgram(openstudio_model)
    calculate_slab_ctrl_setpoint_prg.setName(f"{zone_name}_Calculate_Slab_Ctrl_Setpoint")
    
    calculate_slab_ctrl_setpoint_prg_body = f"SET {zone_name}_cont_cool_oper = @TrendSum {zone_name}_rad_cool_operation_trend radiant_switch_over_time/ZoneTimeStep,\
        SET {zone_name}_cont_heat_oper = @TrendSum {zone_name}_rad_heat_operation_trend radiant_switch_over_time/ZoneTimeStep,\
        SET {zone_name}_occupied_hours = @TrendSum {zone_name}_occupied_status_trend 24/ZoneTimeStep,\
        IF ({zone_name}_cont_cool_oper > 0) && ({zone_name}_occupied_hours > 0) && (CurrentTime == hour_of_slab_sp_change),\
        SET {zone_name}_cmd_hot_water_ctrl = {zone_name}_cmd_hot_water_ctrl + ({zone_name}_cmd_csp_error*prp_k),\
        ELSEIF ({zone_name}_cont_heat_oper > 0) && ({zone_name}_occupied_hours > 0) && (CurrentTime == hour_of_slab_sp_change),\
        SET {zone_name}_cmd_hot_water_ctrl = {zone_name}_cmd_hot_water_ctrl + ({zone_name}_cmd_hsp_error*prp_k),\
        ELSE,\
        SET {zone_name}_cmd_hot_water_ctrl = {zone_name}_cmd_hot_water_ctrl,\
        ENDIF,\
        IF ({zone_name}_cmd_hot_water_ctrl < lower_slab_sp_lim),\
        SET {zone_name}_cmd_hot_water_ctrl = lower_slab_sp_lim,\
        ELSEIF ({zone_name}_cmd_hot_water_ctrl > upper_slab_sp_lim),\
        SET {zone_name}_cmd_hot_water_ctrl = upper_slab_sp_lim,\
        ENDIF,\
        SET {zone_name}_cmd_cold_water_ctrl = {zone_name}_cmd_hot_water_ctrl + 0.01"
        
    calculate_slab_ctrl_setpoint_prg.setBody(calculate_slab_ctrl_setpoint_prg_body)

    #####
    # List of EMS program manager objects
    ####

    initialize_constant_parameters = openstudio_model.getEnergyManagementSystemProgramCallingManagerByName('Initialize_Constant_Parameters')
    if initialize_constant_parameters.is_initialized():
        initialize_constant_parameters = initialize_constant_parameters.get()
        # add program if it does not exist in manager
        existing_program_names = []
        for prg in initialize_constant_parameters.programs():
            existing_program_names.append(prg.name().get().lower())
        
        if set_constant_values_prg.name().get().lower() not in existing_program_names:
            initialize_constant_parameters.addProgram(set_constant_values_prg)
    else:
        initialize_constant_parameters = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
        initialize_constant_parameters.setName('Initialize_Constant_Parameters')
        initialize_constant_parameters.setCallingPoint('BeginNewEnvironment')
        initialize_constant_parameters.addProgram(set_constant_values_prg)

    initialize_constant_parameters_after_warmup = openstudio_model.getEnergyManagementSystemProgramCallingManagerByName('Initialize_Constant_Parameters_After_Warmup')
    if initialize_constant_parameters_after_warmup.is_initialized():
        initialize_constant_parameters_after_warmup = initialize_constant_parameters_after_warmup.get()
        # add program if it does not exist in manager
        existing_program_names = []
        programs = initialize_constant_parameters_after_warmup.programs()
        for prg in programs:
            existing_program_names.append(prg.name().get().lower())
        
        if set_constant_values_prg.name().get().lower() not in existing_program_names:
            initialize_constant_parameters_after_warmup.addProgram(set_constant_values_prg)

    else:
        initialize_constant_parameters_after_warmup = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
        initialize_constant_parameters_after_warmup.setName('Initialize_Constant_Parameters_After_Warmup')
        initialize_constant_parameters_after_warmup.setCallingPoint('AfterNewEnvironmentWarmUpIsComplete')
        initialize_constant_parameters_after_warmup.addProgram(set_constant_values_prg)

    zone_initialize_constant_parameters = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
    zone_initialize_constant_parameters.setName(f"{zone_name}_Initialize_Constant_Parameters")
    zone_initialize_constant_parameters.setCallingPoint('BeginNewEnvironment')
    zone_initialize_constant_parameters.addProgram(set_constant_zone_values_prg)

    zone_initialize_constant_parameters_after_warmup = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
    zone_initialize_constant_parameters_after_warmup.setName(f"{zone_name}_Initialize_Constant_Parameters_After_Warmup")
    zone_initialize_constant_parameters_after_warmup.setCallingPoint('AfterNewEnvironmentWarmUpIsComplete')
    zone_initialize_constant_parameters_after_warmup.addProgram(set_constant_zone_values_prg)

    average_building_temperature = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
    average_building_temperature.setName(f"{zone_name}_Average_Building_Temperature")
    average_building_temperature.setCallingPoint('EndOfZoneTimestepAfterZoneReporting')
    average_building_temperature.addProgram(calculate_minmax_ctrl_temp_prg)
    average_building_temperature.addProgram(calculate_errors_from_comfort_prg)

    programs_at_beginning_of_timestep = osmod.EnergyManagementSystemProgramCallingManager(openstudio_model)
    programs_at_beginning_of_timestep.setName(f"{zone_name}_Programs_At_Beginning_Of_Timestep")
    programs_at_beginning_of_timestep.setCallingPoint('BeginTimestepBeforePredictor')
    programs_at_beginning_of_timestep.addProgram(calculate_slab_ctrl_setpoint_prg)

    #####
    # List of variables for output.
    ####

    zone_max_ctrl_temp_output = osmod.EnergyManagementSystemOutputVariable(openstudio_model, zone_max_ctrl_temp)
    zone_max_ctrl_temp_output.setName(f"{zone_name} Maximum occupied temperature in zone")
    zone_min_ctrl_temp_output = osmod.EnergyManagementSystemOutputVariable(openstudio_model, zone_min_ctrl_temp)
    zone_min_ctrl_temp_output.setName(f"{zone_name} Minimum occupied temperature in zone")

def add_radiant_basic_controls(openstudio_model: osmod, zone: osmod.ThermalZone, radiant_loop: osmod.ZoneHVACLowTempRadiantVarFlow, 
                               radiant_temperature_control_type: str = 'SurfaceFaceTemperature', slab_setpoint_oa_control: bool = False, switch_over_time: float = 24.0,
                               slab_sp_at_oat_low: float = 22.8, slab_oat_low: float = 18.3, slab_sp_at_oat_high: float = 20, slab_oat_high: float = 26.7):

    """
    - Native EnergyPlus objects implement a control for a single thermal zone with a radiant system.
    - https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_radiant_basic_controls

    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    zone : osmod.ThermalZone
        zone to add radiant controls.

    radiant_loop : osmod.ZoneHVACLowTempRadiantVarFlow
        radiant loop in thermal zone

    radiant_temperature_control_type : str, optional
        - (defaults to: 'SurfaceFaceTemperature') — determines the controlled temperature for the radiant system options are
        - 'SurfaceFaceTemperature', 'SurfaceInteriorTemperature'

    slab_setpoint_oa_control : bool, optional
        - (defaults to: false) — True if slab setpoint is to be varied based on outdoor air temperature

    switch_over_time : float, optional
        (defaults to 24) Time limitation for when the system can switch between heating and cooling

    slab_sp_at_oat_low : float, optional
        (defaults to: 22.8) radiant slab temperature setpoint, in C, at the outdoor high temperature.
        
    slab_oat_low : float, optional
        (defaults to: 18.3) — outdoor drybulb air temperature, in C, for low radiant slab setpoint.

    slab_sp_at_oat_high : float, optional
        (defaults to: 20) — radiant slab temperature setpoint, in C, at the outdoor low temperature.

    slab_oat_high : float, optional
        (defaults to: 26.7) — outdoor drybulb air temperature, in C, for high radiant slab setpoint.

    """

    zone_name = str(zone.name()).replace('/[ +-.]/', '_')

    if openstudio_model.version() < openstudio.VersionString('3.1.1'):
        coil_cooling_radiant = radiant_loop.coolingCoil().to_CoilCoolingLowTempRadiantVarFlow().get()
        coil_heating_radiant = radiant_loop.heatingCoil().to_CoilHeatingLowTempRadiantVarFlow().get()
    else:
        coil_cooling_radiant = radiant_loop.coolingCoil().get().to_CoilCoolingLowTempRadiantVarFlow().get()
        coil_heating_radiant = radiant_loop.heatingCoil().get().to_CoilHeatingLowTempRadiantVarFlow().get()

    #####
    # Define radiant system parameters
    ####
    # set radiant system temperature and setpoint control type
    if radiant_temperature_control_type.lower() not in ['surfacefacetemperature', 'surfaceinteriortemperature']:
        print('openstudio.Model.Model', f"Control sequences not compatible with '{radiant_temperature_control_type}' radiant system control. Defaulting to 'SurfaceFaceTemperature'.")
        radiant_temperature_control_type = 'SurfaceFaceTemperature'

    radiant_loop.setTemperatureControlType(radiant_temperature_control_type)

    # get existing switchover time schedule or create one if needed
    sch_radiant_switchover = openstudio_model.getScheduleRulesetByName('Radiant System Switchover')
    if sch_radiant_switchover.is_initialized():
        sch_radiant_switchover = sch_radiant_switchover.get()
    else:
        sch_radiant_switchover = add_constant_schedule_ruleset(openstudio_model, switch_over_time, name = 'Radiant System Switchover', 
                                                               sch_type_limit = 'Dimensionless')

    # set radiant system switchover schedule
    radiant_loop.setChangeoverDelayTimePeriodSchedule(sch_radiant_switchover.to_Schedule().get())

    if slab_setpoint_oa_control:
        # get weather file from model
        weather_file = openstudio_model.getWeatherFile()
        if weather_file.initialized():
            # get annual outdoor dry bulb temperature
            annual_oat = []
            wea_dat = weather_file.file().get().data()
            for dat in wea_dat:
                annual_oat.append(dat.dryBulbTemperature().get())

            # calculate a nhrs rolling average from annual outdoor dry bulb temperature
            nhrs = 24
            last_nhrs_oat_in_year = annual_oat[-23:]
            combined_oat = last_nhrs_oat_in_year + annual_oat

            oat_rolling_average = []
            i = 0
            window_size = nhrs
            moving_averages = []
            while i < len(combined_oat) - window_size + 1:
                window = combined_oat[i : i + window_size]
                window_average = round(sum(window) / window_size, 2)
                oat_rolling_average.append(window_average)
                i += 1
            # use rolling average to calculate slab setpoint temperature

            # calculate relationship between slab setpoint and slope
            slope_num = slab_sp_at_oat_high - slab_sp_at_oat_low
            slope_den = slab_oat_high - slab_oat_low
            sp_and_oat_slope = round(float(slope_num/slope_den),4)
            slab_setpoint = []
            for oat_roll in oat_rolling_average:
                spt = slab_sp_at_oat_low + ((oat_roll - slab_oat_low) * sp_and_oat_slope)
                slab_setpoint.append(round(spt, 1))

            # input upper limits on slab setpoint
            slab_sp_upper_limit = max([slab_sp_at_oat_high, slab_sp_at_oat_low])
            slab_sp_lower_limit = min([slab_sp_at_oat_high, slab_sp_at_oat_low])
            slab_setpoint1 = []
            for sstp in slab_setpoint:
                if sstp > slab_sp_upper_limit:
                    slab_setpoint1.append(round(slab_sp_upper_limit, 1))
                elif sstp < slab_sp_lower_limit:
                    slab_setpoint1.append(round(slab_sp_lower_limit, 1))
                else:
                    slab_setpoint1.append(sstp)
            slab_setpoint = slab_setpoint1

            # create ruleset for slab setpoint
            sch_type_limits_obj = add_schedule_type_limits(openstudio_model, standard_sch_type_limit = 'Temperature')
            sch_radiant_slab_setp = make_ruleset_sched_from_8760(openstudio_model, slab_setpoint, 'Sch_Radiant_SlabSetP_Based_On_Rolling_Mean_OAT',
                                                                 sch_type_limits_obj)

            coil_heating_radiant.setHeatingControlTemperatureSchedule(sch_radiant_slab_setp)
            coil_cooling_radiant.setCoolingControlTemperatureSchedule(sch_radiant_slab_setp)
        else:
            print('openstudio.Model.Model', 'Model does not have a weather file associated with it. Define to implement slab setpoint based on outdoor weather.')
        
    else:
        # radiant system cooling control setpoint
        slab_setpoint = 22
        sch_radiant_clgsetp = add_constant_schedule_ruleset(openstudio_model, slab_setpoint + 0.1, name = f"{zone_name}_Sch_Radiant_ClgSetP")
        coil_cooling_radiant.setCoolingControlTemperatureSchedule(sch_radiant_clgsetp)

        # radiant system heating control setpoint
        sch_radiant_htgsetp = add_constant_schedule_ruleset(openstudio_model, slab_setpoint, name = f"{zone_name}_Sch_Radiant_HtgSetP")
        coil_heating_radiant.setHeatingControlTemperatureSchedule(sch_radiant_htgsetp)

def add_low_temp_radiant(openstudio_model: osmod, thermal_zones: list[osmod.ThermalZone], hot_water_loop: osmod.PlantLoop, 
                         chilled_water_loop: osmod.PlantLoop, two_pipe_system: bool = False, two_pipe_control_strategy: str = 'outdoor_air_lockout',
                         two_pipe_lockout_temperature: float = 18.3, plant_supply_water_temperature_control: bool = False, 
                         plant_supply_water_temperature_control_strategy: str = 'outdoor_air', hwsp_at_oat_low: float = 48.9, 
                         hw_oat_low: float =  12.8, hwsp_at_oat_high: float = 26.7, hw_oat_high: float = 21.1, chwsp_at_oat_low: float = 21.1,
                         chw_oat_low: float = 18.3, chwsp_at_oat_high: float = 12.8, chw_oat_high: float = 23.9, radiant_type: str = 'floor',
                         radiant_temperature_control_type: str = 'SurfaceFaceTemperature', radiant_setpoint_control_type: str = 'ZeroFlowPower',
                         include_carpet: bool = True, carpet_thickness_m: float = 0.006, control_strategy: str = 'proportional_control',
                         use_zone_occupancy_for_control: bool = True, occupied_percentage_threshold: float = 0.10, model_occ_hr_start: float = 6.0,
                         model_occ_hr_end: float = 18.0, proportional_gain: float = 0.3, switch_over_time: float = 24.0, slab_sp_at_oat_low: float = 22.8,
                         slab_oat_low: float = 18.3, slab_sp_at_oat_high: float = 20, slab_oat_high: float = 26.7, radiant_availability_type: str = 'precool', 
                         radiant_lockout: bool = False, radiant_lockout_start_time: float = 12.0, 
                         radiant_lockout_end_time: float = 20.0) -> list[osmod.ZoneHVACLowTempRadiantVarFlow]:

    """
    Creates a condenser water loop and adds it to the model.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_cw_loop)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    thermal_zones : list[osmod.ThermalZone]
        array of zones to add radiant loops
    
    hot_water_loop : osmod.PlantLoop
        the hot water loop that serves the radiant loop.
    
    chilled_water_loop : osmod.PlantLoop
        the chilled water loop that serves the radiant loop.

    two_pipe_system : bool, optional
        when set to true, it converts the default 4-pipe water plant HVAC system to a 2-pipe system.

    two_pipe_control_strategy : str, optional
        - (defaults to: 'outdoor_air_lockout') — Method to determine whether the loop is in heating or cooling mode 'outdoor_air_lockout' 
        - The system will be in heating below the two_pipe_lockout_temperature variable,
        - and cooling above the two_pipe_lockout_temperature. Requires the two_pipe_lockout_temperature variable.
        - 'zone_demand' - Create EMS code to determine heating or cooling mode based on zone heating or cooling load requests.
        - Requires thermal_zones defined.
    
    two_pipe_lockout_temperature : float, optional
        (defaults to: 18.3) — hot water plant lockout in degreesC, default 18.3C. Hot water plant is unavailable when outdoor drybulb is above the specified threshold.

    plant_supply_water_temperature_control : bool, optional
        (defaults to: false) — Set to true if the plant supply water temperature is to be controlled else it is held constant, default to false.
    
    plant_supply_water_temperature_control_strategy : str, optional
        - Method to determine how to control the plant's supply water temperature. 'outdoor_air'
        - Set the supply water temperature based on the outdoor air temperature. 'zone_demand' 
        - Set the supply water temperature based on the preponderance of zone demand.
        - Requires thermal_zone defined.
    
    hwsp_at_oat_low : float, optional
        (defaults to: 48.9) — hot water plant supply water temperature setpoint, in C, at the outdoor low temperature.
    
    hw_oat_low : float, optional
        (defaults to: 12.8) — outdoor drybulb air temperature, in C, for low setpoint for hot water plant.

    hwsp_at_oat_high : float, optional
        (defaults to: 26.7) — hot water plant supply water temperature setpoint, in C, at the outdoor high temperature.
    
    hw_oat_high : float, optional
        (defaults to: 21.1) — outdoor drybulb air temperature, in C, for high setpoint for hot water plant.
    
    chwsp_at_oat_low : float, optional
        (defaults to: 21.1) — chilled water plant supply water temperature setpoint, in C, at the outdoor low temperature.

    chw_oat_low : float, optional
        (defaults to: 18.3) — outdoor drybulb air temperature, in C, for low setpoint for chilled water plant.

    chwsp_at_oat_high : float, optional
        (defaults to: 12.8) — chilled water plant supply water temperature setpoint, in C, at the outdoor high temperature.

    chw_oat_high : float, optional
        (defaults to: 23.9) — outdoor drybulb air temperature, in C, for high setpoint for chilled water plant.

    radiant_type : str, optional
        (defaults to: 'floor') — type of radiant system, floor or ceiling, to create in zone.
    
    radiant_temperature_control_type : str, optional
        - (defaults to: 'SurfaceFaceTemperature') — determines the controlled temperature for the radiant system options are 
        - 'MeanAirTemperature', 'MeanRadiantTemperature', 'OperativeTemperature', 'OutdoorDryBulbTemperature', 'OutdoorWetBulbTemperature', 
        - 'SurfaceFaceTemperature', 'SurfaceInteriorTemperature'

    radiant_setpoint_control_type : str, optional
        (defaults to: 'ZeroFlowPower') — determines the response of the radiant system at setpoint temperature options are ‘ZeroFlowPower’, ‘HalfFlowPower’
    
    include_carpet : bool, optional
        (defaults to: true) — boolean to include thin carpet tile over radiant slab, default to true

    carpet_thickness_ : float, optional
        (defaults to: 0.006) — thickness of carpet in meter

    control_strategy : str, optional
        - (defaults to: 'proportional_control') — name of control strategy. 
        - Options are 'proportional_control', 'oa_based_control', 'constant_control', and 'none'. If control strategy is 'proportional_control', 
        - the method will apply the CBE radiant control sequences detailed in Raftery et al. (2017), 
        - 'A new control strategy for high thermal mass radiant systems'. If control strategy is 'oa_based_control', 
        - the method will apply native EnergyPlus objects/parameters to vary slab setpoint based on outdoor weather. 
        - If control strategy is 'constant_control', the method will apply native EnergyPlus objects/parameters to maintain a constant slab setpoint. 
        - Otherwise no control strategy will be applied and the radiant system will assume the EnergyPlus default controls.

    use_zone_occupancy_for_control : bool, optional
        - (defaults to: true) — Set to true if radiant system is to use specific zone occupancy objects for CBE control strategy. 
        - If false, then it will use values in model_occ_hr_start and model_occ_hr_end for all radiant zones. default to true.

    occupied_percentage_threshold : float, optional
        - (defaults to: 0.10) — the minimum fraction (0 to 1) that counts as occupied if this parameter is set, 
        - the returned ScheduleRuleset will be 0 = unoccupied, 1 = occupied otherwise the ScheduleRuleset will be the weighted fractional occupancy 
        - schedule. Only used if use_zone_occupancy_for_control is set to true.

    model_occ_hr_start : float, optional
        (defaults to: 6.0) — (Optional) Only applies if control_strategy is 'proportional_control'. Starting hour of building occupancy.

    model_occ_hr_end : float, optional
        (defaults to: 18.0) — (Optional) Only applies if control_strategy is 'proportional_control'. Ending hour of building occupancy

    proportional_gain : float, optional
        (defaults to: 0.3) — (Optional) Only applies if control_strategy is 'proportional_control'. Proportional gain constant (recommended 0.3 or less).

    switch_over_time : float, optional
        (defaults to: 24.0) — Time limitation for when the system can switch between heating and cooling

    slab_sp_at_oat_low : float, optional
        (defaults to: 22.8) — radiant slab temperature setpoint, in C, at the outdoor high temperature.

    slab_oat_low : float, optional
        (defaults to: 18.3) — outdoor drybulb air temperature, in C, for low radiant slab setpoint.

    slab_sp_at_oat_high : float, optional
        (defaults to: 20) — radiant slab temperature setpoint, in C, at the outdoor low temperature.

    slab_oat_high : float, optional
        (defaults to: 26.7) — outdoor drybulb air temperature, in C, for high radiant slab setpoint.

    radiant_availability_type : str, optional
        - (defaults to: 'precool') — a preset that determines the availability of the radiant system options are
        - 'all_day', 'precool', 'afternoon_shutoff', 'occupancy' If preset is set to 'all_day' radiant system is available 24 hours a day, 
        - 'precool' primarily operates radiant system during night-time hours, 'afternoon_shutoff' avoids operation during peak grid demand, 
        - and 'occupancy' operates radiant system during building occupancy hours.

    radiant_lockout : bool, optional
        (defaults to: false) — True if system contains a radiant lockout. If true, it will overwrite radiant_availability_type.

    radiant_lockout_start_time : float, optional
        (defaults to: 12.0) — decimal hour of when radiant lockout starts Only used if radiant_lockout is true

    radiant_lockout_end_time : float, optional
        (defaults to: 20.0) — decimal hour of when radiant lockout ends Only used if radiant_lockout is true

    Returns
    -------
    radiant_systems : list[osmod.ZoneHVACLowTempRadiantVarFlow]
        the resultant radiant_systems
    """
    # create internal source constructions for surfaces
    print('openstudio.Model.Model', f"Replacing #{radiant_type} constructions with new radiant slab constructions.")

    # determine construction insulation thickness by climate zone
    climate_zone =  find_standard_climate_zone_frm_osmod(openstudio_model)
    if not climate_zone:
        print('openstudio.Model.Model', 'Unable to determine climate zone for radiant slab insulation determination.  Defaulting to climate zone 5, R-20 insulation, 110F heating design supply water temperature.')
        cz_mult = 4
        radiant_htg_dsgn_sup_wtr_temp_f = 110
    else:
        climate_zone_set = find_climate_zone_set(openstudio_model, climate_zone)
        clm_num = climate_zone_set.replace('ClimateZone ', '')
        clm_num = clm_num.replace('CEC T24 ', '')
        if clm_num == '1':
            cz_mult = 2
            radiant_htg_dsgn_sup_wtr_temp_f = 90
        elif (clm_num == '2' or clm_num == '2A' or clm_num == '2B' or clm_num == 'CEC15'):
            cz_mult = 2
            radiant_htg_dsgn_sup_wtr_temp_f = 100
        elif (clm_num == '3' or clm_num == '3A' or clm_num =='3B' or clm_num == '3C' or clm_num == 'CEC3' or clm_num == 'CEC4' 
              or clm_num == 'CEC5' or clm_num == 'CEC6' or clm_num == 'CEC7' or clm_num == 'CEC8' or clm_num == 'CEC9' or clm_num == 'CEC10' 
              or clm_num == 'CEC11' or clm_num == 'CEC12' or clm_num == 'CEC13' or clm_num == 'CEC14'):
            cz_mult = 3
            radiant_htg_dsgn_sup_wtr_temp_f = 100
        elif (clm_num == '4' or clm_num == '4A' or clm_num == '4B' or clm_num == '4C' or clm_num == 'CEC1' or clm_num == 'CEC2'):
            cz_mult = 4
            radiant_htg_dsgn_sup_wtr_temp_f = 100
        elif (clm_num == '5' or clm_num =='5A' or clm_num =='5B' or clm_num == '5B' or clm_num == '5C' or clm_num == 'CEC16'):
            cz_mult = 4
            radiant_htg_dsgn_sup_wtr_temp_f = 110
        elif (clm_num == '6' or clm_num == '6A' or clm_num == '6B'):
            cz_mult = 4
            radiant_htg_dsgn_sup_wtr_temp_f = 120
        elif (clm_num == '7' or clm_num == '8'): 
            cz_mult = 5
            radiant_htg_dsgn_sup_wtr_temp_f = 120
        else: # default to 4
            cz_mult = 4
            radiant_htg_dsgn_sup_wtr_temp_f = 100
        print('openstudio.Model.Model', 
              f"Based on model climate zone #{climate_zone} using R-#{int(cz_mult * 5)} slab insulation, R-#{(int(cz_mult + 1) * 5)} exterior floor insulation, R-#{int((cz_mult + 1) * 2 * 5)} exterior roof insulation, and #{radiant_htg_dsgn_sup_wtr_temp_f}F heating design supply water temperature.")

    # create materials
    mat_concrete_3_5in = osmod.StandardOpaqueMaterial(openstudio_model, 'MediumRough', 0.0889, 2.31, 2322, 832)
    mat_concrete_3_5in.setName('Radiant Slab Concrete - 0.09 m.')

    mat_concrete_1_5in = osmod.StandardOpaqueMaterial(openstudio_model, 'MediumRough', 0.0381, 2.31, 2322, 832)
    mat_concrete_1_5in.setName('Radiant Slab Concrete - 0.03 m')

    mat_refl_roof_membrane = openstudio_model.getStandardOpaqueMaterialByName('Roof Membrane - Highly Reflective')
    if mat_refl_roof_membrane.empty() == False:
        mat_refl_roof_membrane = openstudio_model.getStandardOpaqueMaterialByName('Roof Membrane - Highly Reflective').get()
    else:
        mat_refl_roof_membrane = osmod.StandardOpaqueMaterial(openstudio_model, 'VeryRough', 0.0095, 0.16, 1121.29, 1460)
        mat_refl_roof_membrane.setThermalAbsorptance(0.75)
        mat_refl_roof_membrane.setSolarAbsorptance(0.45)
        mat_refl_roof_membrane.setVisibleAbsorptance(0.7)
        mat_refl_roof_membrane.setName('Roof Membrane - Highly Reflective')

    if include_carpet:
        conductivity_si = 0.06
        # conductivity_ip = openstudio.convert(conductivity_si, 'W/m*K', 'Btu*in/hr*ft^2*R').get()
        r_value = carpet_thickness_m * (1 / conductivity_si)
        mat_thin_carpet_tile = osmod.StandardOpaqueMaterial(openstudio_model, 'MediumRough', carpet_thickness_m, conductivity_si, 288, 1380)
        mat_thin_carpet_tile.setThermalAbsorptance(0.9)
        mat_thin_carpet_tile.setSolarAbsorptance(0.7)
        mat_thin_carpet_tile.setVisibleAbsorptance(0.8)
        mat_thin_carpet_tile.setName(f"Radiant Slab Thin Carpet Tile R-#{round(r_value, 2)}")

    # set exterior slab insulation thickness based on climate zone
    slab_insulation_thickness_m = 0.0254 * cz_mult
    mat_slab_insulation = osmod.StandardOpaqueMaterial(openstudio_model, 'Rough', slab_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_slab_insulation.setName(f"Radiant Ground Slab Insulation - #{round(slab_insulation_thickness_m, 2)} m.")

    ext_insulation_thickness_m = 0.0254 * (cz_mult + 1)
    mat_ext_insulation = openstudio_model.StandardOpaqueMaterial(openstudio_model, 'Rough', ext_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_ext_insulation.setName(f"Radiant Exterior Slab Insulation - #{round(ext_insulation_thickness_m, 2)} m.")

    roof_insulation_thickness_m = 0.0254 * (cz_mult + 1) * 2
    mat_roof_insulation = osmod.StandardOpaqueMaterial(openstudio_model, 'Rough', roof_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_roof_insulation.setName(f"Radiant Exterior Ceiling Insulation - #{round(roof_insulation_thickness_m, 2)} m.")

    # create radiant internal source constructions
    print('openstudio.Model.Model', 'New constructions exclude the metal deck, as high thermal diffusivity materials cause errors in EnergyPlus internal source construction calculations.')

    layers = []
    layers.append(mat_slab_insulation) 
    layers.append(mat_concrete_3_5in)
    layers.append(mat_concrete_1_5in)
    if include_carpet: layers.append(mat_thin_carpet_tile) 
    radiant_ground_slab_construction = osmod.ConstructionWithInternalSource(layers)
    radiant_ground_slab_construction.setName('Radiant Ground Slab Construction')
    radiant_ground_slab_construction.setSourcePresentAfterLayerNumber(2)
    radiant_ground_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(3)
    radiant_ground_slab_construction.setTubeSpacing(0.2286) # 9 inches

    layers = []
    layers.append(mat_ext_insulation)
    layers.append(mat_concrete_3_5in)
    layers.append(mat_concrete_1_5in)
    if include_carpet: layers.append(mat_thin_carpet_tile) 
    radiant_exterior_slab_construction = osmod.ConstructionWithInternalSource(layers)
    radiant_exterior_slab_construction.setName('Radiant Exterior Slab Construction')
    radiant_exterior_slab_construction.setSourcePresentAfterLayerNumber(2)
    radiant_exterior_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(3)
    radiant_exterior_slab_construction.setTubeSpacing(0.2286) # 9 inches

    layers = []
    layers.append(mat_concrete_3_5in)
    layers.append(mat_concrete_1_5in)
    if include_carpet: layers.append(mat_thin_carpet_tile)
    radiant_interior_floor_slab_construction = osmod.ConstructionWithInternalSource(layers)
    radiant_interior_floor_slab_construction.setName('Radiant Interior Floor Slab Construction')
    radiant_interior_floor_slab_construction.setSourcePresentAfterLayerNumber(1)
    radiant_interior_floor_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(1)
    radiant_interior_floor_slab_construction.setTubeSpacing(0.2286) # 9 inches

    # create reversed interior floor construction
    rev_radiant_interior_floor_slab_construction = osmod.ConstructionWithInternalSource(list(reversed(layers)))
    rev_radiant_interior_floor_slab_construction.setName('Radiant Interior Floor Slab Construction - Reversed')
    rev_radiant_interior_floor_slab_construction.setSourcePresentAfterLayerNumber(layers.length - 1)
    rev_radiant_interior_floor_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(layers.length - 1)
    rev_radiant_interior_floor_slab_construction.setTubeSpacing(0.2286) # 9 inches

    layers = []
    if include_carpet: layers.append(mat_thin_carpet_tile)
    layers.append(mat_concrete_3_5in)
    layers.append(mat_concrete_1_5in)
    radiant_interior_ceiling_slab_construction = osmod.ConstructionWithInternalSource(layers)
    radiant_interior_ceiling_slab_construction.setName('Radiant Interior Ceiling Slab Construction')
    if include_carpet:
        slab_src_loc = 2
    else:
        slab_src_loc = 1
    radiant_interior_ceiling_slab_construction.setSourcePresentAfterLayerNumber(slab_src_loc)
    radiant_interior_ceiling_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(slab_src_loc)
    radiant_interior_ceiling_slab_construction.setTubeSpacing(0.2286) # 9 inches

    # create reversed interior ceiling construction
    rev_radiant_interior_ceiling_slab_construction = osmod.ConstructionWithInternalSource(list(reversed(layers)))
    rev_radiant_interior_ceiling_slab_construction.setName('Radiant Interior Ceiling Slab Construction - Reversed')
    rev_radiant_interior_ceiling_slab_construction.setSourcePresentAfterLayerNumber(len(layers) - slab_src_loc)
    rev_radiant_interior_ceiling_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(len(layers) - slab_src_loc)
    rev_radiant_interior_ceiling_slab_construction.setTubeSpacing(0.2286) # 9 inches

    layers = []
    layers.append(mat_refl_roof_membrane)
    layers.append(mat_roof_insulation)
    layers.append(mat_concrete_3_5in)
    layers.append(mat_concrete_1_5in)
    radiant_ceiling_slab_construction = osmod.ConstructionWithInternalSource(layers)
    radiant_ceiling_slab_construction.setName('Radiant Exterior Ceiling Slab Construction')
    radiant_ceiling_slab_construction.setSourcePresentAfterLayerNumber(3)
    radiant_ceiling_slab_construction.setTemperatureCalculationRequestedAfterLayerNumber(4)
    radiant_ceiling_slab_construction.setTubeSpacing(0.2286) # 9 inches

    # adjust hot and chilled water loop temperatures and set new setpoint schedules
    radiant_htg_dsgn_sup_wtr_temp_delt_r = 10.0
    radiant_htg_dsgn_sup_wtr_temp_c = openstudio.convert(radiant_htg_dsgn_sup_wtr_temp_f, 'F', 'C').get()
    radiant_htg_dsgn_sup_wtr_temp_delt_k = openstudio.convert(radiant_htg_dsgn_sup_wtr_temp_delt_r, 'R', 'K').get()
    hot_water_loop.sizingPlant().setDesignLoopExitTemperature(radiant_htg_dsgn_sup_wtr_temp_c)
    hot_water_loop.sizingPlant().setLoopDesignTemperatureDifference(radiant_htg_dsgn_sup_wtr_temp_delt_k)
    hw_temp_sch = add_constant_schedule_ruleset(openstudio_model, radiant_htg_dsgn_sup_wtr_temp_c, 
                                                name = f"#{hot_water_loop.name()} Temp - #{round(radiant_htg_dsgn_sup_wtr_temp_c, 0)}C")
    spms = hot_water_loop.supplyOutletNode().setpointManagers()
    for spm in spms:
        if spm.to_SetpointManagerScheduled().empty() == False:
            spm = spm.to_SetpointManagerScheduled().get()
            spm.setSchedule(hw_temp_sch)
            print('openstudio.Model.Model', 
                  f"Changing hot water loop setpoint for '{hot_water_loop.name()}' to '{hw_temp_sch.name()}' to account for the radiant system.")

    radiant_clg_dsgn_sup_wtr_temp_f = 55.0
    radiant_clg_dsgn_sup_wtr_temp_delt_r = 5.0
    radiant_clg_dsgn_sup_wtr_temp_c = openstudio.convert(radiant_clg_dsgn_sup_wtr_temp_f, 'F', 'C').get()
    radiant_clg_dsgn_sup_wtr_temp_delt_k = openstudio.convert(radiant_clg_dsgn_sup_wtr_temp_delt_r, 'R', 'K').get()
    chilled_water_loop.sizingPlant().setDesignLoopExitTemperature(radiant_clg_dsgn_sup_wtr_temp_c)
    chilled_water_loop.sizingPlant().setLoopDesignTemperatureDifference(radiant_clg_dsgn_sup_wtr_temp_delt_k)
    chw_temp_sch = add_constant_schedule_ruleset(openstudio_model,radiant_clg_dsgn_sup_wtr_temp_c,
                                                 name = f"#{chilled_water_loop.name()} Temp - #{round(radiant_clg_dsgn_sup_wtr_temp_c, 0)}C")
    ch_spms = chilled_water_loop.supplyOutletNode().setpointManagers()
    for spm in ch_spms:
        if spm.to_SetpointManagerScheduled().is_initialized():
            spm = spm.to_SetpointManagerScheduled().get()
            spm.setSchedule(chw_temp_sch)
            print('openstudio.Model.Model', 
                  f"Changing chilled water loop setpoint for '#{chilled_water_loop.name()}' to '#{chw_temp_sch.name()}' to account for the radiant system.")

    # default temperature controls for radiant system
    zn_radiant_htg_dsgn_temp_f = 68.0
    zn_radiant_htg_dsgn_temp_c = openstudio.convert(zn_radiant_htg_dsgn_temp_f, 'F', 'C').get()
    zn_radiant_clg_dsgn_temp_f = 74.0
    zn_radiant_clg_dsgn_temp_c = openstudio.convert(zn_radiant_clg_dsgn_temp_f, 'F', 'C').get()

    htg_control_temp_sch = add_constant_schedule_ruleset(openstudio_model, zn_radiant_htg_dsgn_temp_c, 
                                                         name = f"Zone Radiant Loop Heating Threshold Temperature Schedule - #{round(zn_radiant_htg_dsgn_temp_c, 2)}C")
    clg_control_temp_sch = add_constant_schedule_ruleset(openstudio_model, zn_radiant_clg_dsgn_temp_c, 
                                                         name = f"Zone Radiant Loop Cooling Threshold Temperature Schedule - #{round(zn_radiant_clg_dsgn_temp_c, 2)}C")
    throttling_range_f = 4.0 # 2 degF on either side of control temperature
    throttling_range_c = openstudio.convert(throttling_range_f, 'F', 'C').get()

    # create preset availability schedule for radiant loop
    radiant_avail_sch = osmod.ScheduleRuleset(openstudio_model)
    radiant_avail_sch.setName('Radiant System Availability Schedule')

    if radiant_lockout == False:
        rad_avail_lwr = radiant_availability_type.lower()
        if rad_avail_lwr == 'all_day':
            start_hour = 24
            start_minute = 0
            end_hour = 24
            end_minute = 0
        elif rad_avail_lwr == 'afternoon_shutoff':
            start_hour = 15
            start_minute = 0
            end_hour = 22
            end_minute = 0
        elif rad_avail_lwr == 'precool':
            start_hour = 10
            start_minute = 0
            end_hour = 22
            end_minute = 0
        elif rad_avail_lwr == 'occupancy':
            start_hour = int(model_occ_hr_end)
            start_minute = int(((model_occ_hr_end % 1) * 60))
            end_hour = int(model_occ_hr_start)
            end_minute = int((model_occ_hr_start % 1) * 60)
        else:
            print('openstudio.Model.Model', 
                  f"Unsupported radiant availability preset '#{radiant_availability_type}'. Defaulting to all day operation.")
            start_hour = 24
            start_minute = 0
            end_hour = 24
            end_minute = 0

    # create custom availability schedule for radiant loop
    if radiant_lockout:
        start_hour = int(radiant_lockout_start_time)
        start_minute = int((radiant_lockout_start_time % 1) * 60)
        end_hour = int(radiant_lockout_end_time)
        end_minute = int((radiant_lockout_end_time % 1) * 60)

    # create availability schedules
    if end_hour > start_hour:
        radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, start_hour, start_minute, 0), 1.0)
        radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, end_hour, end_minute, 0), 0.0)
        if end_hour < 24: radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)
    elif start_hour > end_hour:
        radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, end_hour, end_minute, 0), 0.0)
        radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, start_hour, start_minute, 0), 1.0)
        if start_hour < 24: radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 0.0)
    else:
        radiant_avail_sch.defaultDaySchedule().addValue(openstudio.Time(0, 24, 0, 0), 1.0)

    # convert to a two-pipe system if required
    if two_pipe_system:
        model_two_pipe_loop(openstudio_model, hot_water_loop, chilled_water_loop,
                            control_strategy = two_pipe_control_strategy,
                            lockout_temperature = two_pipe_lockout_temperature,
                            thermal_zones = thermal_zones)

    # add supply water temperature control if enabled
    if plant_supply_water_temperature_control:
        # add supply water temperature for heating plant loop
        add_plant_supply_water_temperature_control(openstudio_model, hot_water_loop, 
                                                   control_strategy = plant_supply_water_temperature_control_strategy, 
                                                   sp_at_oat_low = hwsp_at_oat_low, oat_low = hw_oat_low,
                                                   sp_at_oat_high = hwsp_at_oat_high, oat_high = hw_oat_high, thermal_zones = thermal_zones)

        # add supply water temperature for cooling plant loop
        add_plant_supply_water_temperature_control(openstudio_model, chilled_water_loop, 
                                                   control_strategy = plant_supply_water_temperature_control_strategy,
                                                   sp_at_oat_low = chwsp_at_oat_low, oat_low = chw_oat_low,
                                                   sp_at_oat_high = chwsp_at_oat_high, oat_high = chw_oat_high, thermal_zones = thermal_zones)

    # make a low temperature radiant loop for each zone
    radiant_loops = []
    for zone in thermal_zones:
        print('openstudio.Model.Model', f"Adding radiant loop for #{zone.name()}.")
        if ':' in zone.name():
            print('openstudio.Model.Model', f"Thermal zone '{zone.name()}' has a restricted character ':' in the name and will not work with some EMS and output reporting objects. Please rename the zone.")

        # create radiant coils
        if hot_water_loop:
            radiant_loop_htg_coil = osmod.CoilHeatingLowTempRadiantVarFlow(openstudio_model, htg_control_temp_sch)
            radiant_loop_htg_coil.setName(f"{zone.name()} Radiant Loop Heating Coil")
            radiant_loop_htg_coil.setHeatingControlThrottlingRange(throttling_range_c)
            hot_water_loop.addDemandBranchForComponent(radiant_loop_htg_coil)
        else:
            print('openstudio.Model.Model', 'Radiant loops require a hot water loop, but none was provided.')

        if chilled_water_loop:
            radiant_loop_clg_coil = osmod.CoilCoolingLowTempRadiantVarFlow(openstudio_model, clg_control_temp_sch)
            radiant_loop_clg_coil.setName(f"{zone.name()} Radiant Loop Cooling Coil")
            radiant_loop_clg_coil.setCoolingControlThrottlingRange(throttling_range_c)
            chilled_water_loop.addDemandBranchForComponent(radiant_loop_clg_coil)
        else:
            print('openstudio.Model.Model', 'Radiant loops require a chilled water loop, but none was provided.')

        radiant_loop = osmod.ZoneHVACLowTempRadiantVarFlow(openstudio_model,radiant_avail_sch, radiant_loop_htg_coil, radiant_loop_clg_coil)

        # assign internal source construction to floors in zone
        for space in zone.spaces():
            for surface in space.surfaces():
                if radiant_type == 'floor':
                    if surface.surfaceType == 'Floor':
                        if surface.outsideBoundaryCondition == 'Ground':
                            surface.setConstruction(radiant_ground_slab_construction)
                        elif surface.outsideBoundaryCondition == 'Outdoors':
                            surface.setConstruction(radiant_exterior_slab_construction)
                        else: # interior floor
                            surface.setConstruction(radiant_interior_floor_slab_construction)

                        # also assign construciton to adjacent surface
                        adjacent_surface = surface.adjacentSurface().get()
                        adjacent_surface.setConstruction(rev_radiant_interior_floor_slab_construction)

                elif radiant_type == 'ceiling':
                    if surface.surfaceType == 'RoofCeiling':
                        if surface.outsideBoundaryCondition == 'Outdoors':
                            surface.setConstruction(radiant_ceiling_slab_construction)
                        else: # interior ceiling
                            surface.setConstruction(radiant_interior_ceiling_slab_construction)

                        # also assign construciton to adjacent surface
                        adjacent_surface = surface.adjacentSurface().get()
                        adjacent_surface.setConstruction(rev_radiant_interior_ceiling_slab_construction)

        # radiant loop surfaces
        radiant_loop.setName(f"{zone.name()} Radiant Loop")
        if radiant_type == 'floor':
            radiant_loop.setRadiantSurfaceType('Floors')
        elif radiant_type == 'ceiling':
            radiant_loop.setRadiantSurfaceType('Ceilings')

        # radiant loop layout details
        radiant_loop.setHydronicTubingInsideDiameter(0.015875) # 5/8 in. ID, 3/4 in. OD
        # @todo include a method to determine tubing length in the zone
        # loop_length = 7*zone.floorArea
        # radiant_loop.setHydronicTubingLength()
        radiant_loop.setNumberofCircuits('CalculateFromCircuitLength')
        radiant_loop.setCircuitLength(106.7)

        # radiant loop temperature controls
        radiant_loop.setTemperatureControlType(radiant_temperature_control_type)

        # radiant loop setpoint temperature response
        radiant_loop.setSetpointControlType(radiant_setpoint_control_type)
        radiant_loop.addToThermalZone(zone)
        radiant_loops.append(radiant_loop)

        # rename nodes before adding EMS code
        rename_plant_loop_nodes(openstudio_model)

        # set radiant loop controls
        ctrl_lwr = control_strategy.lower()
        if ctrl_lwr == 'proportional_control':
            # slab setpoint varies based on previous day zone conditions
            add_radiant_proportional_controls(openstudio_model, zone, radiant_loop, 
                                              radiant_temperature_control_type = radiant_temperature_control_type,
                                              use_zone_occupancy_for_control = use_zone_occupancy_for_control,
                                              occupied_percentage_threshold = occupied_percentage_threshold,
                                              model_occ_hr_start = model_occ_hr_start,
                                              model_occ_hr_end = model_occ_hr_end,
                                              proportional_gain = proportional_gain,
                                              switch_over_time = switch_over_time)
        elif ctrl_lwr == 'oa_based_control':
            # slab setpoint varies based on outdoor weather
            add_radiant_basic_controls(openstudio_model, zone, radiant_loop, radiant_temperature_control_type = radiant_temperature_control_type, 
                                       slab_setpoint_oa_control = True, switch_over_time = switch_over_time, slab_sp_at_oat_low = slab_sp_at_oat_low, slab_oat_low = slab_oat_low, 
                                       slab_sp_at_oat_high = slab_sp_at_oat_high, slab_oat_high = slab_oat_high)
        elif ctrl_lwr == 'constant_control':
            # constant slab setpoint control
            add_radiant_basic_controls(openstudio_model, zone, radiant_loop, radiant_temperature_control_type = radiant_temperature_control_type, slab_setpoint_oa_control = False,
                                       switch_over_time = switch_over_time, slab_sp_at_oat_low = slab_sp_at_oat_low, slab_oat_low = slab_oat_low, 
                                       slab_sp_at_oat_high = slab_sp_at_oat_high, slab_oat_high = slab_oat_high)
    return radiant_loops

def thermal_zone_outdoor_airflow_rate(thermal_zone: osmod.ThermalZone) -> float:
    """
    Calculates the zone outdoor airflow requirement (Voz) based on the inputs in the DesignSpecification:OutdoorAir objects in all spaces in the zone.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:thermal_zone_outdoor_airflow_rate)

    Parameters
    ----------
    thermal_zone : osmod.ThermalZone
        thermal zone.
    
    Returns
    -------
    airflow_rate : float
        the zone outdoor air flow rate in cubic meters per second (m^3/s)
    """
    tot_oa_flow_rate = 0.0

    spaces = thermal_zone.spaces()

    sum_floor_area = 0.0
    sum_number_of_people = 0.0
    sum_volume = 0.0

    # Variables for merging outdoor air
    sum_oa_for_people = 0.0
    sum_oa_for_floor_area = 0.0
    sum_oa_rate = 0.0
    sum_oa_for_volume = 0.0

    # Find common variables for the new space
    for space in spaces:
        floor_area = space.floorArea()
        sum_floor_area += floor_area

        number_of_people = space.numberOfPeople()
        sum_number_of_people += number_of_people

        volume = space.volume()
        sum_volume += volume

        dsn_oa = space.designSpecificationOutdoorAir()
        if dsn_oa.empty() == True:
            break

        dsn_oa = dsn_oa.get()

        # compute outdoor air rates in case we need them
        oa_for_people = number_of_people * dsn_oa.outdoorAirFlowperPerson()
        oa_for_floor_area = floor_area * dsn_oa.outdoorAirFlowperFloorArea()
        oa_rate = dsn_oa.outdoorAirFlowRate()
        oa_for_volume = volume * dsn_oa.outdoorAirFlowAirChangesperHour() / 3600

        # First check if this space uses the Maximum method and other spaces do not
        if dsn_oa.outdoorAirMethod() == 'Maximum':
            sum_oa_rate += max([oa_for_people, oa_for_floor_area, oa_rate, oa_for_volume])
        elif dsn_oa.outdoorAirMethod() == 'Sum':
            sum_oa_for_people += oa_for_people
            sum_oa_for_floor_area += oa_for_floor_area
            sum_oa_rate += oa_rate
            sum_oa_for_volume += oa_for_volume

    tot_oa_flow_rate += sum_oa_for_people
    tot_oa_flow_rate += sum_oa_for_floor_area
    tot_oa_flow_rate += sum_oa_rate
    tot_oa_flow_rate += sum_oa_for_volume

    # Convert to cfm
    tot_oa_flow_rate_cfm = openstudio.convert(tot_oa_flow_rate, 'm^3/s', 'cfm').get()

    print('openstudio.Standards.ThermalZone', f"For #{thermal_zone.name()}, design min OA = #{tot_oa_flow_rate_cfm} cfm.")

    return tot_oa_flow_rate

def add_doas(openstudio_model: osmod, thermal_zones: list[osmod.ThermalZone], system_name: str = None, doas_type: str = 'DOASCV', 
             doas_control_strategy: str = 'NeutralSupplyAir', hot_water_loop: osmod.PlantLoop = None, chilled_water_loop: osmod.PlantLoop = None,
             hvac_op_sch: str = None, min_oa_sch: str = None, min_frac_oa_sch: str = None, fan_maximum_flow_rate: float = None,
             econo_ctrl_mthd: str = 'NoEconomizer', include_exhaust_fan: bool = True, demand_control_ventilation: bool = False, 
             clg_dsgn_sup_air_temp: float = 15.6, htg_dsgn_sup_air_temp: float = 21.1) -> osmod.AirLoopHVAC:
    """
    Creates a DOAS system with terminal units for each zone.
    It is a translation of the this function (It is a translation of the this function (It is a translation of the this function (https://www.rubydoc.info/gems/openstudio-standards/Standard:model_add_doas)
    
    Parameters
    ----------
    openstudio_model : osmod
        openstudio model object.
    
    thermal_zones : list[osmod.ThermalZone]
        array of zones to connect to this system
    
    system_name : str, optional
        the name of the system, or nil in which case it will be defaulted.

    doas_type : str, optional
        DOASCV or DOASVAV, determines whether the DOAS is operated at scheduled, constant flow rate, or airflow is variable to allow for economizing or demand controlled ventilation

    doas_control_strategy : str, optional
        DOAS control strategy. Default to 'NeutralSupplyAir'

    hot_water_loop : osmod.PlantLoop, optional
        hot water loop to connect to heating and zone fan coils. Defaults to None
    
    chilled_water_loop : osmod.PlantLoop, optional
        chilled water loop to connect to cooling coil. defaults to None

    hvac_op_sch : str, optional
        name of the HVAC operation schedule, default is always on
    
    min_oa_sch : str, optional
        name of the minimum outdoor air schedule, default is always on

    min_frac_oa_sch : str, optional
       name of the minimum fraction of outdoor air schedule, default is always on
    
    fan_maximum_flow_rate : float, optional
        fan maximum flow rate in cfm, default is autosize
    
    econo_ctrl_mthd : str, optional
        economizer control type, defaults to: 'NoEconomizer'. Default is Fixed Dry Bulb If enabled, the DOAS will be sized for twice the ventilation minimum to allow economizing

    include_exhaust_fan : bool, optional
        if true, include an exhaust fan
    
    demand_control_ventilation : bool, optional
        default to False. If True, demand control ventilation is enabled.
    
    clg_dsgn_sup_air_temp : float, optional
        design cooling supply air temperature in degC, default 15.6C
    
    htg_dsgn_sup_air_temp : float, optional
        design heating supply air temperature in degC, default 21.1C

    Returns
    -------
    doas_hvac : osmod.AirLoopHVAC
        the resultant doas system.
    """
    # Check the total OA requirement for all zones on the system
    tot_oa_req = 0
    for zone in thermal_zones:
        tot_oa_req += thermal_zone_outdoor_airflow_rate(zone)

    # If the total OA requirement is zero do not add the DOAS system because the simulations will fail
    if tot_oa_req == 0:
        print('openstudio.Model.Model', f"Not adding DOAS system for #{len(thermal_zones)} zones because combined OA requirement for all zones is zero.")
        return False
    
    print('openstudio.Model.Model', f"Adding DOAS system for #{len(thermal_zones)} zones.")

    # create a DOAS air loop
    air_loop = osmod.AirLoopHVAC(openstudio_model)
    if system_name == None:
        air_loop.setName(f"#{len(thermal_zones)} Zone DOAS")
    else:
        air_loop.setName(system_name)

    # set availability schedule
    if hvac_op_sch == None:
        hvac_op_sch = openstudio_model.alwaysOnDiscreteSchedule()
    else:
        hvac_op_sch = add_schedule(openstudio_model, hvac_op_sch)

    # modify system sizing properties
    sizing_system = air_loop.sizingSystem()
    sizing_system.setTypeofLoadtoSizeOn('VentilationRequirement')
    sizing_system.setAllOutdoorAirinCooling(True)
    sizing_system.setAllOutdoorAirinHeating(True)
    # set minimum airflow ratio to 1.0 to avoid under-sizing heating coil
    if openstudio_model.version() < openstudio.VersionString('2.7.0'):
        sizing_system.setMinimumSystemAirFlowRatio(1.0)
    else:
        sizing_system.setCentralHeatingMaximumSystemAirFlowRatio(1.0)

    sizing_system.setSizingOption('Coincident')
    sizing_system.setCentralCoolingDesignSupplyAirTemperature(clg_dsgn_sup_air_temp)
    sizing_system.setCentralHeatingDesignSupplyAirTemperature(htg_dsgn_sup_air_temp)

    if doas_type == 'DOASCV':
        supply_fan = create_fan_by_name(openstudio_model, 'Constant_DOAS_Fan', fan_name = 'DOAS Supply Fan', end_use_subcategory = 'DOAS Fans')
    else: # 'DOASVAV'
        supply_fan = create_fan_by_name(openstudio_model, 'Variable_DOAS_Fan', fan_name = 'DOAS Supply Fan', end_use_subcategory = 'DOAS Fans')

    supply_fan.setAvailabilitySchedule(openstudio_model.alwaysOnDiscreteSchedule())
    if fan_maximum_flow_rate != None: supply_fan.setMaximumFlowRate(openstudio.convert(fan_maximum_flow_rate, 'cfm', 'm^3/s').get())
    supply_fan.addToNode(air_loop.supplyInletNode())

    # create heating coil
    if hot_water_loop == None:
        # electric backup heating coil
        create_coil_heating_electric(openstudio_model, air_loop_node = air_loop.supplyInletNode(), name = f"#{air_loop.name()} Backup Htg Coil")
        # heat pump coil
        create_coil_heating_dx_single_speed(openstudio_model, air_loop_node = air_loop.supplyInletNode(), name = f"#{air_loop.name()} Htg Coil")
    else:
        create_coil_heating_water(openstudio_model, hot_water_loop, air_loop_node = air_loop.supplyInletNode(),
                                  name = f"#{air_loop.name()} Htg Coil", controller_convergence_tolerance = 0.0001)

    # could add a humidity controller here set to limit supply air to a 16.6C/62F dewpoint
    # the default outdoor air reset to 60F prevents exceeding this dewpoint in all ASHRAE climate zones
    # the humidity controller needs a DX coil that can control humidity, e.g. CoilCoolingDXTwoStageWithHumidityControlMode
    # max_humidity_ratio_sch = add_constant_schedule_ruleset(openstudio_model, 0.012, name = "0.012 Humidity Ratio Schedule", 
    #                                                        sch_type_limit = "Humidity Ratio")
    # sat_oa_reset = osmod.SetpointManagerScheduled(openstudio_model, max_humidity_ratio_sch)
    # sat_oa_reset.setName(f"#{air_loop.name.to_s} Humidity Controller")
    # sat_oa_reset.setControlVariable('MaximumHumidityRatio')
    # sat_oa_reset.addToNode(air_loop.supplyInletNode())

    # create cooling coil
    if chilled_water_loop.nil == None:
        create_coil_cooling_dx_two_speed(openstudio_model, air_loop_node = air_loop.supplyInletNode(),
                                        name = f"#{air_loop.name()} 2spd DX Clg Coil")
    else:
        create_coil_cooling_water(openstudio_model, chilled_water_loop, air_loop_node = air_loop.supplyInletNode(), 
                                  name = f"#{air_loop.name()} Clg Coil")

    # minimum outdoor air schedule
    if min_oa_sch != None:
        min_oa_sch = add_schedule(openstudio_model, min_oa_sch)

    # minimum outdoor air fraction schedule
    if min_frac_oa_sch == None:
        min_frac_oa_sch = openstudio_model.alwaysOnDiscreteSchedule()
    else:
        min_frac_oa_sch = add_schedule(openstudio_model, min_frac_oa_sch)

    # create controller outdoor air
    controller_oa = osmod.ControllerOutdoorAir(openstudio_model)
    controller_oa.setName(f"#{air_loop.name()} Outdoor Air Controller")
    controller_oa.setEconomizerControlType(econo_ctrl_mthd)
    controller_oa.setMinimumLimitType('FixedMinimum')
    controller_oa.autosizeMinimumOutdoorAirFlowRate()
    if min_oa_sch != None: controller_oa.setMinimumOutdoorAirSchedule(min_oa_sch)
    controller_oa.setMinimumFractionofOutdoorAirSchedule(min_frac_oa_sch)
    controller_oa.resetEconomizerMinimumLimitDryBulbTemperature()
    controller_oa.resetEconomizerMaximumLimitDryBulbTemperature()
    controller_oa.resetEconomizerMaximumLimitEnthalpy()
    controller_oa.resetMaximumFractionofOutdoorAirSchedule()
    controller_oa.setHeatRecoveryBypassControlType('BypassWhenWithinEconomizerLimits')
    controller_mech_vent = controller_oa.controllerMechanicalVentilation()
    controller_mech_vent.setName(f"#{air_loop.name()} Mechanical Ventilation Controller")
    if demand_control_ventilation: controller_mech_vent.setDemandControlledVentilation(True)
    controller_mech_vent.setSystemOutdoorAirMethod('ZoneSum')

    # create outdoor air system
    oa_system = osmod.AirLoopHVACOutdoorAirSystem(openstudio_model, controller_oa)
    oa_system.setName(f"#{air_loop.name()} OA System")
    oa_system.addToNode(air_loop.supplyInletNode())

    # create an exhaust fan
    if include_exhaust_fan:
        if doas_type == 'DOASCV':
            exhaust_fan = create_fan_by_name(openstudio_model, 'Constant_DOAS_Fan', fan_name = 'DOAS Exhaust Fan', end_use_subcategory = 'DOAS Fans')
        else: # 'DOASVAV'
            exhaust_fan = create_fan_by_name(openstudio_model, 'Variable_DOAS_Fan', fan_name = 'DOAS Exhaust Fan', end_use_subcategory = 'DOAS Fans')

        # set pressure rise 1.0 inH2O lower than supply fan, 1.0 inH2O minimum
        exhaust_fan_pressure_rise = supply_fan.pressureRise() - openstudio.convert(1.0, 'inH_{2}O', 'Pa').get()
        if exhaust_fan_pressure_rise < openstudio.convert(1.0, 'inH_{2}O', 'Pa').get():
            exhaust_fan_pressure_rise = openstudio.convert(1.0, 'inH_{2}O', 'Pa').get() 
        exhaust_fan.setPressureRise(exhaust_fan_pressure_rise)
        exhaust_fan.addToNode(air_loop.supplyInletNode())

    # create a setpoint manager
    sat_oa_reset = osmod.SetpointManagerOutdoorAirReset(openstudio_model)
    sat_oa_reset.setName(f"#{air_loop.name()} SAT Reset")
    sat_oa_reset.setControlVariable('Temperature')
    sat_oa_reset.setSetpointatOutdoorLowTemperature(htg_dsgn_sup_air_temp)
    sat_oa_reset.setOutdoorLowTemperature(openstudio.convert(55.0, 'F', 'C').get())
    sat_oa_reset.setSetpointatOutdoorHighTemperature(clg_dsgn_sup_air_temp)
    sat_oa_reset.setOutdoorHighTemperature(openstudio.convert(70.0, 'F', 'C').get())
    sat_oa_reset.addToNode(air_loop.supplyOutletNode())

    # set air loop availability controls and night cycle manager, after oa system added
    air_loop.setAvailabilitySchedule(hvac_op_sch)
    air_loop.setNightCycleControlType('CycleOnAnyZoneFansOnly')

    # add thermal zones to airloop
    for zone in thermal_zones:
        # skip zones with no outdoor air flow rate
        if thermal_zone_outdoor_airflow_rate(zone) <= 0:
            print('openstudio.Model.Model', f"---#{zone.name()} has no outdoor air flow rate and will not be added to #{air_loop.name()}")
            continue

        print('openstudio.Model.Model', f"---adding #{zone.name()} to #{air_loop.name()}")

        # make an air terminal for the zone
        if doas_type == 'DOASCV':
            air_terminal = osmod.AirTerminalSingleDuctUncontrolled(openstudio_model, openstudio_model.alwaysOnDiscreteSchedule())
        elif doas_type == 'DOASVAVReheat':
            # Reheat coil
            if hot_water_loop == None:
                rht_coil = create_coil_heating_electric(openstudio_model, name = f"#{zone.name()} Electric Reheat Coil")
            else:
                rht_coil = create_coil_heating_water(openstudio_model, hot_water_loop, name = f"#{zone.name()} Reheat Coil")

            # VAV reheat terminal
            air_terminal = osmod.AirTerminalSingleDuctVAVReheat(openstudio_model, openstudio_model.alwaysOnDiscreteSchedule(), rht_coil)
            if openstudio_model.version() < openstudio.VersionString('3.0.1'):
                air_terminal.setZoneMinimumAirFlowMethod('Constant')
            else:
                air_terminal.setZoneMinimumAirFlowInputMethod('Constant')

            if demand_control_ventilation: air_terminal.setControlForOutdoorAir(True)
        else: # 'DOASVAV'
            air_terminal = osmod.AirTerminalSingleDuctVAVNoReheat(openstudio_model, openstudio_model.alwaysOnDiscreteSchedule())
            if openstudio_model.version() < openstudio.VersionString('3.0.1'):
                air_terminal.setZoneMinimumAirFlowMethod('Constant')
            else:
                air_terminal.setZoneMinimumAirFlowInputMethod('Constant')

            air_terminal.setConstantMinimumAirFlowFraction(0.1)
            if demand_control_ventilation: air_terminal.setControlForOutdoorAir(True) 

        air_terminal.setName(f"#{zone.name()} Air Terminal")

        # attach new terminal to the zone and to the airloop
        air_loop.multiAddBranchForZone(zone, air_terminal.to_HVACComponent().get())

        # ensure the DOAS takes priority, so ventilation load is included when treated by other zonal systems
        # From EnergyPlus I/O reference:
        # "For situations where one or more equipment types has limited capacity or limited control capability, order the
        #  sequence so that the most controllable piece of equipment runs last. For example, with a dedicated outdoor air
        #  system (DOAS), the air terminal for the DOAS should be assigned Heating Sequence = 1 and Cooling Sequence = 1.
        #  Any other equipment should be assigned sequence 2 or higher so that it will see the net load after the DOAS air
        #  is added to the zone."
        zone.setCoolingPriority(air_terminal.to_ModelObject().get(), 1)
        zone.setHeatingPriority(air_terminal.to_ModelObject().get(), 1)

        # set the cooling and heating fraction to zero so that if DCV is enabled,
        # the system will lower the ventilation rate rather than trying to meet the heating or cooling load.
        if openstudio_model.version() < openstudio.VersionString('2.8.0'):
            if demand_control_ventilation:
                print('openstudio.Model.Model', 'Unable to add DOAS with DCV to model because the setSequentialCoolingFraction method is not available in OpenStudio versions less than 2.8.0.')
            else:
                print('openstudio.Model.Model', 'OpenStudio version is less than 2.8.0.  The DOAS system will not be able to have DCV if changed at a later date.')

        else:
            zone.setSequentialCoolingFraction(air_terminal.to_ModelObject().get(), 0.0)
            zone.setSequentialHeatingFraction(air_terminal.to_ModelObject().get(), 0.0)

        # if economizing, override to meet cooling load first with doas supply
        if econo_ctrl_mthd != 'NoEconomizer':
            zone.setSequentialCoolingFraction(air_terminal.to_ModelObject().get(), 1.0)

        # DOAS sizing
        sizing_zone = zone.sizingZone
        sizing_zone.setAccountforDedicatedOutdoorAirSystem(True)
        sizing_zone.setDedicatedOutdoorAirSystemControlStrategy(doas_control_strategy)
        sizing_zone.setDedicatedOutdoorAirLowSetpointTemperatureforDesign(clg_dsgn_sup_air_temp)
        sizing_zone.setDedicatedOutdoorAirHighSetpointTemperatureforDesign(htg_dsgn_sup_air_temp)

    return air_loop

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

def get_osmod_planar_srf_info(osmod_srf: osmod.PlanarSurface):
    '''
    Extract geometry and material information about the osmod PlanarSurface.

    Parameters
    ----------
    osmod_srf : osmod.PlanarSurface
        the openstudio surface to extract information from.

    Returns
    -------
    dict
        - dictionary with the following keys
        - name: name of the surface
        - vertices: list(shape(number of vertices, 3)), vertices of the surface.
        - construction: handle of the construction of the surface
    '''
    srf_dict = {}
    srf_name = osmod_srf.nameString()
    verts = osmod_srf.vertices()
    xyzs = []
    for vert in verts:
        xyz = [vert.x(), vert.y(), vert.z()]
        xyzs.append(xyz)
    
    srf_dict['name'] = srf_name
    srf_dict['vertices'] = xyzs
    const = osmod_srf.construction()
    if not const.empty():
        const = const.get()
        const_handle = str(const.handle())
        srf_dict['construction'] = const_handle
    else:
        srf_dict['construction'] = None
    
    return srf_dict

def get_osmod_srf_info(osmod_srf: osmod.Surface):
    '''
    Extract geometry and material information about the osmod surface.

    Parameters
    ----------
    osmod_srf : osmod.Surface
        the openstudio surface to extract information from.

    Returns
    -------
    dict
        - dictionary with the following keys
        - name: name of the surface
        - vertices: list(shape(number of vertices, 3)), vertices of the surface.
        - construction: handle of the construction of the surface
        - type: type of the surface
    '''
    srf_dict = get_osmod_planar_srf_info(osmod_srf)
    srf_type = osmod_srf.surfaceType()
    srf_dict['type'] = srf_type

    return srf_dict
        
def get_osmod_subsrf_info(osmod_srf: osmod.SubSurface):
    '''
    Extract geometry and material information about the osmod surface.

    Parameters
    ----------
    osmod_srf : osmod.PlanarSurface
        the openstudio surface to extract information from.

    Returns
    -------
    dict
        - dictionary with the following keys
        - name: name of the surface
        - vertices: list(shape(number of vertices, 3)), vertices of the surface.
        - construction: handle of the construction of the surface
        - type: type of the surface
        - host: handle of the host surface
    '''
    srf_dict = get_osmod_planar_srf_info(osmod_srf)
    srf_type = osmod_srf.subSurfaceType()

    srf_dict['type'] = srf_type

    host = osmod_srf.surface()
    if not host.empty():
        host = host.get()
        host_handle = str(host.handle())
        srf_dict['host'] = host_handle

    return srf_dict

def get_osmod_material_info(osmodel: osmod) -> list[dict]:
    '''
    Extract material information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the material is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name of the material
        - thickness: thickness of the material in meter
        - pset: pset schema to be translated to ifc pset from ../data/json/osmod_material_schema.json
    '''
    mat_pset_path = PSET_DATA_DIR.joinpath('osmod_material_schema.json')
    mat_pset_template = ifcopenshell_utils.get_default_pset(mat_pset_path, template_only=True)
    materials = osmod.getMaterials(osmodel)
    mat_dicts = {}
    for material in materials:
        mat_pset = copy.deepcopy(mat_pset_template)
        handle = str(material.handle())
        name = material.nameString()
        thickness = material.thickness()
        if not material.to_StandardOpaqueMaterial().empty():
            to_mat = material.to_StandardOpaqueMaterial().get()
            mat_pset['Roughness']['value'] = str(to_mat.roughness())
            mat_pset['Conductivity']['value'] = to_mat.conductivity()
            mat_pset['Density']['value'] = to_mat.conductivity()
            mat_pset['SpecificHeat']['value'] = to_mat.specificHeat()
            mat_pset['ThermalAbsorptance']['value'] = to_mat.thermalAbsorptance()
            mat_pset['SolarAbsorptance']['value'] = to_mat.solarAbsorptance()
            mat_pset['VisibleAbsorptance']['value'] = to_mat.visibleAbsorptance()
        elif not material.to_MasslessOpaqueMaterial().empty():
            to_mat = material.to_MasslessOpaqueMaterial().get()
            mat_pset['Roughness']['value'] = str(to_mat.roughness())
            mat_pset['ThermalResistance']['value'] = to_mat.thermalResistance()
            if not to_mat.thermalAbsorptance().empty():
                mat_pset['ThermalAbsorptance']['value'] = to_mat.thermalAbsorptance().get()
            if not to_mat.solarAbsorptance().empty():
                mat_pset['SolarAbsorptance']['value'] = to_mat.solarAbsorptance().get()
            if not to_mat.visibleAbsorptance().empty():
                mat_pset['VisibleAbsorptance']['value'] = to_mat.visibleAbsorptance().get()
        elif not material.to_SimpleGlazing().empty():
            to_mat = material.to_SimpleGlazing().get()
            mat_pset['UFactor']['value'] = to_mat.uFactor()
            mat_pset['SolarHeatGainCoefficient']['value'] = to_mat.solarHeatGainCoefficient()
            if not to_mat.visibleTransmittance().empty(): 
                mat_pset['VisibleTransmittance']['value'] = to_mat.visibleTransmittance().get()
        #TODO: include all material types from osmod
        mat_dict = {'name': name, 'thickness': thickness, 'pset': mat_pset}
        mat_dicts[handle] = mat_dict
    return mat_dicts

def get_osmod_construction_info(osmodel: osmod) -> dict:
    '''
    Extract construction information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the construction is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name of the construction
        - mat_names: list of material names
        - mat_handles: list of material handles
    '''
    const_bases = osmod.getConstructionBases(osmodel)
    const_dicts = {}
    for const_base in const_bases:
        const_dict = {}
        name = const_base.nameString()
        handle = str(const_base.handle())
        const_dict['name'] = name
        if not const_base.to_LayeredConstruction().empty():
            lay_const = const_base.to_LayeredConstruction().get()
            mats = lay_const.layers()
            const_dict['mat_names'] = []
            const_dict['mat_handles'] = []
            for mat in mats:
                mat_handle = str(mat.handle())
                mat_name = mat.nameString()
                const_dict['mat_names'].append(mat_name)
                const_dict['mat_handles'].append(mat_handle)
        const_dicts[handle] = const_dict
    return const_dicts

def get_osmod_space_based_info(osmod_spaces: list[osmod.Space] | list[osmod.SpaceType], pset_template: dict) -> dict:
    '''
    Extract space related information from the openstudio model.

    Parameters
    ----------
    osmod_space : list[osmod.Space] | list[osmod.SpaceType]
        The space or spacetype object to extract information from.

    pset_template : dict
        pset schema to be translated to ifc pset from ../data/json/osmod_space_schema.json or ../data/json/osmod_spacetype_schema.json

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the space is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name 
        - pset: pset schema to be translated to ifc pset from ../data/json/osmod_space_schema.json or ../data/json/osmod_spacetype_schema.json
    '''
    space_dicts = {}
    for space in osmod_spaces:
        pset = copy.deepcopy(pset_template)
        name = space.nameString()
        handle = str(space.handle())
        spec_out_air = space.designSpecificationOutdoorAir()
        if not spec_out_air.empty():
            spec_out_air = spec_out_air.get()
            pset['OutdoorAirFlowperPerson']['value'] = spec_out_air.outdoorAirFlowperPerson()
            pset['OutdoorAirFlowperFloorArea']['value'] = spec_out_air.outdoorAirFlowperFloorArea()

        if not math.isinf(space.floorAreaPerPerson()): pset['FloorAreaPerPerson']['value'] = space.floorAreaPerPerson()
        if not math.isinf(space.lightingPowerPerFloorArea()): pset['LightingPowerPerFloorArea']['value'] = space.lightingPowerPerFloorArea()
        if not math.isinf(space.electricEquipmentPowerPerFloorArea()): 
            pset['ElectricEquipmentPowerPerFloorArea']['value'] = space.electricEquipmentPowerPerFloorArea()
            
        space_dict = {'name': name, 'pset': pset}
        space_dicts[handle] = space_dict
    
    return space_dicts

def get_osmod_space_info(osmodel: osmod) -> dict:
    '''
    Extract space information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the space is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name 
        - pset: pset schema to be translated to ifc pset from ../data/json/ifc_psets/osmod_space_schema.json
        - tzone: the thermal zone handle the space belongs to
        - spacetype: the spacetype handle of the space if any
        - story: the building story handle this space belongs to
        - surfaces: surface dictionaries index by their handles and 
            - within each dict has keys: name, vertices, construction, type 
        - sub_surfaces: sub_surface dictionaries index by their handles and 
            - within each dict has keys: name, vertices, construction, type, host  
    '''
    pset_path = PSET_DATA_DIR.joinpath('osmod_space_schema.json')
    pset_template = ifcopenshell_utils.get_default_pset(pset_path, template_only=True)
    spaces = osmod.getSpaces(osmodel)
    space_dicts = get_osmod_space_based_info(spaces, pset_template)
    for space in spaces:
        space_handle = str(space.handle())
        tzone = space.thermalZone()
        if not tzone.empty():
            tzone = tzone.get()
            tzone_handle = str(tzone.handle())
            space_dicts[space_handle]['tzone'] = tzone_handle
        sptype = space.spaceType()
        if not sptype.empty():
            sptype = sptype.get()
            sptype_handle = str(sptype.handle())
            space_dicts[space_handle]['spacetype'] = sptype_handle
        bldgstory = space.buildingStory()
        if not bldgstory.empty():
            bldgstory = bldgstory.get()
            bldgstory_handle = str(bldgstory.handle())
            space_dicts[space_handle]['story'] = bldgstory_handle
        srf_dicts = {}
        sub_srf_dicts = {}
        srfs = space.surfaces()
        for srf in srfs:
            srf_handle = str(srf.handle())
            srf_dict = get_osmod_srf_info(srf)
            srf_dicts[srf_handle] = srf_dict
            subsrfs = srf.subSurfaces()
            for subsrf in subsrfs:
                subsrf_handle = str(subsrf.handle())
                sub_srf_dict = get_osmod_subsrf_info(subsrf)
                sub_srf_dicts[subsrf_handle] = sub_srf_dict
        
        space_dicts[space_handle]['surfaces'] = srf_dicts
        space_dicts[space_handle]['sub_surfaces'] = sub_srf_dicts

    return space_dicts

def get_osmod_spacetype_info(osmodel: osmod) -> dict:
    '''
    Extract spacetype information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the spacetype is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name 
        - pset: pset schema to be translated to ifc pset from ../data/json/osmod_spacetype_schema.json
    '''
    pset_path = PSET_DATA_DIR.joinpath('osmod_spacetype_schema.json')
    pset_template = ifcopenshell_utils.get_default_pset(pset_path, template_only=True)
    spacetypes = osmod.getSpaceTypes(osmodel)
    spacetype_dicts = get_osmod_space_based_info(spacetypes, pset_template)
    return spacetype_dicts

def get_osmod_tzone_info(osmodel: osmod) -> dict:
    '''
    Extract thermal zone information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the thermal zone is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name
    '''
    tzones = osmod.getThermalZones(osmodel)
    tzone_dicts = {}
    for tzone in tzones:
        name = tzone.nameString()
        handle = str(tzone.handle())

        tzone_dict = {'name': name}
        tzone_dicts[handle] = tzone_dict

    return tzone_dicts

def get_osmod_story_info(osmodel: osmod) -> dict:
    '''
    Extract building story information from the openstudio model.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model to extract construction information from.

    Returns
    -------
    dict
        - nested dictionaries, the osmod handle of the thermal zone is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name
    '''
    stories = osmod.getBuildingStorys(osmodel)
    story_dicts = {}
    for story in stories:
        name = story.nameString()
        handle = str(story.handle())
        story_dict = {'name': name}
        story_dicts[handle] = story_dict

    return story_dicts

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