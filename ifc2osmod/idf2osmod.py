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
    parser = argparse.ArgumentParser(description = "Convert EP+ Idf geometry to Openstudio Models")
    
    parser.add_argument('idf', type = str,
                        metavar = 'FILE',
                        help = 'The path of the idf model')
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the resultant openstudio file')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the idf filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args


def idf2osmod(idf_path: str, osmod_path: str) -> str:
    '''
    Converts osmodel to ifc.

    Parameters
    ----------
    idf_path : str
        The file path of the Idf.

    osmod_path : str
        The file path of the resultant openstudio model.
    
    Returns
    -------
    str
        The file path of the openstudio result
    '''
    #------------------------------------------------------------------------------------------------------
    # region: read the idf and convert it to a osmodel
    #------------------------------------------------------------------------------------------------------
    idf_stem = Path(idf_path).stem
    osmodel = openstudio_utils.read_idf_file(idf_path)
    osmod_dir = Path(osmod_path).parent
    if osmod_dir.exists() == False:
        osmod_dir.mkdir(parents=True)
    osmod_path = osmod_dir.joinpath(idf_stem + '.osm')
    osmodel.save(osmod_path, True)
    return osmod_path
    #------------------------------------------------------------------------------------------------------
    # endregion: read the idf and convert it to a osmodel
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
        idf_path = args.idf
    else:
        lines = list(sys.stdin)
        idf_path = lines[0].strip()

    idf_path = str(Path(idf_path).resolve())
    osmod_path = str(Path(args.osmod).resolve())
    osmod_path = idf2osmod(idf_path, osmod_path)
    # make sure this output can be piped into another command on the cmd
    print(osmod_path)
    sys.stdout.flush()
#===================================================================================================
# endregion: Main
#===================================================================================================