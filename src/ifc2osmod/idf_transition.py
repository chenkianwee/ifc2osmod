import sys
import subprocess
import shutil
import argparse
from pathlib import Path
#===================================================================================================
# region: FUNCTIONS
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Update IDF file version")
    
    parser.add_argument('-u', '--update', type = str,
                        metavar = 'DIR',
                        help = 'The directory path of the updater program to be executed')
    
    parser.add_argument('-i', '--idf', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the idf file to transit')
    
    parser.add_argument('-c', '--curr_version', type = float,
                        metavar = 'FLOAT', 
                        help = 'the version of the current file')
    
    parser.add_argument('-t', '--target_version', type = float,
                        metavar = 'FLOAT', 
                        help = 'The targetted EP+ version')
    
    parser.add_argument('-o', '--output', type = str,
                        metavar = 'FILE', 
                        help = 'The output file path')
    
    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the idf filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def idf_transition(idf_filepath: str, output_filepath: str, bin_dir: str, orig_version: float, target_version: float) -> str:
    '''
    Updates EP+ IDF file from its current version to the target version.

    Parameters
    ----------
    idf_filepath : str
        The file path of the idf file to transit.
    
    output_filepath : str
        The output directory path.

    bin_dir : str
        The directory path of the updater program to be executed.

    orig_version : float
        the version of the current file.

    target_version : float
        The targetted EP+ version.

    '''
    curr_filepath = idf_filepath
    if output_filepath != None:
        output_filepath = str(Path(output_filepath).resolve())
        # copy the idf file from the original folder to the output path
        result_dir = Path(output_filepath).parent
        if not result_dir.exists():
            result_dir.mkdir(parents=True)
        shutil.copy(idf_filepath, output_filepath)
        curr_filepath = output_filepath

    transition_dict = {9.0: 'Transition-V9-0-0-to-V9-1-0', 9.1: 'Transition-V9-1-0-to-V9-2-0', 9.2: 'Transition-V9-2-0-to-V9-3-0',
                       9.3: 'Transition-V9-3-0-to-V9-4-0', 9.4: 'Transition-V9-4-0-to-V9-5-0', 9.5: 'Transition-V9-5-0-to-V9-6-0',
                       9.6: 'Transition-V9-6-0-to-V22-1-0', 22.1: 'Transition-V22-1-0-to-V22-2-0', 22.2: 'Transition-V22-2-0-to-V23-1-0', 
                       23.1: 'Transition-V23-1-0-to-V23-2-0', 23.2: 'Transition-V23-2-0-to-V24-1-0', 24.1: 'latest'}
    
    transition_keys = transition_dict.keys()
    transition_keys = sorted(transition_keys)
    # check if the versions are in the dictionary 
    valid_version = False
    if orig_version in transition_keys and target_version in transition_keys:
        version_diff = target_version - orig_version
        if  version_diff < 0:
            valid_version = False
            print('Original version is higher than targetted version')
        elif version_diff == 0:
            valid_version = False
            print('Original version is the same as targetted version')
        elif version_diff > 0:
            valid_version = True
    
    if valid_version == True:
        orig_index = transition_keys.index(orig_version)
        target_index = transition_keys.index(target_version)
        transition_targets  =transition_keys[orig_index: target_index]
        for tcnt, transition_target in enumerate(transition_targets):
            if tcnt != len(transition_targets) - 1:
                print('Transitioning ...', transition_target, 'to', transition_targets[tcnt+1])
            else:
                print('Transitioning ...', transition_target, 'to', target_version)
            bin_name = transition_dict[transition_target]
            res = subprocess.run(['./' + bin_name, curr_filepath], capture_output=True, text=True, cwd=bin_dir)
            print(res.stdout)
            print(res.stderr)
    else:
        print('input EP+ versions not valid')

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        idf_filepath = args.idf
    else:
        lines = list(sys.stdin)
        idf_filepath = lines[0].strip()

    idf_filepath = str(Path(idf_filepath).resolve())

    bin_dir = args.update
    orig_version = args.curr_version
    target_version = args.target_version

    output_filepath = args.output

    idf_transition(idf_filepath, output_filepath, bin_dir, orig_version, target_version)
# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: Main
if __name__=='__main__':
    main()

# endregion: Main
#===================================================================================================