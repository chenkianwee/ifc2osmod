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
    parser = argparse.ArgumentParser(description = "Read the IFC file and extract the osmod_material pset as a csv file")
    
    parser.add_argument('-i', '--ifc', type = str,
                        metavar = 'FILE',
                        help = 'The ifc path')
    
    parser.add_argument('-r', '--res', type = str,
                        metavar = 'FILE',
                        help = 'The path of the generated file either JSON or csv')
    
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

def read_ifc_mat_pset(ifc_path: str, pset_name: str, res_path: str, is_csv: bool) -> str:
    '''
    Converts osmodel to ifc.

    Parameters
    ----------
    ifc_path : str
        The file path of the ifc.

    pset_name : str
        The name of the pset.
    
    res_path: str
        the path of the generated result.

    is_csv: bool
        True will generate csv.

    Returns
    -------
    str
        The file path of the resultant file
    '''
    #------------------------------------------------------------------------------------------------------
    model = ifcopenshell.open(ifc_path)
    mats = model.by_type('IfcMaterial')
    mat_json = {}
    csv_header_str = ''
    csv_content_str = ''
    for mat in mats:
        mat_name = mat.Name
        psets = ifcopenshell.util.element.get_psets(mat, psets_only=True)
        chosen_pset = psets[pset_name]
        if is_csv:
            chosen_pset['Name'] = mat_name
            chosen_pset = {'Name': chosen_pset.pop('Name'), **chosen_pset}
            csv_header_str, csv_content_str = ifcopenshell_utils.convert_pset2csv_str(csv_header_str, csv_content_str, chosen_pset)
        else:
            mat_json[mat_name] = chosen_pset

    res_path_obj = Path(res_path)
    res_path_dir_obj = res_path_obj.parent
    if not res_path_dir_obj.exists():
        res_path_dir_obj.mkdir(parents=True)

    if is_csv:
        csv_str = csv_header_str + csv_content_str
        with open(res_path, 'w') as f:
            f.write(csv_str)
    else:
        pretty_json_data = json.dumps(mat_json, indent=4)
        with open(res_path, 'w') as f:
            f.write(pretty_json_data)

    return res_path
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
    read_ifc_mat_pset(ifc_path, pset_name, res_path, is_csv)
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