import sys
import json
import argparse
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.geom
from openstudio import model as osmod

import geomie3d
import ifc_utils.ifcopenshell_utils as ifcopenshell_utils
from .utils import openstudio_utils
from . import settings
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Convert IFC Models to OpenStudio Models")
 
    # defining arguments for parser object
    parser.add_argument('-i', '--ifc', type = str, 
                        metavar = 'FILE', 
                        help = 'The file path of the IFC to convert')
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE', default = None,
                        help = 'The file path of the OpenStudio result')

    parser.add_argument('-v', '--viz', action = 'store_true', default=False,
                        help = 'visualize the calculation procedure if turned on')
    
    parser.add_argument('-p', '--process', action = 'store_true', default=False,
                        help = 'turn it on if piping in ifc filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def choose_best_vt_constr(mat_layer_indxs: list[list[int]], mat_lib: dict) -> int:
    '''
    choose the right constructon based on best visible transmittance construction.

    Parameters
    ----------
    mat_layer_indxs: list[list[int]]
        the material layers from the construction library.

    mat_lib: dict
        the material JSON library
    
    Returns
    -------
    int
        the chosen index
    '''
    vt_ls = []
    for mli in mat_layer_indxs:
        glz_mat = mat_lib[str(mli[0])] # for simple glazing there are only one layer
        vt = glz_mat['visibletransmittance']
        vt_ls.append(vt)
    
    vt_idx = vt_ls.index(max(vt_ls))
    return vt_idx

def choose_thin_constr(mat_layer_indxs: list[list[int]], mat_lib: dict) -> int:
    '''
    choose the right constructon based on thinnest construction.

    Parameters
    ----------
    mat_layer_indxs: list[list[int]]
        the material layers from the construction library.

    mat_lib: dict
        the material JSON library
    
    Returns
    -------
    int
        the chosen index
    '''
    thk_ls = []
    for mli in mat_layer_indxs:
        constr_thk = 0
        for i in mli:
            thk = mat_lib[str(i)]['thickness']
            constr_thk += thk
        thk_ls.append(constr_thk)
    
    thin_idx = thk_ls.index(min(thk_ls))
    return thin_idx

def create_ossrf(osmodel: osmod, srf: geomie3d.topobj.Face, constr_dicts: dict, osspace: osmod.Space) -> list[osmod.Surface]:
    '''
    create openstudio surface.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model.

    srf: geomie3d.topobj.Face
        surface with the necessary attributes to convert into a openstudio model.

    constr_dicts: dict
        dictionary of all the osmod constructions.

    osspace: osmod.Space
        space the surface belongs to.

    Returns
    -------
    list[osmod.Surface]
        the openstudio surfaces
    '''
    ossrf_ls = []
    srf_attr = srf.attributes
    constr_id = srf_attr['construction_id']
    srf_type = srf_attr['type']
    srf_name = srf_attr['name']
    osenvlp_constr = constr_dicts[constr_id]
    are_convex = geomie3d.calculate.are_polygon_faces_convex([srf])[0]
    if are_convex:
        vs = geomie3d.get.vertices_frm_face(srf)
        pt3ds = openstudio_utils.g3dverts2ospt3d(vs)
        ossrf = osmod.Surface(pt3ds, osmodel)
        ossrf.setSpace(osspace)
        ossrf.setConstruction(osenvlp_constr)
        ossrf.setName(srf_name)
        # ossrf.setSurfaceType(srf_type)
        ossrf_ls.append(ossrf)
    else:
        tri_faces = geomie3d.modify.triangulate_face(srf)
        for cnt,tri in enumerate(tri_faces):
            vs = geomie3d.get.vertices_frm_face(tri)
            pt3ds = openstudio_utils.g3dverts2ospt3d(vs)
            ossrf = osmod.Surface(pt3ds, osmodel)
            ossrf.setSpace(osspace)
            ossrf.setConstruction(osenvlp_constr)
            ossrf.setName(srf_name + str(cnt))
            ossrf.setSurfaceType(srf_type)
            ossrf_ls.append(ossrf)
    return ossrf_ls

def create_ossubsrf(osmodel: osmod, subsrf: geomie3d.topobj.Face, constr_dicts: dict, ossrf: osmod.Surface, 
                    parent_nrml: list[float]) -> list[osmod.SubSurface]:
    '''
    create openstudio sub surface.

    Parameters
    ----------
    osmodel : osmod
        The openstudio model.

    subsrf: geomie3d.topobj.Face
        surface with the necessary attributes to convert into a openstudio model.

    constr_dicts: dict
        dictionary of all the osmod constructions.

    ossrf: osmod.Surface
        the host of the subsrf.

    parent_nrml: list[float]
        the normal of the parent surface.
    
    Returns
    -------
    list[osmod.SubSurface]
        the openstudio surfaces
    '''
    ossubsrf_ls = []
    subsrf_attr = subsrf.attributes
    sconstr_id = subsrf_attr['construction_id']
    ssrf_type = subsrf_attr['type']
    ssrf_name = subsrf_attr['name']
    osglz_constr = constr_dicts[sconstr_id]
    child_nrml = geomie3d.get.face_normal(subsrf)
    are_convex = geomie3d.calculate.are_polygon_faces_convex([subsrf])[0]
    if are_convex:
        child_vs = geomie3d.get.vertices_frm_face(subsrf)
        child_pt3ds = openstudio_utils.g3dverts2ospt3d(child_vs)
        if not np.array_equal(child_nrml, parent_nrml):
            child_pt3ds.reverse()
        child_ossrf = osmod.SubSurface(child_pt3ds, osmodel)
        child_ossrf.setSurface(ossrf)
        child_ossrf.setConstruction(osglz_constr)
        child_ossrf.setSubSurfaceType(ssrf_type)
        child_ossrf.setName(ssrf_name)
        ossubsrf_ls.append(child_ossrf)
    else:
        tri_faces = geomie3d.modify.triangulate_face(subsrf)
        for cnt,tri in enumerate(tri_faces):
            child_vs = geomie3d.get.vertices_frm_face(tri)
            child_pt3ds = openstudio_utils.g3dverts2ospt3d(child_vs)
            child_ossrf = osmod.SubSurface(child_pt3ds, osmodel)
            child_ossrf.setSurface(ossrf)
            child_ossrf.setConstruction(osglz_constr)
            child_ossrf.setSubSurfaceType(ssrf_type)
            child_ossrf.setName(ssrf_name + str(cnt))
            ossubsrf_ls.append(child_ossrf)

    return ossubsrf_ls

def create_opq_constr(osmodel: osmod, thermal_resistance: float, opq_constr_path: str) -> osmod.Construction:
    '''
    create openstudio construction based on the thermal resistance of the wall.

    Parameters
    ----------
    osmodel: osmod
        openstudio model

    thermal_resistance: float
        the thermal resistance of the construction

    opq_constr_path: str
        the path of the opaque construction library
    
    Returns
    -------
    osmod.Construction
        the openstudio construction
    '''
    with open(opq_constr_path) as f:
        data = json.load(f)
    constr_lib = data['construction_library']
    mat_lib = data['material_library']
    resist_keys_str = list(constr_lib.keys())
    resist_keys = list(map(float, resist_keys_str))
    # find the closest resistance construction
    r_diffs = thermal_resistance - np.array(resist_keys)
    r_diffs = np.abs(r_diffs)
    min_diff = np.min(r_diffs)
    min_idxs = np.where(r_diffs == min_diff)[0]
    chosen_constr_idx = resist_keys_str[min_idxs[0]] # there can only be one
    chosen_constr = constr_lib[chosen_constr_idx]
    chosen_mat_layers = chosen_constr['material_layers']
    n_mat_lays = len(chosen_mat_layers)
    if n_mat_lays == 1:
        chosen_mat_layer = chosen_mat_layers[0]
        chosen_name = chosen_constr['name'][0]
    elif n_mat_lays > 1:
        thin_idx = choose_thin_constr(chosen_mat_layers, mat_lib)
        chosen_mat_layer = chosen_mat_layers[thin_idx]
        chosen_name = chosen_constr['name'][thin_idx]
    
    # create the construction in osmod
    osmod_layers = []
    for ml in chosen_mat_layer:
        mat_dict = mat_lib[str(ml)]
        if mat_dict['conductivity'] is not None:
            std_opq_mat = osmod.StandardOpaqueMaterial(osmodel, mat_dict['roughness'], mat_dict['thickness'],
                                                       mat_dict['conductivity'], mat_dict['density'], mat_dict['specificheat'])
            osmod_layers.append(std_opq_mat)
        elif mat_dict['thermalresistance'] is not None: # must be a massless material
            massless_mat = osmod.MasslessOpaqueMaterial(osmodel, mat_dict['roughness'], mat_dict['thermalresistance'])
            massless_mat.setThermalAbsorptance(mat_dict['thermalabsorptance'])
            massless_mat.setSolarAbsorptance (mat_dict['solarabsorptance'])
            massless_mat.setVisibleAbsorptance (mat_dict['visibleabsorptance'])
            osmod_layers.append(massless_mat)
        else:
            print('MATERIAL NOT AVAILABLE')

    
    osmod_constr = osmod.Construction(osmodel)
    osmod_constr.setName(chosen_name)
    osmod_constr.setLayers(osmod_layers)
    return osmod_constr

def create_smpl_glz_constr(osmodel: osmod, uvalue: float, smpl_glz_constr_path: str) -> osmod.Construction:
    '''
    create openstudio construction based on the thermal resistance of the wall.

    Parameters
    ----------
    osmodel: osmod
        openstudio model

    uvalue: float
        the uvalue of the glazing construction

    smpl_glz_constr_path: str
        the path of the glazing construction library
    
    Returns
    -------
    osmod.Construction
        the openstudio construction
    '''
    with open(smpl_glz_constr_path) as f:
        data = json.load(f)

    constr_lib = data['construction_library']
    mat_lib = data['material_library']
    u_keys_str = list(constr_lib.keys())
    u_keys = list(map(float, u_keys_str))
    # find the closest uvalue construction
    r_diffs = uvalue - np.array(u_keys)
    r_diffs = np.abs(r_diffs)
    min_diff = np.min(r_diffs)
    min_idxs = np.where(r_diffs == min_diff)[0]
    chosen_constr_idx = u_keys_str[min_idxs[0]] # there can only be one
    chosen_constr = constr_lib[chosen_constr_idx]
    chosen_mat_layers = chosen_constr['material_layers']
    n_mat_lays = len(chosen_mat_layers)
    if n_mat_lays == 1:
        chosen_mat_layer = chosen_mat_layers[0]
        chosen_name = chosen_constr['name'][0]
    elif n_mat_lays > 1:
        vt_idx = choose_best_vt_constr(chosen_mat_layers, mat_lib)
        chosen_mat_layer = chosen_mat_layers[vt_idx]
        chosen_name = chosen_constr['name'][vt_idx]
    
    # create the construction in osmod
    osmod_layers = []
    for ml in chosen_mat_layer:
        mat_dict = mat_lib[str(ml)]
        smpl_glz = osmod.SimpleGlazing(osmodel, mat_dict['ufactor'], mat_dict['solarheatgaincoefficient'])
        smpl_glz.setVisibleTransmittance(mat_dict['visibletransmittance'])
        osmod_layers.append(smpl_glz)
    
    osmod_constr = osmod.Construction(osmodel)
    osmod_constr.setName(chosen_name)
    osmod_constr.setLayers(osmod_layers)
    return osmod_constr

def ifcarch2osmod(ifc_path: str, osmod_path: str, viz: bool, opq_constr_path: str, smpl_glz_constr_path: str) -> str:
    '''
    Converts ifc to openstudio model.

    Parameters
    ----------
    ifc_path : str
        The file path of the IFC to convert.
    
    osmod_path : str
        The file path of the OpenStudio result.

    ndecimals : int
        The number of decimals to round to for the geometries.

    viz : bool
        visualize the calculation procedure if turned on.
    
    opq_constr_path: str
        path to the JSON file that stores opaque construction info for openstudio

    smpl_glz_constr_path: str
        path to the JSON file that stores glazing info for openstudio

    Returns
    -------
    str
        The file path of the OpenStudio result
    '''
    #------------------------------------------------------------------------------------------------------
    # region: read the ifc file and extract all the necessary information for conversion to osm
    #------------------------------------------------------------------------------------------------------
    ifcmodel = ifcopenshell.open(ifc_path)
    ifcbldg_dicts = ifcopenshell_utils.get_ifc_building_info(ifcmodel, envlp_pset_name ='Pset_OsmodThermalResistance')
    ifcstory_dicts = ifcopenshell_utils.get_ifc_story_info(ifcmodel)
    ifczone_dicts = ifcopenshell_utils.get_ifc_zone_info(ifcmodel)
    ifcspacez_dicts, envlp_constr_dicts = ifcopenshell_utils.get_ifc_spatial_zone_info(ifcmodel, ifcstory_dicts, ifcbldg_dicts, pset_name ='Pset_OsmodSpace',
                                                                                       envlp_pset_name = 'Pset_OsmodThermalResistance')
    subsrf_constr_dicts = ifcopenshell_utils.get_ifc_subsrf_info(ifcmodel, ifcspacez_dicts)

    # region: get all the shading surfaces
    ifc_shadings = ifcmodel.by_type('IfcShadingDevice')
    shade_list = []
    for ifcshade in ifc_shadings:
        # get the geometrical data from the shadings
        shade_faces = ifcopenshell_utils.ifcopenshell_entity_geom2g3d(ifcshade)
        shade_list.extend(shade_faces)
    # endregion: get all the shading surfaces

    # region: viz all the envlopes
    if viz == True:
        viz_bldg_dicts(ifcbldg_dicts)
        viz_spatialzone_dicts(ifcspacez_dicts, shade_list)
    # endregion: viz all the envlopes
    #------------------------------------------------------------------------------------------------------
    # endregion: read the ifc file and extract all the necessary information for conversion to osm
    #------------------------------------------------------------------------------------------------------
    # region: setup openstudio model
    #------------------------------------------------------------------------------------------------------
    osmodel = osmod.Model()
    # region: create wall materials and construction
    envlpc_items = envlp_constr_dicts.items()
    # print(envlpc_items)
    osenvlp_constr_dicts = {}
    for envlpc_item in envlpc_items:
        envlpc_key = envlpc_item[0]
        envlpc_val = envlpc_item[1]
        t_resist = envlpc_val['ThermalResistance']
        # base on this thermal resistance search for the right material
        opq_constr = create_opq_constr(osmodel, t_resist, opq_constr_path)
        osenvlp_constr_dicts[envlpc_key] = opq_constr
    # endregion: create wall materials and construction
    
    # region: create window material and construction
    glzc_items = subsrf_constr_dicts.items()
    osglz_constr_dicts = {}
    for glzc_item in glzc_items:
        glzc_val = glzc_item[1]
        glzc_key = glzc_item[0]
        if 'UFactor' in list(glzc_val.keys()):
            subsrf_constr = create_smpl_glz_constr(osmodel, glzc_val['UFactor'], smpl_glz_constr_path)
        elif 'ThermalResistance' in list(glzc_val.keys()):
            subsrf_constr = create_opq_constr(osmodel, glzc_val['ThermalResistance'], opq_constr_path)
        else:
            print('GLAZING MATERIAL NOT ACCOUNTED FOR')

        osglz_constr_dicts[glzc_key] = subsrf_constr
    # endregion: create window material and construction

    # building 
    bldg_vals = ifcbldg_dicts.values()
    if len(bldg_vals) > 1:
        print('OPENSTUDIO CAN ONLY TAKE ONE BUILDING')

    # buildingstory
    osbldgstry_dicts = {}
    bldgstory_items = ifcstory_dicts.items()
    for bldgstory_item in bldgstory_items:
        bldgstory_val = bldgstory_item[1]
        bldgstory_key = bldgstory_item[0]
        osbldgstry = osmod.BuildingStory(osmodel)
        osbldgstry.setName(bldgstory_val['name'])
        osbldgstry_dicts[bldgstory_key] = osbldgstry
    
    # thermal zone
    tzone_items = ifczone_dicts.items()
    ostzone_dicts = {}
    for tzone_item in tzone_items:
        tzone_key = tzone_item[0]
        tzone_val = tzone_item[1]
        oszone = osmod.ThermalZone(osmodel)
        oszone.setName(tzone_val['name'])
        ostzone_dicts[tzone_key] = oszone

    # region: building spaces
    ifcspacez_vals = ifcspacez_dicts.values()
    for ifcspacez_val in ifcspacez_vals:
        osspace = osmod.Space(osmodel)
        space_name = ifcspacez_val['name']
        osspace.setName(space_name)
        osspace.setBuildingStory(osbldgstry_dicts[ifcspacez_val['story']])
        tzone_id = ifcspacez_val['tzone']
        if tzone_id == None:
            oszone = osmod.ThermalZone(osmodel)
            oszone.setName( space_name + '_tzone')
        else:
            oszone = ostzone_dicts[tzone_id]
        osspace.setThermalZone(oszone)

        space_srfs = ifcspacez_val['surfaces']
        for space_srf in space_srfs:
            srf_attr = space_srf.attributes
            ossrfs = create_ossrf(osmodel, space_srf, osenvlp_constr_dicts, osspace)
            if 'children' in srf_attr.keys():
                children = space_srf.attributes['children']
                parent_nrml = geomie3d.get.face_normal(space_srf)
                if len(ossrfs) > 1:
                    print('SURFACE IS NON CONVEX AND HAS BEEN BROKEN INTO TRIANGLES, WILL NOT BE ABLE TO HOST ANY SUBSURF')
                elif len(ossrfs) == 1:
                    for child_srf in children:
                        create_ossubsrf(osmodel, child_srf, osglz_constr_dicts, ossrfs[0], parent_nrml)

        osspace.autocalculateFloorArea()
        ifcspace_pset = ifcspacez_val['pset']
        if ifcspace_pset is not None:
            if 'ElectricEquipmentPowerPerFloorArea' in list(ifcspace_pset.keys()): 
                epower_farea = ifcspace_pset['ElectricEquipmentPowerPerFloorArea']
                osspace.setElectricEquipmentPowerPerFloorArea(epower_farea)
            if 'FloorAreaPerPerson' in list(ifcspace_pset.keys()): 
                farea_person = ifcspace_pset['FloorAreaPerPerson']
                osspace.setFloorAreaPerPerson(farea_person)
            if 'LightingPowerPerFloorArea' in list(ifcspace_pset.keys()): 
                lpower_farea = ifcspace_pset['LightingPowerPerFloorArea']
                osspace.setLightingPowerPerFloorArea(lpower_farea)
            if 'OutdoorAirFlowperFloorArea' in list(ifcspace_pset.keys()): 
                oair_farea = ifcspace_pset['OutdoorAirFlowperFloorArea']
                outdoor_air = osmod.DesignSpecificationOutdoorAir(osmodel)
                outdoor_air.setOutdoorAirFlowperFloorArea(oair_farea) #m3/s
                osspace.setDesignSpecificationOutdoorAir(outdoor_air)
    # endregion: building spaces
    
    # region: convert the shading
    osshade_grp = osmod.ShadingSurfaceGroup(osmodel)
    for shade in shade_list:
        is_convex = geomie3d.calculate.are_polygon_faces_convex([shade])[0]
        if is_convex:
            shade_verts = geomie3d.get.vertices_frm_face(shade)
            os3dpts = openstudio_utils.g3dverts2ospt3d(shade_verts)
            os_shade = osmod.ShadingSurface(os3dpts, osmodel)
            os_shade.setShadingSurfaceGroup(osshade_grp)
        else:
            tri_faces = geomie3d.modify.triangulate_face(shade)
            for tri in tri_faces:
                shade_verts = geomie3d.get.vertices_frm_face(tri)
                os3dpts = openstudio_utils.g3dverts2ospt3d(shade_verts)
                os_shade = osmod.ShadingSurface(os3dpts, osmodel)
                os_shade.setShadingSurfaceGroup(osshade_grp)

    # endregion: convert the shading
    osmodel.save(osmod_path, True)
    return osmod_path
    #------------------------------------------------------------------------------------------------------
    # endregion: setup openstudio model
    #------------------------------------------------------------------------------------------------------

def viz_bldg_dicts(ifcbldg_dicts: dict):
    '''
    visualize all the surfaces in the story dicts

    Parameters
    ----------
    ifcstory_dicts: dict
        dictionaries of produce by the ifcopenshell_utils.get_ifc_story_info function.
    
    '''
    from geomie3d import viz
    all_envlps = []
    vals = ifcbldg_dicts.values()
    for val in vals:
        envlps = val['ifc_envelope']
        envlp_vals = envlps.values()
        # print(len(envlp_vals))
        # print(envlp_vals)
        for envlp in envlp_vals:
            # print(envlp)
            srfs = envlp['surfaces']
            all_envlps.extend(srfs)
            # print(srfs)

    viz.viz([{'topo_list': all_envlps, 'colour': 'blue'}])

def viz_spatialzone_dicts(ifcspatial_zone_dicts: dict, shade_list: list[geomie3d.topobj.Face]):
    '''
    visualize all the surfaces in the spatial dicts

    Parameters
    ----------
    ifcspatial_zone_dicts: dict
        dictionaries of produce by the ifcopenshell_utils.get_ifc_story_info function.
    
    shade_list: list[geomie3d.topobj.Face]
        list of shades in the ifc model.
    '''
    from geomie3d import viz
    subsrf_ls = []
    srf_ls = []
    vals = ifcspatial_zone_dicts.values()
    for val in vals:
        srfs = val['surfaces']
        srf_ls.extend(srfs)
        for srf in srfs:
            attr = srf.attributes
            if 'children' in attr:
                # print(attr['children'])
                subsrf_ls.extend(attr['children'])
    
    win_nrml_edges = geomie3d.create.pline_edges_frm_face_normals(subsrf_ls)
    envlp_nrml_edges = geomie3d.create.pline_edges_frm_face_normals(srf_ls)
    
    
    if len(shade_list) !=0:
        viz.viz([{'topo_list': srf_ls, 'colour': 'white'},
                        {'topo_list': subsrf_ls, 'colour': 'blue'},
                        {'topo_list': win_nrml_edges, 'colour': 'green'},
                        {'topo_list': envlp_nrml_edges, 'colour': 'white'},
                        {'topo_list': shade_list, 'colour': 'blue'},
                        ])
    else:
        viz.viz([{'topo_list': srf_ls, 'colour': 'white'},
                        {'topo_list': subsrf_ls, 'colour': 'blue'},
                        {'topo_list': win_nrml_edges, 'colour': 'green'},
                        {'topo_list': envlp_nrml_edges, 'colour': 'white'},
                        ])

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        ifc_path = args.ifc
    else:
        lines = list(sys.stdin)
        ifc_path = lines[0].strip()

    osmod_path = args.osmod
    if osmod_path == None:
        ifc_parent_path = Path(ifc_path).parent
        ifc_name = Path(ifc_path).name
        ifc_name = ifc_name.lower().replace('.ifc', '')
        res_folder = ifc_parent_path.joinpath(ifc_name)
        if res_folder.exists() == False:
            res_folder.mkdir(parents=True)
        osmod_path = res_folder.joinpath(ifc_name + '.osm')
    else:
        res_folder = Path(osmod_path).parent
        if res_folder.exists() == False:
            res_folder.mkdir(parents=True)

    viz = args.viz
    osmod_path = Path(osmod_path).resolve()
    opq_constr_path = settings.OSMOD_OPQ_CONSTR_PATH
    smpl_glz_constr_path = settings.OSMOD_SMPL_GLZ_CONSTR_PATH
    ifcarch2osmod(ifc_path, osmod_path, viz, opq_constr_path, smpl_glz_constr_path)
    # make sure this output can be piped into another command on the cmd
    print(osmod_path)
    sys.stdout.flush()
#===================================================================================================
# endregion: FUNCTIONS
#===================================================================================================
# region: Main
#===================================================================================================
if __name__=='__main__':
    main()
#===================================================================================================
# endregion: Main
#===================================================================================================