import json
from pprint import pprint

import numpy as np
import geomie3d
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate
import ifcopenshell.util.unit

def get_ifc_facegeom(ifc_object: ifcopenshell.entity_instance) -> tuple[np.ndarray, np.ndarray]:
    """
    get the face geometry of the ifc entty, only works with ifc entity with geometry
    
    Parameters
    ----------
    ifc_object : ifcopenshell.entity_instance.entity_instance
        ifcopenshell entity.
    
    Returns
    -------
    result : tuple[np.ndarray, np.ndarray]
        tuple[np.ndarray[number_of_verts, 3], np.ndarray[number_of_faces, 3]] 
    """
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, ifc_object)
    verts = shape.geometry.verts # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
    verts3d = np.reshape(verts, (int(len(verts)/3), 3))
    verts3d = np.round(verts3d, decimals = 2)
    face_idx = shape.geometry.faces
    face_idx3d = np.reshape(face_idx, (int(len(face_idx)/3), 3))
    return verts3d, face_idx3d

def ifcopenshell_entity_geom2g3d(ifc_object: ifcopenshell.entity_instance) -> list[geomie3d.topobj.Face]:
    """
    Retrive the triangulated faces from the ifc_object. Merge the triangulated face from the ifcopenshell geometry into a single geomie3d face. 

    Parameters
    ----------
    ifc_object: ifcopenshell.entity_instance.entity_instance
        the ifc_object to retrieve geometry from.
    
    Returns
    -------
    faces : list[geomie3d.topobj.Face]
        list of geomie3d faces.
    """
    verts3d, face_idx3d = get_ifc_facegeom(ifc_object)
    g3d_verts = geomie3d.create.vertex_list(verts3d)
    face_pts = np.take(g3d_verts, face_idx3d, axis=0)
    flist = []
    for fp in face_pts:
        f = geomie3d.create.polygon_face_frm_verts(fp)
        flist.append(f)
    
    grp_faces = geomie3d.calculate.grp_faces_on_nrml(flist)
    mfs = []
    for grp_f in grp_faces[0]:
        outline = geomie3d.calculate.find_faces_outline(grp_f)[0]
        # geomie3d.viz.viz([{'topo_list': outline, 'colour': 'blue'}])
        n_loose_edges = 3
        loop_cnt = 0
        while n_loose_edges >= 3:
            path_dict = geomie3d.calculate.a_connected_path_from_edges(outline)
            outline = path_dict['connected']
            # geomie3d.viz.viz([{'topo_list': outline, 'colour': 'blue'}])
            bwire = geomie3d.create.wire_frm_edges(outline)
            mf = geomie3d.create.polygon_face_frm_wires(bwire)
            mfs.append(mf)
            outline = path_dict['loose']
            if loop_cnt == 0:
                n_loose_edges = len(path_dict['loose'])
            else:
                if n_loose_edges - len(path_dict['loose']) == 0:
                    n_loose_edges = 0
                else:        
                    n_loose_edges = len(path_dict['loose'])
            loop_cnt+=1
    return mfs

def get_default_pset(pset_path: str, template_only: bool = False) -> dict:
    '''
    Get the default pset dictionary.

    Parameters
    ----------
    pset_path : str
        Path of the default pset schema.

    template_only : bool
        default False, if set to True returns only the template without the title as key.

    Returns
    -------
    dict
        dictionary of the default pset json with the title as the key
    '''
    with open(pset_path) as f:
        pset_schema = json.load(f)
    schema_title = pset_schema['title']
    props = pset_schema['properties']
    prop_names = props.keys()
    template = {}
    for prop_name in prop_names:
        default_val = props[prop_name]['properties']['value']['default']
        ifc_measure = props[prop_name]['properties']['primary_measure_type']['default']
        template[prop_name] = {'value': default_val, 'primary_measure_type': ifc_measure}
    
    if template_only:
        return template
    else:
        pset_schema = {schema_title: template}
        return pset_schema

def create_osmod_pset_template(ifcmodel: ifcopenshell.file, pset_path: str) -> ifcopenshell.entity_instance:
    """
    create ifc material in the ifcmodel
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    pset_path : str
        Path of the default pset schema.

    Returns
    -------
    ifcopenshell.entity_instance
        ifc pset template instance 
    """
    osmod_default = get_default_pset(pset_path)
    osmod_title = list(osmod_default.keys())[0]
    ifc_template = ifcopenshell.api.run("pset_template.add_pset_template", ifcmodel, name=osmod_title)
    props = osmod_default[osmod_title]
    prop_keys = props.keys()
    for prop_key in prop_keys:
        primary_measure_type = props[prop_key]['primary_measure_type']
        # create template properties
        ifcopenshell.api.run("pset_template.add_prop_template", ifcmodel,
                             pset_template=ifc_template, name=prop_key, primary_measure_type=primary_measure_type)
        
    return ifc_template

def create_ifc_entity_with_osmod_pset(ifcmodel: ifcopenshell.file, ifc_class: str, pset_path: str, osmod2ifc_dicts: dict) -> ifcopenshell.entity_instance:
    """
    create ifc entity in the ifcmodel with the specified osmod pset. https://docs.ifcopenshell.org/autoapi/ifcopenshell/api/pset/index.html#ifcopenshell.api.pset.edit_pset
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    ifc_class : str
        the ifc object to create, e.g. IfcSpaceType, IfcSpace.
        
    pset_path : str
        Path of the default pset schema.
    
    osmod2ifc_dicts: dict
        - nested dictionaries, the osmod handle of the spacetype is used as the key on the top level
        - each dictionary in the nested dict must have the following keys: 
        - name: name 
        - pset: pset schema to be translated to ifc pset from ../data/json/ifc_psets

    Returns
    -------
    ifcopenshell.entity_instance
        ifc pset template instance 
    """
    with open(pset_path) as f:
        json_data = json.load(f)
        osmod_pset_title = json_data['title']
    osmod_pset_template = create_osmod_pset_template(ifcmodel, pset_path)

    ifc_objs = []
    osmod2ifc_vals = osmod2ifc_dicts.values()
    for osmod2ifc_val in osmod2ifc_vals:
        osmod2ifc_name = osmod2ifc_val['name']
        ifc_obj = ifcopenshell.api.run("root.create_entity", ifcmodel, ifc_class=ifc_class, name=osmod2ifc_name)
        pset = ifcopenshell.api.run("pset.add_pset", ifcmodel, product=ifc_obj, name=osmod_pset_title)
        ifcopenshell.api.run("pset.edit_pset", ifcmodel, pset=pset, properties=osmod2ifc_val['pset'], pset_template=osmod_pset_template)
        ifc_objs.append(ifc_obj)

    return ifc_objs

def validate_ifc(ifc_path: str):
    """
    validate the ifc file
    
    Parameters
    ----------
    ifc_path : str
        path of ifc model. 
    """
    # validate the generated ifc file
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(ifc_path, logger, express_rules=True)
    
    if len(logger.statements) == 0:
        print('Validated !!')
    else:
        print('Error !!')
        pprint(logger.statements)

def convert_pset2csv_str(csv_header_str: str, csv_content_str: str, chosen_pset: dict) -> tuple[str, str]:
    '''
    Converts mat pset dictionary to csv str.

    Parameters
    ----------
    csv_header_str: str
        headers of the csv file.
    
    csv_content_str: str
        the content of the csv.
    
    chosen_pset: dict
        the pset dictionary of the material

    Returns
    -------
    tuple[str, str]
        the csv_header_str, csv_content_str
    '''
    pset_keys = chosen_pset.keys()
    if not csv_header_str:
        for kcnt,key in enumerate(pset_keys):
            if kcnt == len(pset_keys) - 1:
                csv_header_str+=f"{key}\n"
            else:
                csv_header_str+=f"{key},"   
    for kcnt,key in enumerate(pset_keys):
        value = chosen_pset[key]
        if kcnt == len(pset_keys)-1:
            csv_content_str += f"{value}\n"
        else:
            csv_content_str += f"{value},"

    return csv_header_str, csv_content_str

def extract_mat_layer_sets_pset(ifcmodel: ifcopenshell.file, pset_name: str, is_calc_massless: bool = False) -> dict:
    """
    extract material layer set with the specified pset from the ifcmodel

    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    pset_name : str
        The name of the pset to retrieve.
        
    is_calc_massless : bool, optional
        Default = False. If set True dictionary will of each material layer set will have 'massless' key.

    Returns
    -------
    dict
        - a dictionary on the first level the material layer set 'id' as key to another dict with the following keys
        - material_layers: list[dict] of the pset.
        - material_layers_csv: str converted from the dictionaries written in csv form
        - if is_calc_massless is True
        - massless: dictionary of the massless material keys 'Roughness', 'ThermalAbsorptance', 'SolarAbsorptance', 'VisibleAbsorptance', 'ThermalResistance'
        - massless_csv: csv str of the dictionary from massless
    """
    length_scale = ifcopenshell.util.unit.calculate_unit_scale(ifcmodel, unit_type='LENGTHUNIT')
    mat_layer_sets = ifcmodel.by_type('IfcMaterialLayerSet')
    mls_psets = {}
    for mls in mat_layer_sets:
        mls_info = mls.get_info()
        mls_name = mls_info['LayerSetName']
        mls_id = mls_info['id']
        mat_layers = mls_info['MaterialLayers']
        mat_ls = []
        roughs = []
        tabsorps = []
        sabsorps = []
        vabsorps = []
        resistances = []
        csv_header_str = ''
        csv_content_str = ''
        for mat_layer in mat_layers:
            ml_info = mat_layer.get_info()
            mat = ml_info['Material']
            thickness = ml_info['LayerThickness']*length_scale
            chosen_pset = ifcopenshell.util.element.get_psets(mat, psets_only=True)[pset_name]
            chosen_pset['Thickness'] = thickness
            chosen_pset['Name'] = mat.Name
            chosen_pset = {'Name': chosen_pset.pop('Name'), 'Thickness': chosen_pset.pop('Thickness'), **chosen_pset}
            if is_calc_massless:
                conductivity = chosen_pset['Conductivity']    
                if conductivity is not None:
                    resistance = thickness/conductivity
                    chosen_pset['ThermalResistance'] = resistance
                rough = chosen_pset['Roughness']
                if rough == 'VeryRough':
                    rough = 6
                elif rough == 'Rough':
                    rough = 5
                elif rough == 'MediumRough':
                    rough = 4
                elif rough == 'MediumSmooth':
                    rough = 3
                elif rough == 'Smooth':
                    rough = 2
                elif rough == 'VerySmooth':
                    rough = 1
                roughs.append(rough)
                tabsorps.append(chosen_pset['ThermalAbsorptance'])
                sabsorps.append(chosen_pset['SolarAbsorptance'])
                vabsorps.append(chosen_pset['VisibleAbsorptance'])
                resistances.append(chosen_pset['ThermalResistance'])

            mat_ls.append(chosen_pset)
            csv_header_str, csv_content_str = convert_pset2csv_str(csv_header_str, csv_content_str, chosen_pset)

        mls_str = f"{mls_name}\n{csv_header_str}{csv_content_str}"
        mls_psets[mls_id] = {'material_layers': mat_ls, 'material_layers_csv': mls_str}

        if is_calc_massless:
            # average out all the layers and calc the total resistance
            if None not in resistances:
                avg_rough = int(sum(roughs)/len(roughs))
                if avg_rough >= 6:
                    avg_rough = 'VeryRough'
                elif avg_rough == 5:
                    avg_rough = 'Rough'
                elif avg_rough == 4:
                    avg_rough = 'MediumRough'
                elif avg_rough == 3:
                    avg_rough = 'MediumSmooth'
                elif avg_rough == 2:
                    avg_rough = 'Smooth'
                elif avg_rough <= 1:
                    avg_rough = 'VerySmooth'

                avg_tabsorp = sum(tabsorps)/len(tabsorps)
                avg_sabsorp = sum(sabsorps)/len(sabsorps)
                avg_vabsorp = sum(vabsorps)/len(vabsorps)
                ttl_r = sum(resistances)
                mls_psets[mls_id]['massless'] = {'Roughness': avg_rough, 'ThermalAbsorptance': avg_tabsorp, 'SolarAbsorptance':avg_sabsorp,
                                                'VisibleAbsorptance': avg_vabsorp, 'ThermalResistance': ttl_r}
                
                massless_csv_str="Massless\nRoughness,ThermalAbsorptance,SolarAbsorptance,VisibleAbsorptance,ThermalResistance\n"
                massless_csv_str+=f"{avg_rough},{avg_tabsorp},{avg_sabsorp},{avg_vabsorp},{ttl_r}\n"
                mls_psets[mls_id]['massless_csv'] = massless_csv_str

    return mls_psets

def extract_envlp_mat_layer_pset(ifcmodel: ifcopenshell.file, mls_psets: dict) -> tuple[dict, str]:
    """
    extract the envelope and material layer set with the specified pset from the ifcmodel
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    mls_pset : dict
        - a dictionary on the first level the material layer set 'id' as key to another dict with the following keys
        - material_layers: list[dict] of the pset.
        - material_layers_csv: str converted from the dictionaries written in csv form
        - if is_calc_massless is True
        - massless: dictionary of the massless material keys 'Roughness', 'ThermalAbsorptance', 'SolarAbsorptance', 'VisibleAbsorptance', 'ThermalResistance'
        - massless_csv: csv str of the dictionary from massless

    Returns
    -------
    tuple[dict, str]
        - dict: dictionary of each envelope with this material layer set property set 
        - str: the dictionary converted to csv str
    """
    walls = ifcmodel.by_type('IfcWall')
    floors = ifcmodel.by_type('IfcSlab')
    roofs = ifcmodel.by_type('IfcRoof')
    windows = ifcmodel.by_type('IfcWindow')
    doors = ifcmodel.by_type('IfcDoor')
    envlps = walls + floors + roofs + windows + doors
    envlp_json = {}
    csv_str = ''
    for envlp in envlps:
        envlp_name = envlp.Name
        csv_str+=f"{envlp_name}\n"
        invs = ifcmodel.get_inverse(envlp)
        envlp_json[envlp_name] = {}
        mat_found = False
        # look for material associated with the envelope object
        for inv in invs:
            # find the IfcRelAssociatesMaterial
            if inv.is_a('IfcRelAssociatesMaterial'):
                inv_info = inv.get_info()
                mat_usage = inv_info['RelatingMaterial'].get_info()
                layer_set = mat_usage['ForLayerSet'].get_info()
                layer_set_name = layer_set['LayerSetName']
                layer_set_id = layer_set['id']
                mat_set = mls_psets[layer_set_id]
                if 'massless' in mat_set.keys():
                    envlp_json[envlp_name] = {'massless': mat_set['massless'], layer_set_name: mat_set['material_layers']}
                    csv_str+=mat_set['massless_csv']
                    csv_str+=f"{mat_set['material_layers_csv']}\n"
                else:
                    envlp_json[envlp_name] = {layer_set_name: mat_set['material_layers']}
                    csv_str+=f"{mat_set['material_layers_csv']}\n"
                mat_found = True
                break

        if mat_found == False:
            csv_str+='\n'
    
    return envlp_json, csv_str