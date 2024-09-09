import sys
import argparse
from pathlib import Path

import ifc_utils.ifcopenshell_utils as ifcopenshell_utils
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Generate FreeCAD CustomPset.csv from JSON schema")
    
    parser.add_argument('-j', '--json', type = str,
                        metavar = 'DIR',
                        help = 'The directory path of the containing all the json schemas')
    
    parser.add_argument('-c', '--csv', type = str,
                        metavar = 'FILE',
                        help = 'The path of the generated csv')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the json filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args


def json2csv(json_path: str) -> str:
    '''
    Converts osmodel to ifc.

    Parameters
    ----------
    json_path : str
        The file path of the json pset.

    csv_path : str
        The file path of the resultant csv pset.
    
    Returns
    -------
    str
        The file path of the resultant csv pset
    '''
    pset_dict = ifcopenshell_utils.get_default_pset(json_path)
    title = list(pset_dict.keys())[0]
    title_split = title.split('_')
    clean_title = ''
    for t in title_split:
        newt = f"{t[0].upper()}{t[1:]}"
        clean_title+=newt

    csv_str = f"Pset_{clean_title};"

    value = pset_dict[title]
    value_keys = value.keys()
    for cnt,vk in enumerate(value_keys):
        if cnt == len(value_keys) - 1:
            csv_str += f"{vk};{value[vk]['primary_measure_type']}\n"
        else:
            csv_str += f"{vk};{value[vk]['primary_measure_type']};"
    return csv_str

def many_json2csv(json_dir: str, csv_path: str):
    '''
    Converts osmodel to ifc.

    Parameters
    ----------
    json_dir : str
        The directory path of the json pset.

    csv_path : str
        The file path of the resultant csv pset.
    
    Returns
    -------
    str
        The file path of the resultant csv pset
    '''
    files = Path(json_dir).glob('*.json')
    all_csv_str = ''
    for file in files:
        csv_str = json2csv(str(file))
        all_csv_str+=csv_str
    
    with open(csv_path, 'w') as f:
        f.write(all_csv_str)

    return csv_path

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        json_dir = args.json
    else:
        lines = list(sys.stdin)
        json_dir = lines[0].strip()

    csv_path = args.csv

    many_json2csv(json_dir, csv_path)
    print(Path(csv_path).resolve())
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