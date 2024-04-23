import csv
import datetime
from dateutil.parser import parse
import pytz

from ladybug.sql import SQLiteResult
from pathlib import Path
#===================================================================================================
# region: PARAMETERS
#===================================================================================================
# eplusout_sql_path = Path('/home/chenkianwee/kianwee_work/get/projects/grundfos/model/osmod/grundfos/grundfos_wrkflw/run/eplusout.sql')
eplusout_sql_path = Path(__file__).parent.joinpath('ifc2osm_eg_result', 'ifc2osm_eg_result_wrkflw', 'run', 'eplusout.sql')
csv_path = Path(__file__).parent.joinpath('ifc2osm_eg_result', 'res.csv')

# endregion: PARAMETERS
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def write2csv(rows2d: list[list], csv_path: str, mode: str = 'w'):
    # writing to csv file 
    with open(csv_path, mode, newline='') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile) 
        # writing the data rows 
        csvwriter.writerows(rows2d)

# endregion: FUNCTIONS
#===================================================================================================
# region: MAIN
#===================================================================================================
sql_obj = SQLiteResult(eplusout_sql_path.__str__())
avail_output_names = sql_obj.available_outputs

run_names = sql_obj.run_period_names
avail_idx = avail_output_names.index('Zone Air Temperature')
print(avail_output_names)
print(run_names)
print(avail_idx)
data = sql_obj.data_collections_by_output_name(avail_output_names[avail_idx])
# run_indxs = sql_obj.run_period_indices
# print(run_indxs)
# data = sql_obj.data_collections_by_output_name_run_period(avail_output_names[avail_idx], run_indxs[2])

zone_air_year = data[2]
dts = zone_air_year.datetimes
rows2d = [['datetime', avail_output_names[avail_idx]]]
for cnt,zair in enumerate(zone_air_year):
    dt = dts[cnt]
    dtstr = dt.isoformat()
    pydt = parse(dtstr)
    dt_utc = pydt.replace(tzinfo=pytz.utc)
    dt_spore = dt_utc.astimezone(pytz.timezone('Asia/Singapore'))
    dtstr = dt_spore.isoformat()
    # print(dt_utc)
    # print(dt_spore)
    row = [dtstr, zair]
    rows2d.append(row)

write2csv(rows2d, csv_path)

# for d in data:
#     print(d)

# print(len(data))
# print(data[1].header.analysis_period)
# print(data[1].header.metadata)
# print(data_col)
# for d in data_col:
#     header = d.header.metadata
#     print(header)
# print(data_collect)

# print(dts[10].isoformat())
# for a_zair in zone_air_year:
#     print(a_zair)

# endregion: FUNCTIONS