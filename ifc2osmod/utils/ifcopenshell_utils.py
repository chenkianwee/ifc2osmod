import json
import copy
from pprint import pprint

import numpy as np
import geomie3d
import geomie3d.viz
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate
import ifcopenshell.util.unit

def collect_psets(pset: dict, constr_dicts: dict) -> int:
    '''
    Converts mat pset dictionary to csv str.

    Parameters
    ----------
    pset: dict
        the construction pset to decide whether to collect.
    
    constr_dict: dict
        dictionary of all the construction.

    Returns
    -------
    int
        id of the pset in the dictionary
    '''
    constr_ls = list(constr_dicts.values())
    if pset not in constr_ls:
        constr_id = len(constr_ls)
        constr_dicts[constr_id] = pset
    else:
        constr_id = constr_ls.index(pset)

    return constr_id

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
        mls_psets[mls_id] = {'name': mls_name, 'material_layers': mat_ls, 'material_layers_csv': mls_str}

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

def find_objs_in_relaggregates(ifcmodel: ifcopenshell.file, ifc_obj: ifcopenshell.entity_instance, ifc_class_to_find: str = None, 
                               related_or_relating: str = 'RelatedObjects') -> list[ifcopenshell.entity_instance]:
    """
    find the related objects of interest
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    ifc_obj: ifcopenshell.entity_instance
        the ifc entity to search for

    ifc_class_to_find: str, optional
        the ifc class of interest to find related to ifc_obj through IfcRelAggregates. If None, retrieve all objects

    related_or_relating: str, optional
        default to 'RelatedObjects'. Can specify 'RelatingObject'.

    Returns
    -------
    list[ifcopenshell.entity_instance]
        found ifc objects
    """
    found_objs = []
    invs = ifcmodel.get_inverse(ifc_obj)
    for inv in invs:
        if inv.is_a('IfcRelAggregates'):
            inv_info = inv.get_info()
            if related_or_relating == 'RelatedObjects':
                related_objs = inv_info[related_or_relating]
                for related_obj in related_objs:
                    if ifc_class_to_find is not None:
                        if related_obj.is_a(ifc_class_to_find):
                            found_objs.append(related_obj)
                    else:
                        found_objs.append(related_obj)

            elif related_or_relating == 'RelatingObject':
                relating_obj = inv_info[related_or_relating]
                if ifc_class_to_find is not None:
                    if relating_obj.is_a(ifc_class_to_find):
                        found_objs.append(relating_obj)
                else:
                    found_objs.append(relating_obj)
            
    return found_objs

def find_objs_in_relassignstogroup(ifcmodel: ifcopenshell.file, ifc_obj: ifcopenshell.entity_instance, ifc_class_to_find: str = None,
                                   objs_or_grp: str = 'RelatingGroup') -> list[ifcopenshell.entity_instance]:
    """
    extract all the spacezone information
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    ifc_obj: ifcopenshell.entity_instance
        the object that belongs to the group.

    ifc_class_to_find: str, optional
        the class to find and retrieve. If None, will retrieve all objects.

    objs_or_grp: str, optional
        default to 'RelatingGroup'. 'RelatedObjects' to get all the other objects that is in the same group.

    Returns
    -------
    list[ifcopenshell.entity_instance]
        the group objects the ifc_obj belongs to.
    """
    found_objs = []
    invs = ifcmodel.get_inverse(ifc_obj)
    ifc_obj_info = ifc_obj.get_info()
    ifc_obj_id = ifc_obj_info['GlobalId'] 
    for inv in invs:
        if inv.is_a('IfcRelAssignsToGroup'):
            inv_info = inv.get_info()
            if objs_or_grp == 'RelatingGroup':
                relating_grp = inv_info[objs_or_grp]
                if ifc_class_to_find is not None:
                    if relating_grp.is_a(ifc_class_to_find):
                        found_objs.append(relating_grp)
                else:
                    found_objs.append(relating_grp)

            elif objs_or_grp == 'RelatedObjects':
                relating_objs = inv_info[objs_or_grp]
                for relating_obj in relating_objs:
                    obj_info = relating_obj.get_info()
                    obj_id = obj_info['GlobalId']
                    if obj_id != ifc_obj_id:
                        if ifc_class_to_find is not None:
                            if relating_obj.is_a(ifc_class_to_find):
                                found_objs.append(relating_obj)
                        else:
                            found_objs.append(relating_obj)
    return found_objs

def find_objs_in_relcontainedinspatialstructure(ifcmodel: ifcopenshell.file, ifc_obj: ifcopenshell.entity_instance, ifc_class_to_find: str = None, 
                                                elements_or_structure: str = 'RelatedElements') -> list[ifcopenshell.entity_instance]:
    """
    find the related objects of interest
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    ifc_obj: ifcopenshell.entity_instance
        the ifc entity to search for

    ifc_class_to_find: str, optional
        the ifc class of interest to find related to ifc_obj
    
    elements_or_structure: str, optional
        Default = 'RelatedElements'. 'RelatingStructure' to get the spatial structure.

    Returns
    -------
    list[ifcopenshell.entity_instance]
        found ifc objects
    """
    found_objs = []
    invs = ifcmodel.get_inverse(ifc_obj)
    for inv in invs:
        if inv.is_a('IfcRelContainedInSpatialStructure'):
            inv_info = inv.get_info()
            if elements_or_structure == 'RelatedElements':
                rel_eles = inv_info[elements_or_structure]
                for rel_ele in rel_eles:
                    if ifc_class_to_find is not None:
                        if rel_ele.is_a(ifc_class_to_find):
                            found_objs.append(rel_ele)
                    else:
                        found_objs.append(rel_ele)
            elif elements_or_structure == 'RelatingStructure':
                rel_struct = inv_info[elements_or_structure]
                if ifc_class_to_find is not None:
                    if rel_struct.is_a(ifc_class_to_find):
                        found_objs.append(rel_struct)
                else:
                    found_objs.append(rel_struct)

    return found_objs

def find_spacezones_in_storey(ifcmodel: ifcopenshell.file, ifc_bldgstorey: ifcopenshell.entity_instance) -> list[ifcopenshell.entity_instance]:
    """
    find the related objects of interest
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.
    
    ifc_bldgstorey: ifcopenshell.entity_instance
        the ifc_bldgstorey to search for

    Returns
    -------
    list[ifcopenshell.entity_instance]
        found ifc objects
    """
    found_objs = []
    invs = ifcmodel.get_inverse(ifc_bldgstorey)
    for inv in invs:
        if inv.is_a('IfcRelContainedInSpatialStructure'):
            related_eles = inv.get_info()['RelatedElements']
            for related_ele in related_eles:
                if related_ele.is_a('IfcSpatialZone'):
                    found_objs.append(related_ele)
            
        if inv.is_a('IfcRelAggregates'):
            inv_info = inv.get_info()
            related_objs = inv_info['RelatedObjects']
            for related_obj in related_objs:
                if related_obj.is_a('IfcSpatialZone'):
                    found_objs.append(related_obj)
    return found_objs

def find_srf_closest2this_pt(vert: geomie3d.topobj.Vertex, srf_ls: list[ifcopenshell.entity_instance], 
                             intx_pt: bool = False) -> geomie3d.topobj.Face | tuple[geomie3d.topobj.Face, list[float]]:
    """
    find the surface in srf_ls that is closest to vert.

    Parameters
    ----------
    vert: geomie3d.topobj.Vertex
        the point.

    srf_ls: list[geomie3d.topobj.Face]
        the surfaces to find the closest surface to.
    
    intx_pt: bool, optional
        if set to True, returns the closest point between the vert and the closest surface
        
    Returns
    -------
    geomie3d.topobj.Face | tuple[geomie3d.topobj.Face, list[float]]
        - the face closest to this srf
        - the closest point on the surface to the point
    """
    nsrfs = len(srf_ls)
    vert_rep = np.array([vert])
    vert_rep = np.repeat(vert_rep, nsrfs, axis=0)
    # mid_vert_rep = np.repeat(mid_vert_rep, 1, axis=0)
    dists, intxs = geomie3d.calculate.dist_verts2polyfaces(vert_rep, srf_ls, int_pts=True)
    dists = np.round(dists, decimals=6)
    min_dist = np.min(dists)
    min_indx1 = np.where(dists == min_dist)[0]
    min_indx = min_indx1[0]
    closest_srf = srf_ls[min_indx]

    # print('min dist', min_dist)
    # print('min indx', min_indx1)

    # cmp = geomie3d.create.composite(srf_ls)
    # edges = geomie3d.get.edges_frm_composite(cmp)
    # intx = intxs[min_indx]
    # intx_edge = geomie3d.create.pline_edge_frm_verts([mid_vert, intx])
    # geomie3d.viz.viz([{'topo_list': srf_ls[min_indx:min_indx+1], 'colour': 'red'},
    #                   {'topo_list': [mid_vert], 'colour': 'blue'},
    #                   {'topo_list': [intx], 'colour': 'red'},
    #                   {'topo_list': [intx_edge], 'colour': 'red'},
    #                   {'topo_list': [srf], 'colour': 'blue'},
    #                   {'topo_list': edges, 'colour': 'white'}
    #                   ])
    if intx_pt:
        intx = intxs[min_indx]
        intxyz = intx.point.xyz.tolist()
        return closest_srf, intxyz
    else:
        return closest_srf

def find_srf_closest2this_srf(srf: geomie3d.topobj.Face, srf_ls: list[ifcopenshell.entity_instance]) -> geomie3d.topobj.Face:
    """
    find the surface in srf_ls that is closest to srf.

    Parameters
    ----------
    srf: geomie3d.topobj.Face
        the surface.

    srf_ls: list[geomie3d.topobj.Face]
        the surfaces to find the closest surface to.
    
    Returns
    -------
    geomie3d.topobj.Face
        the face closest to this srf
    """
    midxyz = geomie3d.calculate.face_midxyz(srf)
    mid_vert = geomie3d.create.vertex(midxyz)
    closest_srf = find_srf_closest2this_pt(mid_vert, srf_ls)
    return closest_srf

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

def get_ifc_building_info(ifcmodel: ifcopenshell.file, envlp_pset_name: str = 'Pset_OsmodMassless') -> dict:
    """
    extract all the ifc building information
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    envlp_pset_name: str, optional
        the pset name to retrieve from the building envelope. Default = Pset_OsmodMassless

    Returns
    -------
    dict
        - nested dictionary with the globalid as key
        - each dictionary has the following keys: 
        - name: name
        - ifc_envelope: ifcwall, ifcslab and ifcroof that belongs to this story. 1st lvl key globalid, 2nd lvl keys: pset, surfaces
    """
    bldg_dicts = {}
    buildings = ifcmodel.by_type('IfcBuilding')
    for building in buildings:
        bldg_info = building.get_info()
        bldg_id = bldg_info['GlobalId']
        name =  bldg_info['Name']
        # find all the building storeys in this building and all the envlps in each storeys
        storys = find_objs_in_relaggregates(ifcmodel, building, ifc_class_to_find='IfcBuildingStorey')
        ifc_envlp_dicts = {}
        for story in storys:
            ifc_walls = find_objs_in_relcontainedinspatialstructure(ifcmodel, story, ifc_class_to_find='IfcWall')
            ifc_slabs = find_objs_in_relcontainedinspatialstructure(ifcmodel, story, ifc_class_to_find='IfcSlab')
            ifc_roofs = find_objs_in_relcontainedinspatialstructure(ifcmodel, story, ifc_class_to_find='IfcRoof')
            ifc_envlps = ifc_walls + ifc_slabs + ifc_roofs
            ifc_envlp_dict = get_ifc_envlp_info(ifc_envlps, envlp_pset_name)
            ifc_envlp_dicts.update(ifc_envlp_dict)
        
        bldg_dicts[bldg_id] = {'name': name, 'ifc_envelope': ifc_envlp_dicts}

    return bldg_dicts

def get_ifc_envlp_info(ifc_envlps: list[ifcopenshell.entity_instance], envlp_pset_name: str) -> dict:
    """
    extract all the spacezone information
    
    Parameters
    ----------
    ifc_envlps: list[ifcopenshell.entity_instance]
        ifc model.

    envlp_pset_name: str
        the pset name to retrieve from the building envelope.

    Returns
    -------
    dict
        - ifc_envelope: ifcwall, ifcslab and ifcroof that belongs to this story. 1st lvl key globalid, 
        - 2nd lvl keys: type, predefined_type, pset, surfaces
        - each surface has attributes 'id' of the ifc_envlope dictionary id
    """
    ifc_envlp_dicts = {}
    # ecnt = 0
    all_faces = []
    for ifc_envlp in ifc_envlps:
        envlp_info = ifc_envlp.get_info()
        envlp_type = envlp_info['type']
        envlp_pre_type = envlp_info['PredefinedType']
        envlp_id = envlp_info['GlobalId']
        envlp_pset = ifcopenshell.util.element.get_psets(ifc_envlp, psets_only=True)[envlp_pset_name]
        envlp_faces = ifcopenshell_entity_geom2g3d(ifc_envlp)
        # geomie3d.viz.viz([{'topo_list': envlp_faces, 'colour': 'green'}])
        for envlp_face in envlp_faces:
            envlp_face.attributes = {'id': envlp_id}
        ifc_envlp_dicts[envlp_id] = {'type': envlp_type, 'predefined_type': envlp_pre_type, 'pset': envlp_pset, 'surfaces': envlp_faces}
        all_faces.extend(envlp_faces)
        # print('ecnt', ecnt)
        # ecnt+=1
    # geomie3d.viz.viz([{'topo_list': all_faces, 'colour': 'red'}])
    return ifc_envlp_dicts

def get_ifc_facegeom(ifc_object: ifcopenshell.entity_instance) -> tuple[np.ndarray, np.ndarray]:
    """
    get the face geometry of the ifc entty, only works with ifc entity with geometry
    
    Parameters
    ----------
    ifc_object : ifcopenshell.entity_instance.entity_instance
        ifcopenshell entity.

    ndecimals: int, optional
        round all the numbers to this number of decimals.
    
    Returns
    -------
    result : tuple[np.ndarray, np.ndarray]
        tuple[np.ndarray[number_of_verts, 3], np.ndarray[number_of_faces, 3]] 
    """
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, ifc_object)
    verts = shape.geometry.verts # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
    verts3d = np.reshape(verts, (int(len(verts)/3), 3))
    face_idx = shape.geometry.faces
    face_idx3d = np.reshape(face_idx, (int(len(face_idx)/3), 3))
    return verts3d, face_idx3d

def get_ifc_spatial_zone_info(ifcmodel: ifcopenshell.file, story_dicts: dict, bldg_dicts: dict, pset_name: str = 'Pset_OsmodSpace',
                              envlp_pset_name: str = 'Pset_OsmodThermalResistance') -> tuple[dict, dict]:
    """
    extract all the spacezone information
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    pset_name : str
        The name of the pset to retrieve.

    story_dicts: dict
        - nested dictionary with the globalid as key
        - each dictionary has the following keys: 
        - name: name
        - building: globalid of the building this story belongs to
        - ifc_envelope: ifcwall, ifcslab and ifcroof that belongs to this story

    envlp_pset_name: str, optional
        the pset name to retrieve from the building envelope. Only used if no story id. Default = Pset_OsmodMassless

    Returns
    -------
    tuple[dict, dict]
        - first dictionary is the spatial zone, second dictionary is the envelope construction dictionary
        - nested dictionary with the spatialzone globalid as key
        - each dictionary has the following keys: 
        - name: name
        - pset: pset schema to be translated to ifc pset from ../data/json/ifc_psets/osmod_space_schema.json
        - tzone: the thermal zone globalid the space belongs to
        - spacetype: the spacetype globalid of the space if any
        - story: the building story globalid this space belongs to
        - surfaces: geomie3d surfaces with attributes
        - 'name', 'space', 'type', 'pset', 'construction_id'
        - envelope construction dictionary consist of the key and the thermal resistance of the surface
    """
    envlp_constr_dicts = {}
    spacez_dicts = {}
    ifc_spacezones = ifcmodel.by_type('IfcSpatialZone')
    srf_ls = []
    for spacez in ifc_spacezones:
        space_info = spacez.get_info()
        space_name = space_info['Name']
        space_id = space_info['GlobalId']
        # get the pset
        psets = ifcopenshell.util.element.get_psets(spacez, psets_only=True)
        pset = None
        if pset_name in psets.keys(): 
            pset = psets[pset_name]

        # get the building story this space belongs to
        bldg_story = None 
        bldg_story1 = find_objs_in_relaggregates(ifcmodel, spacez, ifc_class_to_find='IfcBuildingStorey', related_or_relating='RelatingObject')
        bldg_story2 = find_objs_in_relcontainedinspatialstructure(ifcmodel, spacez, ifc_class_to_find='IfcBuildingStorey', 
                                                                  elements_or_structure='RelatingStructure')
        if bldg_story1:
            bldg_story = bldg_story1[0]
        elif bldg_story2:
            bldg_story = bldg_story2[0]
        
        if bldg_story is not None:
            story_id = bldg_story.get_info()['GlobalId']
        else:
            story_id = None

        # get the ifczone
        ifc_grps = find_objs_in_relassignstogroup(ifcmodel, spacez)
        ifc_zone_id = None
        for ifc_grp in ifc_grps:
            if ifc_grp.is_a('IfcZone'):
                ifc_zone_id = ifc_grp.get_info()['GlobalId']

        #TODO: factor in spacetype 

        if space_info['Representation'] != None:
            srfs = ifcopenshell_entity_geom2g3d(spacez)
            srf_ls.extend(srfs)
            # get all the envlps of the story if story is not None
            if story_id is not None:
                # get the envelope from the story
                story_dict = story_dicts[story_id]
                bldg_id = story_dict['building']
                bldg_dict = bldg_dicts[bldg_id]
                ifc_envlp_dicts = bldg_dict['ifc_envelope']
            else:
                # get all the envlp in the ifcmodel
                ifc_walls = ifcmodel.by_type('ifcWall')
                ifc_slabs = ifcmodel.by_type('ifcSlab')
                ifc_roofs = ifcmodel.by_type('ifcRoof')
                ifc_envlps = ifc_walls + ifc_slabs + ifc_roofs
                ifc_envlp_dicts = get_ifc_envlp_info(ifc_envlps, envlp_pset_name)

            # convert the geometries of the ifc envelope into geomie3d geometries for processing
            envlp_vals = ifc_envlp_dicts.values()
            
            envlp_srf_ls = []
            for envlp_val in envlp_vals:
                envlp_srfs = envlp_val['surfaces']
                envlp_srf_ls.extend(envlp_srfs)
            
            for cnt, srf in enumerate(srfs):
                closest_srf = find_srf_closest2this_srf(srf, envlp_srf_ls)
                # if you need to get the thickness of the envelope, using the closest surface
                # assume it has the same normal as the thermalzone surface, find the opposite surface, the distance will be the thickness
                srf_att = closest_srf.attributes
                srf_id = srf_att['id']
                envlp = ifc_envlp_dicts[srf_id]
                envlp_pset = envlp['pset']
                envlp_type = envlp['type']
                if envlp_type == 'IfcWall':
                    srf_type = 'Wall'
                elif envlp_type == 'IfcSlab':
                    if envlp['predefined_type'].lower() == 'roof':
                        srf_type = 'RoofCeiling'
                    elif envlp['predefined_type'].lower() == 'floor':
                        srf_type = 'Floor'
                elif envlp_type == 'IfcRoof':
                    srf_type = 'RoofCeiling'
                else:
                    srf_type = None

                if 'id' in envlp_pset.keys():
                    del envlp_pset['id']
                
                envlp_constr_id = collect_psets(envlp_pset, envlp_constr_dicts)
                envlp_name = space_name + '_envelope_' + str(cnt)
                srf_att = {'name': envlp_name, 'space': space_id, 'type': srf_type, 'construction_id': envlp_constr_id}
                geomie3d.modify.update_topo_att(srf, srf_att)
                # print(srf.attributes)
                # print('srf cnt',cnt)
        else:
            srfs = []

        spacez_dicts[space_id] = {'name': space_name, 'pset': pset, 'tzone': ifc_zone_id, 'spacetype': None, 'story': story_id,
                                  'surfaces': srfs}
        
    # geomie3d.viz.viz([{'topo_list': srf_ls, 'colour': 'red'}])
    return spacez_dicts, envlp_constr_dicts

def get_ifc_story_info(ifcmodel: ifcopenshell.file) -> dict:
    """
    extract all the story information
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    Returns
    -------
    dict
        - nested dictionary with the globalid as key
        - each dictionary has the following keys: 
        - name: name
        - building: globalid of the building this story belongs to 
    """
    story_dicts = {}
    storys = ifcmodel.by_type('IfcBuildingStorey')
    for story in storys[0:]:
        # get the building this story belongs to
        ifcbldg = find_objs_in_relaggregates(ifcmodel, story, ifc_class_to_find='IfcBuilding', related_or_relating='RelatingObject')[0]
        bldg_id = ifcbldg.get_info()['GlobalId']
        story_info = story.get_info()
        story_id = story_info['GlobalId']
        name = story_info['Name']
        story_dicts[story_id] = {'name':name, 'building': bldg_id}

    return story_dicts

def get_ifc_subsrf_info(ifcmodel: ifcopenshell.file, space_zone_dicts: dict, pset_glaze_name: str = 'Pset_OsmodUfactor', 
                        pset_massless_name: str = 'Pset_OsmodThermalResistance'):
    """
    extract all the window and doors information. Append them into the surface attr of the envelops
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    space_zone_dicts: dict
        dictionary generated from the get get_ifc_spatial_zone_info function.

    pset_glaze_name: str, optional
        name of the simple glazing pset, for glass windows and doors. Default = Pset_OsmodSimpleGlazing
    
    pset_massless_name: str, optional
        name of the simple massless pset, for opaque doors. Default = Pset_OsmodMassless

    """
    def create_rays_frm_verts(vertices: list[geomie3d.topobj.Vertex], dir_xyz: list[float]) -> list[geomie3d.utility.Ray]:
        rays = []
        for v in vertices:
            ray = geomie3d.create.ray(v.point.xyz, dir_xyz)
            rays.append(ray)
        return rays

    def extract_intx_frm_hit_rays(hit_rays: list[geomie3d.utility.Ray]) -> list[geomie3d.topobj.Vertex]:
        vs = []
        for r in hit_rays:
            att = r.attributes['rays_faces_intersection']
            intx = att['intersection'][0]
            v = geomie3d.create.vertex(intx)
            vs.append(v)
        return vs

    def calc_vobj_height_width(xyzs: np.ndarray, zdir: list[float], ydir: list[float], viz: bool = False) -> tuple[float, float]:
        '''
        Calculates the height and width of a vertical element using the directions of the normal and x and y direction of the local coordinate.

        Parameters
        ----------
        xyzs : np.ndarray
            np.ndarray[shape(number of points, 3)]. Must be more than 3 points at least.
        
        xdir : list[float]
            The x direction of the vertical object

        ydir : list[float]
            the up/y direction of the vertical object. Obtained by cross product of nrml and xdir

        Returns
        -------
        height_width : tuple[float, float]
            the first value is the height, the second value is width
        '''
        bbox = geomie3d.calculate.bbox_frm_xyzs(xyzs)
        center_xyz = geomie3d.calculate.bboxes_centre([bbox])[0]
        # check the bounding box if it is a flat surface we can get the dimension easier
        xdim = bbox.maxx - bbox.minx
        ydim = bbox.maxy - bbox.miny
        zdim = bbox.maxz - bbox.minz
        win_dims = np.array([xdim, ydim, zdim])
        dim_cond = win_dims == 0
        dim_cond = np.where(dim_cond)[0]
        if dim_cond.size == 0:
            # the bbox is a box
            # project the center xyz up down left right to get the height and width
            r_up = geomie3d.create.ray(center_xyz, ydir)
            ydir_rev = geomie3d.calculate.reverse_vectorxyz(ydir)
            r_dn = geomie3d.create.ray(center_xyz, ydir_rev)
            r_z = geomie3d.create.ray(center_xyz, zdir)
            zdir_rev = geomie3d.calculate.reverse_vectorxyz(zdir)
            r_zneg = geomie3d.create.ray(center_xyz, zdir_rev)
            box = geomie3d.create.boxes_frm_bboxes([bbox])[0]
            box_faces = geomie3d.get.faces_frm_solid(box)
            box_faces = [geomie3d.modify.reverse_face_normal(wf) for wf in box_faces]
            dim_proj_res = geomie3d.calculate.rays_faces_intersection([r_up, r_dn, r_z, r_zneg], box_faces)
            hit_rays = dim_proj_res[0]
            intxs = extract_intx_frm_hit_rays(hit_rays)
            intxs_xyzs = [intx.point.xyz for intx in intxs]
            ct_pts = np.array([center_xyz, center_xyz, center_xyz, center_xyz])
            dists = geomie3d.calculate.dist_btw_xyzs(ct_pts, intxs_xyzs)
            height = dists[0] + dists[1]
            width = dists[2] + dists[3]
            if viz == True:
                center_vert = geomie3d.create.vertex(center_xyz)
                geomie3d.viz.viz([{'topo_list': [box], 'colour': 'blue'},
                                {'topo_list': [center_vert], 'colour': 'red'},
                                {'topo_list': intxs, 'colour': 'red'}])

        elif dim_cond.size == 1:
            #  the bbox is just a surface
            if dim_cond[0] == 0:
                height = zdim
                width = ydim
            if dim_cond[0] == 1:
                height = zdim
                width = xdim
        else:
            print('the bbox is either a line or a point, there is no height nor width')

        return height, width

    # collect all the simple glazing constructions
    win_constr_dicts = {}

    # get all the surfaces from the spatial zones
    sz_vals = space_zone_dicts.values()
    envlp_srfs = []
    for sz_val in sz_vals:
        envlp_srfs.extend(sz_val['surfaces'])

    ifc_windows = ifcmodel.by_type('IfcWindow')
    ifc_doors = ifcmodel.by_type('IfcDoor')
    ifc_subsrfs = ifc_windows + ifc_doors
    windows = []
    for win in ifc_subsrfs[0:]:
        # get the pset of the ifcsubsrf
        win_info = win.get_info()
        win_name = win_info['Name']
        psets = ifcopenshell.util.element.get_psets(win, psets_only=True)#[pset_name]
        pset_keys = list(psets.keys())
        pset = None
        if win_info['type'].lower() == 'ifcdoor':
            if pset_glaze_name in pset_keys:
                srf_type = 'GlassDoor'
                # must be a glass door
                pset = psets[pset_glaze_name]
            elif pset_massless_name in pset_keys:
                srf_type = 'Door'
                # must be an opaque door
                pset = psets[pset_massless_name]
        elif win_info['type'].lower() == 'ifcwindow':
             srf_type = 'FixedWindow'
             pset = psets[pset_glaze_name]

        # find the center point of the window
        verts3d, face_idx3d = get_ifc_facegeom(win)
        g3d_verts = geomie3d.create.vertex_list(verts3d)
        bbox = geomie3d.calculate.bbox_frm_xyzs(verts3d)
        center_xyz = geomie3d.calculate.bboxes_centre([bbox])[0]
        center_vert = geomie3d.create.vertex(center_xyz)
        # find the closest surface to the center pont of this window
        closest_srf, closest_ptxyz = find_srf_closest2this_pt(center_vert, envlp_srfs, intx_pt=True)
        # get the normal of the wall srf and use it for projection later
        n = geomie3d.get.face_normal(closest_srf)
        n_rev = geomie3d.calculate.reverse_vectorxyz(n)
        # move the points alittle further away from the surface so that all can be projected properly to the surface
        cmp_verts = geomie3d.create.composite(g3d_verts)
        target_xyz = geomie3d.calculate.move_xyzs([center_xyz], [n], 1.0)[0]
        mv_cmp_verts = geomie3d.modify.move_topo(cmp_verts, target_xyz, ref_xyz=center_xyz)
        mv_verts = geomie3d.get.vertices_frm_composite(mv_cmp_verts)
        # check if the window is contain within the wall project all the points onto the wall
        rays = create_rays_frm_verts(mv_verts, n_rev)
        proj_res = geomie3d.calculate.rays_faces_intersection(rays, [closest_srf])
        if len(proj_res[0]) == len(g3d_verts):
            is_win_in_wall = True
        else:
            is_win_in_wall = False
        win_srf = None
        if is_win_in_wall:
            # if the window is contain within the wall
            # project the bbox onto the closest surface base on the reverse surface normal
            fuse1 = []
            box = geomie3d.create.boxes_frm_bboxes([bbox])[0]
            box_faces = geomie3d.get.faces_frm_solid(box)
            for box_face in box_faces:
                verts = geomie3d.get.vertices_frm_face(box_face)
                bface_rays = create_rays_frm_verts(verts, n_rev)
                ray_res2 = geomie3d.calculate.rays_faces_intersection(bface_rays, [closest_srf])
                hit_rays2 = ray_res2[0]
                intx_v = extract_intx_frm_hit_rays(hit_rays2)
                fused_intx = geomie3d.modify.fuse_vertices(intx_v)
                if len(fused_intx) > 3:
                    fuse1.extend(fused_intx)
            
            if len(fuse1) != 0:
                fuse2 = geomie3d.modify.fuse_vertices(fuse1)
                win_srf = geomie3d.create.polygon_face_frm_verts(fuse2)
        else:
            # use the center point and project out to the bbox to get the win height and width
            up_dir = [0,0,1]        
            angle = geomie3d.calculate.angle_btw_2vectors(n, up_dir)
            if -90 <= angle <= 90: # the surface is vertical
                if round(angle, 1) != 90:
                    # that means the wall is not straight but slanted
                    z_dir = geomie3d.calculate.cross_product(n, up_dir)
                    rot_mat = geomie3d.calculate.rotate_matrice(z_dir, angle)
                    y_dir = geomie3d.calculate.trsf_xyzs([n], rot_mat)[0]
                else:
                    y_dir = up_dir
                    # get the x-dir of the wall, considering if up is Y and the normal is X
                    z_dir = geomie3d.calculate.cross_product(n, y_dir)
                    # region: for visualizing the wall local coordinate system
                    # y_pt = geomie3d.calculate.move_xyzs([center_xyz], [y_dir], [10])[0]
                    # y_v = geomie3d.create.vertex_list([center_xyz, y_pt])
                    # yedge = geomie3d.create.pline_edge_frm_verts(y_v)

                    # z_pt = geomie3d.calculate.move_xyzs([center_xyz], [z_dir], [10])[0]
                    # z_v = geomie3d.create.vertex_list([center_xyz, z_pt])
                    # zedge = geomie3d.create.pline_edge_frm_verts(z_v)
                    
                    # x_pt = geomie3d.calculate.move_xyzs([center_xyz], [n], [10])[0]
                    # x_v = geomie3d.create.vertex_list([center_xyz, x_pt])
                    # xedge = geomie3d.create.pline_edge_frm_verts(x_v)
                    # endregion: for visualizing the wall local coordinate system
                    # get the window height and width
                    win_height, win_width = calc_vobj_height_width(verts3d, z_dir, y_dir, viz = False)

            # get wall height and width
            wall_verts = geomie3d.get.vertices_frm_face(closest_srf)
            wall_xyzs = [wall_vert.point.xyz for wall_vert in wall_verts]
            wall_height, wall_width = calc_vobj_height_width(wall_xyzs, z_dir, y_dir, viz = False)
            # compare their dimension and make adjustment for the 
            win_dims = np.array([win_height, win_width])
            wall_dims = np.array([wall_height, wall_width])
            dim_cond = win_dims >= wall_dims
            win_dims_rev = np.where(dim_cond, wall_dims-0.5, win_dims)
            # create a rectangle based on the height and width
            win = geomie3d.create.polygon_face_frm_midpt(center_xyz, win_dims_rev[1], win_dims_rev[0],)
            # cs transfer and map the rectangle onto the wall
            orig_xdir = geomie3d.get.face_normal(win)
            orig_ydir = [0, 1, 0]
            orig_cs = geomie3d.utility.CoordinateSystem(center_xyz, orig_xdir, orig_ydir)
            dest_cs = geomie3d.utility.CoordinateSystem(closest_ptxyz, n, y_dir)
            win_srf = geomie3d.modify.trsf_topo_based_on_cs(win, orig_cs, dest_cs)

        del pset['id']

        subsrf_constr_id = collect_psets(pset, win_constr_dicts)        
        win_attr = {'name': win_name, 'type': srf_type, 'construction_id': subsrf_constr_id}
        geomie3d.modify.update_topo_att(win_srf, win_attr)
        if 'children' in closest_srf.attributes.keys():
            closest_srf.attributes['children'].append(win_srf)
        else:
            closest_srf.attributes['children'] = [win_srf]

        windows.append(win_srf)

        # cmp = geomie3d.create.composite(envlp_srfs)
        # edges = geomie3d.get.edges_frm_composite(cmp)
        # geomie3d.viz.viz([{'topo_list': edges, 'colour': 'white'},
        #                   {'topo_list': [closest_srf], 'colour': 'red'},
        #                   {'topo_list': [center_vert], 'colour': 'blue'},])

    # cmp = geomie3d.create.composite(envlp_srfs)
    # edges = geomie3d.get.edges_frm_composite(cmp)
    # geomie3d.viz.viz([{'topo_list': edges, 'colour': 'white'},
    #                   {'topo_list': windows, 'colour': 'red'}])

    return win_constr_dicts

def get_ifc_zone_info(ifcmodel: ifcopenshell.file) -> dict:
    """
    extract all the spacezone information
    
    Parameters
    ----------
    ifcmodel : ifcopenshell.file.file
        ifc model.

    Returns
    -------
    dict
        - nested dictionaries, the globalid of the ifczone is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name
    """
    ifczones = ifcmodel.by_type('IfcZone')
    zone_dicts = {}
    for ifczone in ifczones:
        zone_info = ifczone.get_info()
        globalid = zone_info['GlobalId']
        name = zone_info['Name']
        zone_dicts[globalid] = {'name': name}
    return zone_dicts

def ifcopenshell_entity_geom2g3d(ifc_object: ifcopenshell.entity_instance) -> list[geomie3d.topobj.Face]:
    """
    Retrive the triangulated faces from the ifc_object. Merge the triangulated face from the ifcopenshell geometry into a single geomie3d face. Currently return surfaces without holes.

    Parameters
    ----------
    ifc_object: ifcopenshell.entity_instance.entity_instance
        the ifc_object to retrieve geometry from.
    
    ndecimals: int, optional
        round all the numbers to this number of decimals.

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

    # geomie3d.viz.viz([{'topo_list': flist, 'colour': 'blue'}])
    
    grp_faces = geomie3d.calculate.grp_faces_on_nrml(flist)
    all_merged_faces = grp_faces[1]
    # gcnt = 0
    for grp_f in grp_faces[0]:
        grpf_merged = []
        outline = geomie3d.calculate.find_faces_outline(grp_f)[0]
        n_loose_edges = 3
        loop_cnt = 0
        while n_loose_edges >= 3:
            # arrange the outline into connected path for creating a valid face
            path_dict = geomie3d.calculate.a_connected_path_from_edges(outline)
            outline = path_dict['connected']
            bwire = geomie3d.create.wire_frm_edges(outline)
            mf = geomie3d.create.polygon_face_frm_wires(bwire)
            grpf_merged.append(mf)

            outline = path_dict['loose']
            if loop_cnt == 0:
                n_loose_edges = len(path_dict['loose'])
            else:
                if n_loose_edges - len(path_dict['loose']) == 0:
                    n_loose_edges = 0
                else:        
                    n_loose_edges = len(path_dict['loose'])
            loop_cnt+=1
        
        # geomie3d.viz.viz([{'topo_list': grpf_merged, 'colour': 'blue'}])
        holes_dict = sepr_holes_faces(grpf_merged, grp_f)
        grpf_merged_nh = holes_dict['non_holes']
        n_merged = len(grpf_merged_nh)
        holes = holes_dict['holes']
        if holes:
            # find the host surface the holes belong to
            parent_dict = {}
            for hole in holes:
                # hole_midpt = geomie3d.calculate.face_midxyz(hole)
                hvs = geomie3d.get.bdry_vertices_frm_face(hole)
                hvs = np.array([hvs])
                hvs = np.repeat(hvs, n_merged, axis=0)
                in_polys = geomie3d.calculate.are_verts_in_polygons(hvs, grpf_merged_nh)
                host_indx = []
                for cnt, in_poly in enumerate(in_polys):
                    # look for the first one assumes one hole to one parent surface
                    if False not in in_poly:
                        host_indx.append(cnt)
                        break
                if len(host_indx) == 1:
                    # add the hole onto the parent surface
                    parent_srf = grpf_merged[host_indx[0]]
                    p_nrml = geomie3d.get.face_normal(parent_srf)
                    h_nrml = geomie3d.get.face_normal(hole)
                    is_same_dir = np.isclose(p_nrml, h_nrml)
                    if False not in is_same_dir:
                        hole = geomie3d.modify.reverse_face_normal(hole)
                    hole_wires = geomie3d.get.bdry_wires_frm_face(hole)
                    if host_indx[0] not in parent_dict.keys():
                        parent_dict[host_indx[0]] = [hole_wires]
                    else:
                        parent_dict[host_indx[0]].append(hole_wires)
            parent_items = parent_dict.items()
            for parent_item in parent_items:
                key = parent_item[0]
                hole_wire_list = parent_item[1]
                parent_srf = copy.deepcopy(grpf_merged_nh[key])
                parent_srf.hole_wire_list = hole_wire_list
                parent_srf.update_polygon_surface()
                grpf_merged_nh[key] = parent_srf
        
        # geomie3d.viz.viz([{'topo_list': grpf_merged_nh, 'colour': 'green'}])
        all_merged_faces.extend(grpf_merged_nh)
        # print('gcnt', gcnt)
        # gcnt += 1
    # geomie3d.viz.viz([{'topo_list': all_merged_faces, 'colour': 'green'}])
    # print('ttl face in envlp', len(all_merged_faces))
    return all_merged_faces

def sepr_holes_faces(merged_faces: list[geomie3d.topobj.Face], orig_faces: list[geomie3d.topobj.Face]) -> dict:
    """
    checked if the merged faces are actually holes. This is done by checking if the original triangulated surface mid points fall within the merge faces. If the midpt is not in the merged faces, it must be a hole.

    Parameters
    ----------
    merged_faces: list[geomie3d.topobj.Face]
        the faces to check.

    orig_faces: list[geomie3d.topobj.Face]
        the original faces.
    
    Returns
    -------
    dict
        dictionary with keys 'holes', 'non_holes'.
    """
    non_holes = []
    holes = []
    # get midpts of all the surfaces
    mid_verts = []
    # orig_faces = [orig_faces[0], orig_faces[1]]
    chosen_xyzs = []
    for of in orig_faces:
        midxyz = geomie3d.calculate.face_midxyz(of)
        mid_verts.append(geomie3d.create.vertex(midxyz))

        # chosen_xyzs.append(midxyz.tolist())
        # of_vs = geomie3d.get.bdry_vertices_frm_face(of)
        # of_xyzs = [v.point.xyz.tolist() for v in of_vs
        # chosen_xyzs.extend(of_xyzs)
    

    mid_verts2d = []
    for _ in range(len(merged_faces)):
        mid_verts2d.append(mid_verts)

    # for mf in merged_faces:
        # mf_mid = geomie3d.calculate.face_midxyz(mf)
        # chosen_xyzs.append(mf_mid.tolist())

        # mf_vs = geomie3d.get.bdry_vertices_frm_face(mf).tolist()
        # mf_xyzs = [v.point.xyz.tolist() for v in mf_vs]
        # chosen_xyzs.extend(mf_xyzs)
        
    # is_co = geomie3d.calculate.is_coplanar_xyzs(chosen_xyzs[0:])
    # print(chosen_xyzs)
    # print('=====================')
    # print('is_co', is_co)
    # print('=====================')
    # print(mid_verts2d, merged_faces)
    # geomie3d.viz.viz([{'topo_list': merged_faces, 'colour': 'blue'},
    #                   {'topo_list': mid_verts, 'colour': 'red'}])

    are_verts_in = geomie3d.calculate.are_verts_in_polygons(mid_verts2d, merged_faces)
    for vcnt, vert_in in enumerate(are_verts_in):
        aface = merged_faces[vcnt]
        if True in vert_in:
            non_holes.append(aface)
        else:
            holes.append(aface)

    return {'non_holes': non_holes, 'holes': holes}

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
    assert len(logger.statements) == 0
    # if len(logger.statements) == 0:
    #     print('Validated !!')
    # else:
    #     print('Error !!')
    #     pprint(logger.statements)
