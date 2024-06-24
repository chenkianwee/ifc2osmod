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
    parser = argparse.ArgumentParser(description = "Add Packaged Terminal Air-Con (ptac) system to OpenStudio Models")
    
    parser.add_argument('-s', '--osm', type = str,
                        metavar = 'osm filepath',
                        help = 'The file path of the osm file')
    
    parser.add_argument('-e', '--epw', type = str,
                        metavar = 'epw weather filepath',
                        help = 'The file path of the weather file')
    
    parser.add_argument('-d', '--ddy', type = str,
                        metavar = 'ddy design day filepath',
                        help = 'The file path of the ddy design day file')
    
    parser.add_argument('-m', '--measure', type = str, default=None,
                        metavar = 'measure json filepath',
                        help = 'The file path of the measures that will be applied to the model')
    
    parser.add_argument('-o', '--output', type = str, default=None,
                        metavar = 'output directory path', 
                        help = 'The output directory path')
    
    parser.add_argument('-p', '--process', action = 'store_true', default=False,
                        help = 'turn it on if piping in the osm filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def main(args: argparse.Namespace) -> str:
    #------------------------------------------------------------------------------------------------------
    # region: setup openstudio model
    #------------------------------------------------------------------------------------------------------
    pipe_input = args.process
    if pipe_input == False:
        osm_filepath = args.osm
    else:
        lines = list(sys.stdin)
        osm_filepath = lines[0].strip()

    res_dir = args.output
    if res_dir == None:
        res_dir = str(Path(osm_filepath).parent)

    proj_name = str(Path(osm_filepath).name)
    proj_name = proj_name.lower()
    proj_name = proj_name.replace('.osm', '')
    proj_name = proj_name + '_add_ptac'
    epw_path = args.epw
    epw_path = str(Path(epw_path).resolve())
    ddy_path = args.ddy
    ddy_path = str(Path(ddy_path).resolve())
    measure_path = args.measure
    
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
    main(args)

# endregion: Main
#===================================================================================================