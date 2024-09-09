import sys
import json
import argparse
from pathlib import Path

from openstudio import model as osmod

from .utils import utils
from .utils import openstudio_utils
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Extract all the glazing construction of a OpenStudio Model and index it by U-value")
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'DIR',
                        help = 'The dir containing the openstudio files')
    
    parser.add_argument('-r', '--res', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the resultant file')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the idf filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def calc_smpl_glz_uval(constr_dict: dict, mat_dicts: dict):
    '''
    Extract envelope construction information from openstudio model.

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

    Returns
    -------
    float
        the uvalue of the smpl construction.
    '''
    resistances = []
    mat_handles = constr_dict['mat_handles']
    for mat_handle in mat_handles:
        mat = mat_dicts[mat_handle]
        mat_attr = mat['pset']
        uval = mat_attr['UFactor']['value']
        if uval is not None:
            r = 1/uval
            resistances.append(r)
    if len(resistances) != 0:
        ttl_uval = 1/sum(resistances)
        return ttl_uval
    else:
        return None

def extract_calc_envlp_constr(osmod_dir: str, res_path: str) -> str:
    '''
    Extract envelope construction information from openstudio model.

    Parameters
    ----------
    osmod_dir: str
        The file path of the openstudio model.
    
    res_path: str
        the path of the generated result.
    
    '''
    #------------------------------------------------------------------------------------------------------
    osmod_paths = Path(osmod_dir).glob('*.osm')
    constr_lib = {}
    mat_lib = {}
    for osmod_path in osmod_paths:
        osmodel = osmod.Model.load(osmod_path).get()
        mat_dicts = openstudio_utils.get_osmod_material_info(osmodel)
        constr_dicts = openstudio_utils.get_osmod_construction_info(osmodel)
        constr_vals = constr_dicts.values()
        for constr_val in constr_vals:
            constr_name = constr_val['name']
            uval = calc_smpl_glz_uval(constr_val, mat_dicts)
            if uval is not None:
                uval = round(uval, 2)
                uniq_ids = utils.get_mat_layers_frm_constr(constr_val, mat_dicts, mat_lib)
                if uval not in constr_lib.keys():
                    constr_lib[uval] = {'name': [constr_name], 'material_layers': [uniq_ids]}
                else:
                    uniq_ids_ls = constr_lib[uval]['material_layers']
                    sort_uniq_ids_ls = utils.sort2dls(uniq_ids_ls)
                    sort_uniq_ls = sorted(uniq_ids)
                    if sort_uniq_ls not in sort_uniq_ids_ls:
                        constr_lib[uval]['material_layers'].append(uniq_ids)
                        constr_lib[uval]['name'].append(constr_name)

    constr_lib = dict(sorted(constr_lib.items()))
    osmod_envlp_info = {'material_library': mat_lib, 'construction_library': constr_lib}
    res_path_obj = Path(res_path)
    res_dir_obj = res_path_obj.parent
    if not res_dir_obj.exists():
        res_dir_obj.mkdir(parents=True)
    
    envlp_json_str = json.dumps(osmod_envlp_info, indent=4)
    with open(res_path, 'w') as f:
        f.write(envlp_json_str)

    #------------------------------------------------------------------------------------------------------

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        osmod_dir = args.osmod
    else:
        lines = list(sys.stdin)
        osmod_dir = lines[0].strip()

    res_path = args.res
    res_path = str(Path(res_path).resolve())
    osmod_dir = str(Path(osmod_dir).resolve())
    extract_calc_envlp_constr(osmod_dir, res_path)
    # make sure this output can be piped into another command on the cmd
    print(res_path)
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