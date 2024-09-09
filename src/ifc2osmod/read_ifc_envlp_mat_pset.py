import sys
import json
import argparse
from pathlib import Path

import ifcopenshell
import ifc_utils.ifcopenshell_utils as ifcopenshell_utils
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Read the IFC file and extract the envelope (wall,roof,floor,window,door) and its material info (osmod_material pset) as a csv file")
    
    parser.add_argument('-i', '--ifc', type = str,
                        metavar = 'FILE',
                        help = 'The ifc path')
    
    parser.add_argument('-r', '--res', type = str,
                        metavar = 'FILE',
                        help = 'The path of the generated csv')

    parser.add_argument('-ps', '--pset', type = str, default='osmod_material',
                        metavar = 'NAME',
                        help = 'The name of the pset to retrieve')

    parser.add_argument('-c', '--csv', action = 'store_true', default=False,
                        help = 'if turned on generate csv')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the ifc path')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def read_ifc_envlp_constr_info(ifc_path: str, pset_name: str, res_path: str, is_csv: bool) -> str:
    '''
    Retrieve construction info of ifc envelope objects.

    Parameters
    ----------
    ifc_path : str
        The file path of the ifc.

    pset_name : str
        The name of the pset.

    res_path : str
        The file path of the generated result.

    is_csv : bool
        True will generate csv file, false will generate json file.

    Returns
    -------
    str
        The file path of the resultant file.
    '''
    #------------------------------------------------------------------------------------------------------
    model = ifcopenshell.open(ifc_path)
    mls_psets = ifcopenshell_utils.extract_mat_layer_sets_pset(model,pset_name)
    envlp_json, csv_str = ifcopenshell_utils.extract_envlp_mat_layer_pset(model, mls_psets)

    res_path_obj = Path(res_path)
    res_dir_obj = res_path_obj.parent
    if not res_dir_obj.exists():
        res_dir_obj.mkdir(parents=True)

    if is_csv:
        with open(res_path, 'w') as f:
            f.write(csv_str)
    else:
        envlp_json_str = json.dumps(envlp_json, indent=4)
        with open(res_path, 'w') as f:
            f.write(envlp_json_str)
    #------------------------------------------------------------------------------------------------------

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        ifc_path = args.ifc
    else:
        lines = list(sys.stdin)
        ifc_path = lines[0].strip()
    res_path = args.res
    pset_name = args.pset
    is_csv = args.csv
    read_ifc_envlp_constr_info(ifc_path, pset_name, res_path, is_csv)
    print(Path(res_path).resolve())
    # make sure this output can be piped into another command on the cmd
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