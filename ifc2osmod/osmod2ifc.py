import sys
import json
import argparse
from pathlib import Path

import ifcopenshell.api.aggregate
import ifcopenshell.api.aggregate.assign_object

import geomie3d
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.api
import ifcopenshell.api.aggregate
import openstudio
from openstudio import model as osmod

import settings
import openstudio_utils
import ifcopenshell_utils

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


def osmod2ifc(osmod_path: str, ifc_path: str, viz: bool) -> str:
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
    # get all the materials from osmodel -> ifc material
    mat_dicts = openstudio_utils.get_osmod_material_info(osmodel)
    # get all the construction from osmodel -> ifc material set
    const_dicts = openstudio_utils.get_osmod_construction_info(osmodel)
    # idf model do not have building storys
    thermalzones = osmod.getThermalZones(osmodel)
    for tzone in thermalzones:
        # get all the osmod spaces -> ifc space
        spaces = tzone.spaces()
        for space in spaces:
            space_name = space.nameString()
            srfs = space.surfaces()
            for srf in srfs:
                # openstudio_utils.get_osmod_srf_info(srf)
                subsrfs = srf.subSurfaces()
                for subsrf in subsrfs:
                    osm_verts2 = subsrf.vertices()
                    subsrf_const = subsrf.construction()
                    if not subsrf_const.empty():
                        subsrf_const = subsrf_const.get()
                    # print(type(subsrf_const))
                    # print(subsrf_const.name())    
                    # print(len(osm_verts2))
                # print(len(subsrfs))
                # print(len(osm_verts))
            # print(space_name)
            # print(len(srfs))
    #------------------------------------------------------------------------------------------------------
    # endregion: extract data from the osmodel
    #------------------------------------------------------------------------------------------------------
    #------------------------------------------------------------------------------------------------------
    # region: translate the osmodel data to ifc
    #------------------------------------------------------------------------------------------------------
    # https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html#material-layer-sets
    ifcmodel = ifcopenshell.file()
    # All projects must have one IFC Project element
    project = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcProject", name=osmod_stem)
    # specify without any arguments to automatically create millimeters = length, square meters = area, and cubic meters = volume.
    ifcopenshell.api.run("unit.assign_unit", ifcmodel)

    # Let's create a modeling geometry context, so we can store 3D geometry (note: IFC supports 2D too!)
    context = ifcopenshell.api.run("context.add_context", ifcmodel, context_type="Model")

    # In particular, in this example we want to store the 3D "body" geometry of objects, i.e. the body shape
    body = ifcopenshell.api.run("context.add_context", ifcmodel, context_type="Model", 
                                context_identifier="Body", target_view="MODEL_VIEW", parent=context)

    # Create a site, building, and storey. Many hierarchies are possible.
    site = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcSite", name="My Site")
    building = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcBuilding", name="idf_stem")
    storey = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class="IfcBuildingStorey", name="Ground Floor")

    # Since the site is our top level location, assign it to the project
    # Then place our building on the site, and our storey in the building
    ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = project, product = site)
    ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = site, product = building)
    ifcopenshell.api.run("aggregate.assign_object", ifcmodel, relating_object = building, product = storey)

    # region: translate construction and materials from osmodel to ifc
    # https://docs.ifcopenshell.org/autoapi/ifcopenshell/api/pset/index.html#ifcopenshell.api.pset.edit_pset
    pset_dir = settings.PSET_DATA_DIR
    osmod_mat_schema_path = str(pset_dir.joinpath('osmod_material_schema.json'))
    with open(osmod_mat_schema_path) as f:
        json_data = json.load(f)
        osmod_mat_pset_title = json_data['title']
    osmod_pset_template = ifcopenshell_utils.create_osmod_pset_template(ifcmodel, osmod_mat_schema_path)

    ifc_mat_dict = {}
    for mat_dict in mat_dicts:
        mat_name = mat_dict['name']
        ifc_mat = ifcopenshell.api.run("material.add_material", ifcmodel, name=mat_name)
        pset = ifcopenshell.api.run("pset.add_pset", ifcmodel, product=ifc_mat, name=osmod_mat_pset_title)
        ifcopenshell.api.run("pset.edit_pset", ifcmodel, pset=pset, properties=mat_dict['mat_pset'], pset_template=osmod_pset_template)
        ifc_mat_dict[mat_name] = {'ifc_mat': ifc_mat, 'thickness': mat_dict['thickness']}
        
    for const_dict in const_dicts:
        ifc_mat_set = ifcopenshell.api.run("material.add_material_set", ifcmodel, name=const_dict['name'], set_type="IfcMaterialLayerSet")
        mat_names = const_dict['mat_names']
        for mat_name in mat_names:
            layer = ifcopenshell.api.run("material.add_layer", ifcmodel, layer_set=ifc_mat_set, material=ifc_mat_dict[mat_name]['ifc_mat'])
            ifcopenshell.api.run("material.edit_layer", ifcmodel, layer=layer, attributes={"LayerThickness": ifc_mat_dict[mat_name]['thickness']*1000})
    # endregion: translate construction and materials from osmodel to ifc

    # region: translate osmod space to ifc space

    # endregion: translate osmod space to ifc space
    ifcmodel.write(ifc_path)
    #------------------------------------------------------------------------------------------------------
    # endregion: translate the osmodel data to ifc
    #------------------------------------------------------------------------------------------------------
#===================================================================================================
# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: Main
#===================================================================================================
if __name__=='__main__':
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        osmod_path = args.osmod
    else:
        lines = list(sys.stdin)
        osmod_path = lines[0].strip()

    osmod_path = str(Path(osmod_path).resolve())
    ifc_path = str(Path(args.ifc).resolve())
    

    osmod2ifc(osmod_path, ifc_path, False)

    '''
    python idf2ifc.py ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -i ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    '''
#===================================================================================================
# endregion: Main
#===================================================================================================