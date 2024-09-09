import math
import json
import copy
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from shutil import copytree

import geomie3d
import openstudio
from openstudio import model as osmod

import ifc_utils.ifcopenshell_utils as ifcopenshell_utils
from .. import settings

from ladybug.epw import EPW

PSET_DATA_DIR = settings.PSET_DATA_DIR

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

    # get climate zones
    czs = openstudio_model.getClimateZones()
    ash = czs.ashraeInstitutionName()
    czs.setClimateZone(ash, lb_epw.ashrae_climate_zone)

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

def g3dverts2ospt3d(g3dverts: list[geomie3d.topobj.Vertex]) -> list[openstudio.openstudioutilitiesgeometry.Point3d]:
    pt3ds = []
    for v in g3dverts:
        xyz = v.point.xyz
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
        measure_dir_orig = Path(measure_dir_orig).resolve()
        copytree(measure_dir_orig, measure_dir_dest, dirs_exist_ok=True)
        # set measurestep
        mstep = openstudio.MeasureStep(measure_dir_dest)
        mstep.setName(foldername)
        # mstep.setDescription(measure_folder['description'])
        # mstep.setModelerDescription(measure_folder['modeler_description'])
        if 'arguments' in measure_folder.keys():
            arguments = measure_folder['arguments']
            argument_items = arguments.items()
            for argument_item in argument_items:
                mstep.setArgument(argument_item[0], argument_item[1])

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
            mat_pset['Density']['value'] = to_mat.density()
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

if __name__ == '__main__':
    # print(std_dict)
    pressure_rise = openstudio.convert(1.33, "inH_{2}O", 'Pa').get()
    # print(pressure_rise)
    m = osmod.Model()
    sch = m.alwaysOnDiscreteSchedule()
    # print(sch)
    # sch = m.getScheduleRulesetByName('test')
    # print(m.version())