def flatten_mat_dict(mat_dict: dict) -> dict:
    '''
    Remove the pset key and flatten all its values in the material dictionary.

    Parameters
    ----------
    mat_dict: dict
        each dictionary has the following keys: 
        - name: name of the material
        - thickness: thickness of the material in meter
        - pset: pset schema to be translated to ifc pset from ../data/json/osmod_material_schema.json

    Returns
    -------
    dict
        the flatten dictionary.
    '''
    new_dict = {'name':mat_dict['name'], 'thickness':mat_dict['thickness']}
    pset = mat_dict['pset']
    pset_items = pset.items()
    for pitem in pset_items:
        new_dict[pitem[0].lower()] = pitem[1]['value']
    
    return new_dict

def get_mat_layers_frm_constr(constr_dict: dict, mat_dicts: dict, mat_lib: dict) -> list[int]:
    '''
    Get all the mat layers from a construction and store them in mat_lib with a unique id.

    Parameters
    ----------
    constr_dict: dict
        dictionary of the construction.
    
    mat_dicts: dict
        nested dictionaries, the osmod handle of the material is used as the key on the top level
        - each dictionary has the following keys: 
        - name: name of the material
        - thickness: thickness of the material in meter
        - pset: pset schema to be translated to ifc pset from ../data/json/osmod_material_schema.json

    mat_lib: dict
        nested dictionaries, the uniq_id of the material is used as the key on the top level
        - dict from the function flatten_mat_dict() 

    Returns
    -------
    list[int]
        the unique_id of the materials in the mat_lib dictionary.
    '''
    def rmv_name(mat_lib_vals):
        mat_lib_vals_no_name = []
        for mat_lib_val in mat_lib_vals:
            mat_lib_val_no_name = dict(mat_lib_val)
            mat_lib_val_no_name.pop('name')
            mat_lib_vals_no_name.append(mat_lib_val_no_name)
        return mat_lib_vals_no_name

    # lets get all the materials 
    mat_handles = constr_dict['mat_handles']
    uniq_ids = []
    for mat_handle in mat_handles:
        mat = mat_dicts[mat_handle]
        mat = flatten_mat_dict(mat)
        mat_no_name = dict(mat)
        mat_no_name.pop('name')
        mat_lib_vals = list(mat_lib.values())
        mat_lib_vals_no_name = rmv_name(mat_lib_vals)
        if mat_no_name not in mat_lib_vals_no_name:
            uniq_id = len(mat_lib_vals)
            mat_lib[uniq_id] = mat
        else:
            mat_lib_keys = list(mat_lib.keys())
            key_indx = mat_lib_vals_no_name.index(mat_no_name)
            uniq_id = mat_lib_keys[key_indx]
        uniq_ids.append(uniq_id)
    return uniq_ids

def sort2dls(ls_2d: list[list[int]]) -> list[list[int]]:
    sorted_2d = []
    for ls in ls_2d:
        sorted_ls = sorted(ls)
        sorted_2d.append(sorted_ls)
    return sorted_2d