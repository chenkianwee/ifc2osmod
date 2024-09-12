import sys
import csv
import argparse
import datetime
from pathlib import Path

from dateutil.parser import parse

from ladybug.sql import SQLiteResult
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Convert the data from epsql file into csv file")
    
    parser.add_argument('-s', '--sql', type = str,
                        metavar = 'FILE',
                        help = 'The path of the EP+ sql file')
    
    parser.add_argument('-r', '--res', type = str,
                        metavar = 'DIR',
                        help = 'The directory path of the resultant file')

    parser.add_argument('-p', '--process', action = 'store_true',
                        default=False, help = 'turn it on if piping in the idf filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def write2csv(rows2d: list[list], csv_path: str, mode: str = 'w'):
    # writing to csv file 
    with open(csv_path, mode, newline='') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile) 
        # writing the data rows 
        csvwriter.writerows(rows2d)

def append2row2d(coll: SQLiteResult, row2d: list[list], utc_offset: float):
    # for coll in colls:
    header = coll.header
    unit = header.unit
    meta = header.metadata
    meta_vals = meta.values()
    nmeta = len(meta_vals)
    header_str = ''
    for cnt, v in enumerate(meta_vals):
        if cnt == nmeta -1:
            header_str += f"{v}"
        else:
            header_str += f"{v}_"

    header_str += f"({unit})"
    row2d[0].append(header_str)
    if len(row2d) == 1: # only have header
        dts = coll.datetimes
        tz = datetime.timezone(datetime.timedelta(hours=utc_offset))
        for cnt, data in enumerate(coll):
            dt = dts[cnt]
            dtstr = dt.isoformat()
            pydt = parse(dtstr)
            dt_tz = pydt.replace(tzinfo=tz)
            dtstr = dt_tz.isoformat()
            row = [dtstr, data]
            row2d.append(row)
    else: # already append a previous data set
        for cnt, data in enumerate(coll):
            row2d[cnt+1].append(data)

def extract_sql_info(sql_path: str, res_dir: str):
    '''
    Converts extract information from sql.

    Parameters
    ----------
    sql_path : str
        The sql file path.
    
    res_path: str
        the path of the generated result.
    
    '''
    parent_dir = Path(sql_path).parent.parent
    proj_name = parent_dir.stem
    sql_obj = SQLiteResult(sql_path)
    
    avail_output_names = sql_obj.available_outputs
    loc = sql_obj.location
    utc_offset = loc.time_zone
    data_dict = {}
    for output_name in avail_output_names:
        colls = sql_obj.data_collections_by_output_name(output_name)
        for coll in colls:
            header = coll.header
            anlys_prd = header.analysis_period
            anlys_prd_str = anlys_prd.ToString()
            dkeys = data_dict.keys()
            if anlys_prd_str not in dkeys:
                data_dict[anlys_prd_str] = [['datetime']]

            # add the data into it
            row2d = data_dict[anlys_prd_str]
            append2row2d(coll, row2d, utc_offset)
                
    items = data_dict.items()
    for item in items:
        key = item[0]
        val = item[1]
        key = key.replace('/', '_')
        key = key.replace(' ', '_')
        key = key.replace('@', 'at')
        res_path = Path(res_dir).joinpath(f"{proj_name}_{key}.csv")
        write2csv(val, res_path)

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        sql_filepath = args.sql
    else:
        lines = list(sys.stdin)
        sql_filepath = lines[0].strip()

    res_dir_str = args.res
    res_dir = Path(res_dir_str).resolve()
    res_dir_str = str(res_dir)
    extract_sql_info(sql_filepath, res_dir_str)
    print(res_dir_str)
    sys.stdout.flush()
#===================================================================================================
# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: MAIN
#===================================================================================================
if __name__=='__main__':
    main()
#===================================================================================================
# endregion: MAIN
#===================================================================================================