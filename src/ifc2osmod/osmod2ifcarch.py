import sys
import json
import argparse
from pathlib import Path

import numpy as np
import geomie3d
import ifcopenshell
import ifcopenshell.api
from openstudio import model as osmod

import ifc_utils.ifcopenshell_utils as ifcopenshell_utils
from . import settings
from .utils import openstudio_utils
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Convert OpenStudio geometry to IFC Models")
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE',
                        help = 'The path of the openstudio model')
    
    parser.add_argument('-i', '--ifc', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the resultant ifc file')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the osmod filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def convert_osmod_pset_schema2ifc_pset_props(osmod_pset: dict) -> dict:
    '''
    Converts osmodel pset to ifc pset.

    Parameters
    ----------
    osmod_pset : dict
        dictionary from the osmod

    Returns
    -------
    dict
        The file path of the ifc result
    '''
    ifc_pset = {}
    osmod_keys = osmod_pset.keys()
    for osmod_key in osmod_keys:
        osmod_value = osmod_pset[osmod_key]
        ifc_pset[osmod_key] = osmod_value['value']
    return ifc_pset

def create_ifc_built_ele_type(ifcmodel: ifcopenshell.file, type_name: str, const_types: dict, ifc_class: str, predefined_type: str, 
                              material_layer_set: ifcopenshell.entity_instance) -> ifcopenshell.entity_instance:
    '''
    create IfcBuiltElementType.

    Parameters
    ----------
    ifcmodel: ifcopenshell.file
        the ifc model.

    type_name: str
        the name of the ifc built element type class.
    
    const_types: dict
        dictionary of all the types already created.

    ifc_class: str
        the ifc built element type class to create.

    predefined_type: str
        the predefined type of the built element type. 
    
    material_layer_set: ifcopenshell.entity_instance
        the material layer set to be associated with the built element type.

    Returns
    -------
    ifcopenshell.entity_instance
        The ifc built element type that is created.
    '''
    const_type_names = const_types.keys()
    if type_name in const_type_names:
        ifc_built_ele_type = const_types[type_name]
    else:
        ifc_built_ele_type = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class=ifc_class, name=type_name, 
                                                predefined_type=predefined_type)
        ifcopenshell.api.run("material.assign_material", ifcmodel, product=ifc_built_ele_type, material=material_layer_set)
        const_types[type_name] = ifc_built_ele_type
    return ifc_built_ele_type

def srf_verts_2pt_wall(xyzs: np.ndarray | list) -> tuple[np.ndarray, float, float]:
    '''
    extrude in normal direction.

    Parameters
    ----------
    xyzs: np.ndarray
        np.ndarray[shape(number of points, 3)] the points forming the polygon face to be processed. The polygon must be vertical.

    Returns
    -------
    points2d: np.ndarray
        np.ndarray[shape(2,2)].
    
    height: float
        height of the wall
    
    elev: float
        elevation of the wall
    '''
    bbox = geomie3d.calculate.bbox_frm_xyzs(xyzs)
    height = bbox.maxz - bbox.minz
    if type(xyzs) != np.ndarray:
        xyzs = np.array(xyzs)

    xyzs[:, 2] = bbox.minz
    g3d_verts = geomie3d.create.vertex_list(xyzs)
    fused_verts = geomie3d.modify.fuse_vertices(g3d_verts)
    fused_xyzs = np.array([v.point.xyz for v in fused_verts])
    fused_xyzs2d = fused_xyzs[:, :2]
    fused_xyzs2d = fused_xyzs2d.tolist()
    return fused_xyzs2d, height, bbox.minz

def create_ifc_srf_style(ifcmodel: ifcopenshell.file, rgb: list[float], transparency: float, representation: ifcopenshell.entity_instance):
    '''
    define the color and transparency of an ifc representation.

    Parameters
    ----------
    ifcmodel: ifcopenshell.file
        the ifc model.

    rgb: list[float]
        list[shape(3)], [r,g,b]. Values of 0-1

    transparency: float
        value of 0-1. 0 being opaque, 1 being transparent.
    
    representation: ifcopenshell.entity_instance
        the ifc representation to assign the style to.
    '''
    # add a style to the material for easy visualization
    style = ifcopenshell.api.run("style.add_style", ifcmodel)
    # Create a simple grey shading colour and transparency.
    ifcopenshell.api.run("style.add_surface_style", ifcmodel,
        style=style, ifc_class="IfcSurfaceStyleShading", attributes={
            "SurfaceColour": { "Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2] },
            "Transparency": transparency, # 0 is opaque, 1 is transparent
        })
    # Now any element (like our wall) with a concrete material will have
    ifcopenshell.api.run("style.assign_representation_styles", ifcmodel, shape_representation=representation, styles=[style])

def create_an_ifc_surface(ifcmodel: ifcopenshell.file, xyzs: np.ndarray, name: str, ifc_class: str, const_thickness: float, 
                          surface_dict: dict, body: ifcopenshell.entity_instance, srf_const_dict: dict, const_types: dict, 
                          ifc_type_class: str, predefined_type: str) -> ifcopenshell.entity_instance:
    '''
    create IfcSlab or IfcRoof.

    Parameters
    ----------
    ifcmodel: ifcopenshell.file
        the ifc model.

    xyzs: np.ndarray
        np.ndarray[shape(number of points, 3)] the points forming the polygon face to be processed.

    name: str
        the name of the ifc built element.
    
    ifc_class: str
        the ifc built element class to create. IfcSlab or IfcRoof

    const_thickness: float
        the thickness of the slab or roof.

    surface_dict: dict
        dict has keys: name, vertices, construction, type, thickness
    
    body: ifcopenshell.entity_instance
        modeling context of the ifc model.

    srf_const_dict: dict
        dictionary has the following keys: ifc_mat_layer_set, thickness, name, mat_names, mat_handles
    
    const_types: dict
        - nested dictionaries, the name of the ifc built element type is used as the key on the top level
        - with the value of the dictionary is the ifc built element type.

    ifc_type_class: str
        the ifc built element type class to create.

    predefined_type: str
        the predefined type of the built element type. 

    Returns
    -------
    ifcopenshell.entity_instance
        The ifc built element that is created.
    '''
    ifc_surface = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class=ifc_class, name=name)
    if srf_const_dict is not None and const_thickness > 0:
        if ifc_class == 'IfcWall':
            poly_mesh_dict = ifcopenshell_utils.mv_extrude_srf(xyzs, const_thickness, const_thickness/2)
            ifc_repr = ifcopenshell.api.run("geometry.add_mesh_representation", ifcmodel, context=body, 
                                            vertices=[poly_mesh_dict['vertices'].tolist()], faces=[poly_mesh_dict['indices']])
            ifcopenshell.api.run("geometry.edit_object_placement", ifcmodel, product=ifc_surface)
        elif ifc_class == 'IfcRoof':
            poly_mesh_dict = ifcopenshell_utils.extrude(xyzs, const_thickness, direction=[0,0,1])
            ifc_repr = ifcopenshell.api.run("geometry.add_mesh_representation", ifcmodel, context=body, 
                                            vertices=[poly_mesh_dict['vertices'].tolist()], faces=[poly_mesh_dict['indices']])
            ifcopenshell.api.run("geometry.edit_object_placement", ifcmodel, product=ifc_surface)
        else:
            poly_mesh_dict = ifcopenshell_utils.extrude(xyzs, const_thickness)
            ifc_repr = ifcopenshell.api.run("geometry.add_mesh_representation", ifcmodel, context=body, 
                                            vertices=[poly_mesh_dict['vertices'].tolist()], faces=[poly_mesh_dict['indices']])
            ifcopenshell.api.run("geometry.edit_object_placement", ifcmodel, product=ifc_surface)
    else:
        faces = [[list(range(len(xyzs)))]]
        ifc_repr = ifcopenshell.api.run("geometry.add_mesh_representation", ifcmodel, context=body, 
                                                vertices=[xyzs], faces=faces)
        ifcopenshell.api.run("geometry.edit_object_placement", ifcmodel, product=ifc_surface)

    ifcopenshell.api.run("geometry.assign_representation", ifcmodel, product=ifc_surface, representation=ifc_repr)
    surface_dict['thickness'] = const_thickness
    surface_dict['ifc_surface'] = ifc_surface

    if srf_const_dict is not None:
        if ifc_type_class == 'IfcSlabType':
            prefix = 'flr'
        elif ifc_type_class == 'IfcRoofType':
            prefix = 'roof'
        elif ifc_type_class == 'IfcWallType':
            prefix = 'wall'
        elif ifc_type_class == 'IfcWindowType':
            prefix = 'win'
        elif ifc_type_class == 'IfcDoorType':
            prefix = 'door'
        ifc_type_name = f"{prefix}_{srf_const_dict['name']}"
        ifc_type = create_ifc_built_ele_type(ifcmodel, ifc_type_name, const_types, ifc_type_class, predefined_type, srf_const_dict['ifc_mat_layer_set'])
        if ifc_type_class == 'IfcWindowType':
            ifc_type.PartitioningType = 'NOTDEFINED'
        elif ifc_type_class == 'IfcDoorType':
            ifc_type.OperationType = 'NOTDEFINED'
        ifcopenshell.api.run("type.assign_type", ifcmodel, related_object=ifc_surface, relating_type=ifc_type)
    
    # color the representation
    if ifc_class == 'IfcWall' or ifc_class == 'IfcSlab':
        rgb = [0.5, 0.5, 0.5]
        transparency = 0
        create_ifc_srf_style(ifcmodel, rgb, transparency, ifc_repr)
    elif ifc_class == 'IfcRoof':
        rgb = [1.0, 0.0, 0.0]
        transparency = 0
        create_ifc_srf_style(ifcmodel, rgb, transparency, ifc_repr)

    elif ifc_class == 'IfcWindow':
        rgb = [1.0, 1.0, 1.0]
        transparency = 0.8
        create_ifc_srf_style(ifcmodel, rgb, transparency, ifc_repr)
    
    elif ifc_class == 'IfcDoor':
        rgb = [0.5, 0.5, 0.5]
        transparency = 0.0
        create_ifc_srf_style(ifcmodel, rgb, transparency, ifc_repr)

    return ifc_surface
    
def create_ifc_surfaces(ifcmodel: ifcopenshell.file, surface_dicts: dict, const_dicts: dict, const_types: dict, 
                        ifc_envelopes: list, body: ifcopenshell.entity_instance):
    '''
    create IfcBuiltElement of the surfaces from openstudio model.

    Parameters
    ----------
    ifcmodel: ifcopenshell.file
        the ifc model.

    surface_dicts: dict
        - surfaces: surface dictionaries index by their handles and 
        - within each dict has keys: name, vertices, construction, type 
    
    const_dicts: dict
        - nested dictionaries, the osmod handle of the construction is used as the key on the top level
        - each dictionary has the following keys: ifc_mat_layer_set, thickness, name, mat_names, mat_handles

    const_types: dict
        - nested dictionaries, the name of the ifc built element type is used as the key on the top level
        - with the value of the dictionary is the ifc built element type.

    ifc_envelopes: list
        list of ifc built elements created.
    
    body: ifcopenshell.entity_instance
        modeling context of the ifc model.

    '''
    surface_dict_vals = surface_dicts.values()
    srf_const_dict = None
    const_thickness = None
    for surface_dict_val in surface_dict_vals:
        srf_name = surface_dict_val['name']
        vertices = surface_dict_val['vertices']
        srf_type = surface_dict_val['type']
        const_handle = surface_dict_val['construction']
        if const_handle is not None:
            srf_const_dict = const_dicts[const_handle]
            const_thickness = srf_const_dict['thickness']
        if srf_type == 'Wall':
            ifc_srf = create_an_ifc_surface(ifcmodel, vertices, srf_name, 'IfcWall', const_thickness, surface_dict_val, body, srf_const_dict,
                                             const_types, 'IfcWallType', 'NOTDEFINED')
            
        elif srf_type == 'Floor':
            ifc_srf = create_an_ifc_surface(ifcmodel, vertices, srf_name, 'IfcSlab', const_thickness, surface_dict_val, body, srf_const_dict,
                                                 const_types, 'IfcSlabType', 'FLOOR')
        elif srf_type == 'RoofCeiling':
            ifc_srf = create_an_ifc_surface(ifcmodel, vertices, srf_name, 'IfcRoof', const_thickness, surface_dict_val, body, srf_const_dict,
                                             const_types, 'IfcRoofType', 'NOTDEFINED')
        ifc_envelopes.append(ifc_srf)

def create_ifc_sub_surfaces(ifcmodel: ifcopenshell.file, sub_surface_dicts: dict, surface_dicts: dict, const_dicts: dict, const_types: dict, 
                            ifc_envelopes: list, body: ifcopenshell.entity_instance):
    '''
    create IfcBuiltElement of the surfaces from openstudio model.

    Parameters
    ----------
    ifcmodel: ifcopenshell.file
        the ifc model.

    sub_surface_dicts: dict
        - sub surface dictionaries index by their handles and 
        - within each dict has keys: name, vertices, construction, type, host
    
    surface_dicts: dict
        - surfaces: surface dictionaries index by their handles and 
        - within each dict has keys: name, vertices, construction, type, thickness
    
    const_dicts: dict
        - nested dictionaries, the osmod handle of the construction is used as the key on the top level
        - each dictionary has the following keys: ifc_mat_layer_set, thickness, name, mat_names, mat_handles

    const_types: dict
        - nested dictionaries, the name of the ifc built element type is used as the key on the top level
        - with the value of the dictionary is the ifc built element type.

    ifc_envelopes: list
        list of ifc built elements created.
    
    body: ifcopenshell.entity_instance
        modeling context of the ifc model.

    '''
    sub_surface_dict_vals = sub_surface_dicts.values()
    srf_const_dict = None
    const_thickness = None
    for sub_surface_dict_val in sub_surface_dict_vals:
        sub_srf_name = sub_surface_dict_val['name']
        ssrf_vertices = sub_surface_dict_val['vertices']
        sub_srf_type = sub_surface_dict_val['type']
        sub_srf_host = sub_surface_dict_val['host']
        host_thickness = surface_dicts[sub_srf_host]['thickness']
        ifc_host = surface_dicts[sub_srf_host]['ifc_surface']
        ifcopening = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcOpeningElement", name=f"{sub_srf_name}_opening")
        # make a hole in the wall
        extruded_ssrf = ifcopenshell_utils.mv_extrude_srf(ssrf_vertices, host_thickness*2.5, host_thickness)
        opening_repr = ifcopenshell.api.run("geometry.add_mesh_representation", ifcmodel, context=body, 
                                            vertices=[extruded_ssrf['vertices'].tolist()], faces=[extruded_ssrf['indices']])
        ifcopenshell.api.run("geometry.edit_object_placement", ifcmodel, product=ifcopening)
        ifcopenshell.api.run("geometry.assign_representation", ifcmodel, product=ifcopening, representation=opening_repr)
        ifcopenshell.api.run("void.add_opening", ifcmodel, opening=ifcopening, element=ifc_host)
        
        ssrf_const_handle = sub_surface_dict_val['construction']
        if ssrf_const_handle is not None:
            srf_const_dict = const_dicts[ssrf_const_handle]
            const_thickness = srf_const_dict['thickness']

        if sub_srf_type == 'FixedWindow':
            ifc_srf = create_an_ifc_surface(ifcmodel, ssrf_vertices, sub_srf_name, 'IfcWindow', const_thickness, sub_surface_dict_val, body, srf_const_dict,
                                             const_types, 'IfcWindowType', 'NOTDEFINED')
            ifcopenshell.api.run("void.add_filling", ifcmodel, opening=ifcopening, element=ifc_srf)
        elif sub_srf_type == 'Door' or sub_srf_type == 'GlassDoor':
            ifc_srf = create_an_ifc_surface(ifcmodel, ssrf_vertices, sub_srf_name, 'IfcDoor', const_thickness, sub_surface_dict_val, body, srf_const_dict,
                                             const_types, 'IfcDoorType', 'DOOR')
            ifcopenshell.api.run("void.add_filling", ifcmodel, opening=ifcopening, element=ifc_srf)
        ifc_envelopes.append(ifc_srf)
        
def osmod2ifcarch(osmod_path: str, ifc_path: str, viz: bool) -> str:
    '''
    Converts osmodel to ifc.

    Parameters
    ----------
    osmod_path : str
        The file path of the Idf.

    ifc_path : str
        The file path of the resultant IFC.
    
    viz : bool
        visualize the calculation procedure if turned on.

    Returns
    -------
    str
        The file path of the ifc result
    '''
    #------------------------------------------------------------------------------------------------------
    # region: extract data from the osmodel
    #------------------------------------------------------------------------------------------------------
    osmod_stem = str(Path(osmod_path).stem)
    osmodel = osmod.Model.load(osmod_path).get()
    # get all the building storys
    story_dicts = openstudio_utils.get_osmod_story_info(osmodel)
    # get all the osmodel spacetypes -> ifcspacetype
    spacetype_dicts = openstudio_utils.get_osmod_spacetype_info(osmodel)
    # get all the materials from osmodel -> ifc material
    mat_dicts = openstudio_utils.get_osmod_material_info(osmodel)
    # get all the construction from osmodel -> ifc material set
    const_dicts = openstudio_utils.get_osmod_construction_info(osmodel)
    # get all the osmod thermalzones -> ifczone
    tzone_dicts = openstudio_utils.get_osmod_tzone_info(osmodel)
    # get all the spaces -> ifcspace
    space_dicts = openstudio_utils.get_osmod_space_info(osmodel)
    #------------------------------------------------------------------------------------------------------
    # endregion: extract data from the osmodel
    #------------------------------------------------------------------------------------------------------
    #------------------------------------------------------------------------------------------------------
    # region: translate the osmodel data to ifc
    #------------------------------------------------------------------------------------------------------
    # region: initiate ifc file
    pset_dir = settings.PSET_DATA_DIR
    # ifcmodel = ifcopenshell.file(schema='IFC4x3')
    ifcmodel = ifcopenshell.file(schema='IFC4')
    # All projects must have one IFC Project element
    project = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcProject", name=osmod_stem)
    # specify without any arguments to automatically create millimeters = length, square meters = area, and cubic meters = volume.
    ifcopenshell.api.run("unit.assign_unit", ifcmodel)
    # Let's create a modeling geometry context, so we can store 3D geometry (note: IFC supports 2D too!)
    context = ifcopenshell.api.run("context.add_context", ifcmodel, context_type="Model")
    # In particular, in this example we want to store the 3D "body" geometry of objects, i.e. the body shape
    body = ifcopenshell.api.run("context.add_context", ifcmodel, context_type="Model", 
                                context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    # Create a site, building.
    site = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcSite", name="My Site")
    building = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcBuilding", name=osmod_stem)
    # Since the site is our top level location, assign it to the project
    # Then place our building on the site, and our storey in the building
    ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = project, product = site)
    ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = site, product = building)

    # create the building storeys
    if story_dicts:
        story_vals = story_dicts.values()
        for story_val in story_vals:
            storey = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcBuildingStorey", name=story_val['name'])
            ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = building, product = storey)
            story_val['ifc_story'] = storey
    else:
        default_story_name = "Ground Floor"
        storey = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcBuildingStorey", name=default_story_name)
        ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = building, product = storey)
        story_dicts[default_story_name] = {'name': default_story_name, 'ifc_story': storey}
        
    # endregion: initiate ifc file

    # region: create ifc space types
    osmod_spacetype_schema_path = str(pset_dir.joinpath('osmod_spacetype_schema.json'))
    with open(osmod_spacetype_schema_path) as f:
        json_data = json.load(f)
        osmod_spacetype_pset_title = json_data['title']
    osmod_spacetype_pset_template = ifcopenshell_utils.create_osmod_pset_template(ifcmodel, osmod_spacetype_schema_path)
    spacetype_dict_vals = spacetype_dicts.values()
    for spacetype_dict_val in spacetype_dict_vals:
        spacetype_name = spacetype_dict_val['name']
        ifc_spacetype = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class='IfcSpaceType', name=spacetype_name)
        pset = ifcopenshell.api.run("pset.add_pset", ifcmodel, product=ifc_spacetype, name=osmod_spacetype_pset_title)
        ifc_pset_props = convert_osmod_pset_schema2ifc_pset_props(spacetype_dict_val['pset'])
        ifcopenshell.api.run("pset.edit_pset", ifcmodel, pset=pset, properties=ifc_pset_props, pset_template=osmod_spacetype_pset_template)
    # endregion: create ifc space types

    # region: translate construction and materials from osmodel to ifc
    osmod_mat_schema_path = str(pset_dir.joinpath('osmod_material_schema.json'))
    with open(osmod_mat_schema_path) as f:
        json_data = json.load(f)
        osmod_mat_pset_title = json_data['title']

    osmod_mat_pset_template = ifcopenshell_utils.create_osmod_pset_template(ifcmodel, osmod_mat_schema_path)
    mat_dict_values = mat_dicts.values()
    for mat_dict_value in mat_dict_values:
        mat_name = mat_dict_value['name']
        ifc_mat = ifcopenshell.api.run("material.add_material", ifcmodel, name=mat_name)
        pset = ifcopenshell.api.run("pset.add_pset", ifcmodel, product=ifc_mat, name=osmod_mat_pset_title)
        ifc_pset_props = convert_osmod_pset_schema2ifc_pset_props(mat_dict_value['pset'])
        ifcopenshell.api.run("pset.edit_pset", ifcmodel, pset=pset, properties=ifc_pset_props, pset_template=osmod_mat_pset_template)
        mat_dict_value['ifc_mat'] = ifc_mat
        
    # https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html#material-layer-sets
    const_dict_vals = const_dicts.values()
    for const_dict_val in const_dict_vals:
        ifc_mat_set = ifcopenshell.api.run("material.add_material_set", ifcmodel, name=const_dict_val['name'], set_type="IfcMaterialLayerSet")
        mat_handles = const_dict_val['mat_handles']
        const_thickness = 0
        for mat_handle in mat_handles:
            layer = ifcopenshell.api.run("material.add_layer", ifcmodel, layer_set=ifc_mat_set, material=mat_dicts[mat_handle]['ifc_mat'])
            thickness = mat_dicts[mat_handle]['thickness']
            ifcopenshell.api.run("material.edit_layer", ifcmodel, layer=layer, attributes={"LayerThickness": thickness*1000})
            const_thickness += thickness
        const_dict_val['ifc_mat_layer_set'] = ifc_mat_set
        const_dict_val['thickness'] = const_thickness

    # endregion: translate construction and materials from osmodel to ifc

    # region: setting up ifczone and associating spaces to zones
    # create ifczone
    tzone_dict_vals = tzone_dicts.values()
    for tzone_dict_val in tzone_dict_vals:
        tzone_name = tzone_dict_val['name']
        ifc_zone = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class='IfcZone', name=tzone_name)
        tzone_dict_val['ifc_zone'] = ifc_zone

    # create ifcspatialzone
    osmod_space_schema_path = str(pset_dir.joinpath('osmod_space_schema.json'))
    with open(osmod_space_schema_path) as f:
        json_data = json.load(f)
        osmod_space_pset_title = json_data['title']
    osmod_space_pset_template = ifcopenshell_utils.create_osmod_pset_template(ifcmodel, osmod_space_schema_path)

    const_types = {}
    space_dict_vals = space_dicts.values()
    for space_dict_val in space_dict_vals:
        # create IfcSpatialZone and input its psets
        space_name = space_dict_val['name']
        ifc_spacezone = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class='IfcSpatialZone', name=space_name)
        pset = ifcopenshell.api.run("pset.add_pset", ifcmodel, product=ifc_spacezone, name=osmod_space_pset_title)
        ifc_pset_props = convert_osmod_pset_schema2ifc_pset_props(space_dict_val['pset'])
        ifcopenshell.api.run("pset.edit_pset", ifcmodel, pset=pset, properties=ifc_pset_props, pset_template=osmod_space_pset_template)
        
        # put the space in the right thermal zone (ifczone)
        tzone_handle = space_dict_val['tzone']
        ifc_zone = tzone_dicts[tzone_handle]['ifc_zone']
        ifcopenshell.api.run("group.assign_group", ifcmodel, products = [ifc_spacezone], group = ifc_zone)

        # put the space in the right building stories
        if 'story' in space_dict_val.keys():
            bldg_story_handle = space_dict_val['story']
            ifc_bldg_story = story_dicts[bldg_story_handle]['ifc_story']
        else:
            ifc_bldg_story = list(story_dicts.values())[0]['ifc_story']
        ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = ifc_bldg_story, product = ifc_spacezone)

        # convert the geometries to ifc
        # convert surfaces
        ifc_envelopes = []
        surface_dicts = space_dict_val['surfaces']
        create_ifc_surfaces(ifcmodel, surface_dicts, const_dicts, const_types, ifc_envelopes, body)
        # convert subsurfaces
        sub_surface_dicts = space_dict_val['sub_surfaces']
        create_ifc_sub_surfaces(ifcmodel, sub_surface_dicts, surface_dicts, const_dicts, const_types, ifc_envelopes, body)

        if len(ifc_envelopes) > 0:
            ifcopenshell.api.run("spatial.assign_container", ifcmodel, relating_structure=ifc_bldg_story, products=ifc_envelopes)
    # endregion: setting up ifczone and associating spaces to zones
    
    ifcmodel.write(ifc_path)
    ifcopenshell_utils.validate_ifc(ifc_path)
    #------------------------------------------------------------------------------------------------------
    # endregion: translate the osmodel data to ifc
    #------------------------------------------------------------------------------------------------------

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        osmod_path = args.osmod
    else:
        lines = list(sys.stdin)
        osmod_path = lines[0].strip()

    osmod_path = str(Path(osmod_path).resolve())
    ifc_path = str(Path(args.ifc).resolve())
    
    osmod2ifcarch(osmod_path, ifc_path, False)
    print(ifc_path)
    sys.stdout.flush()
#===================================================================================================
# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: Main
#===================================================================================================
if __name__=='__main__':
    main()
#===================================================================================================
# endregion: Main
#===================================================================================================