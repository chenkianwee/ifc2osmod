import sys
import json
import argparse
from pathlib import Path
import openstudio
from openstudio import model as osmod
import openstudio_utils

#===================================================================================================
# region: FUNCTIONS
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Add Packaged Terminal Air-Con (ptac) system to OpenStudio Models and execute the model")
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the osm file')
    
    parser.add_argument('-e', '--epw', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the weather file')
    
    parser.add_argument('-d', '--ddy', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the ddy design day file')
    
    parser.add_argument('-m', '--measure', type = str, default=None,
                        metavar = 'FILE',
                        help = 'The file path of the measures that will be applied to the model')
    
    parser.add_argument('-out', '--output', type = str, default=None,
                        metavar = 'DIR', 
                        help = 'The output directory path')
    
    parser.add_argument('-p', '--process', action = 'store_true', default=False,
                        help = 'turn it on if piping in the osm filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def add_ptac2osmod(osm_filepath: str, res_dir: str, epw_path: str, ddy_path: str, measure_path: str) -> str:
    '''
    Adds Packaged Terminal Air-Conditioning (PTAC) Unit to each thermal zone and execute the openstudio model.

    Parameters
    ----------
    osm_filepath : str
        The file path of the OpenStudio result.

    res_dir : str
        The output directory path for all the results.

    epw_path : str
        The file path of the weather file.

    ddy_path : str
        The file path of the ddy design day file.

    measure_path : str
        The file path of the measures that will be applied to the model.

    '''
    #------------------------------------------------------------------------------------------------------
    # region: setup openstudio model
    #------------------------------------------------------------------------------------------------------
    
    proj_name = str(Path(osm_filepath).stem)
    proj_name = proj_name.lower()
    proj_name = proj_name + '_add_ptac'
    
    measure_list = []
    if measure_path != None:
        with open(measure_path) as open_file:
            data = json.load(open_file)
            measure_list = data['measures']

    m = osmod.Model.load(osm_filepath).get()

    oswrkflw = openstudio.WorkflowJSON()
    m.setWorkflowJSON(oswrkflw)
    thermal_zones = m.getThermalZones()
    openstudio_utils.add_design_days_and_weather_file(m, epw_path, ddy_path)
    openstudio_utils.add_ptac(m, thermal_zones, cooling_type = 'Single Speed DX AC', heating_type=None)
    openstudio_utils.model_apply_prm_sizing_parameters(m)
    
    wrkflw_path = openstudio_utils.save_osw_project(res_dir, m, measure_list, proj_name)
    sim_control = m.getSimulationControl()
    sim_control.setDoZoneSizingCalculation(True)

    openstudio_utils.execute_workflow(wrkflw_path)
    #------------------------------------------------------------------------------------------------------
    # endregion: setup openstudio model
    #------------------------------------------------------------------------------------------------------

# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: Main
if __name__=='__main__':
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        osm_filepath = args.osmod
    else:
        lines = list(sys.stdin)
        osm_filepath = lines[0].strip()

    res_dir = args.output
    if res_dir == None:
        res_dir = str(Path(osm_filepath).parent)

    epw_path = args.epw
    epw_path = str(Path(epw_path).resolve())
    ddy_path = args.ddy
    ddy_path = str(Path(ddy_path).resolve())
    measure_path = args.measure

    add_ptac2osmod(osm_filepath, res_dir, epw_path, ddy_path, measure_path)

# endregion: Main
#===================================================================================================