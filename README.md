# ifc2osmod
## Introduction
- actively being developed, still very unstable
- Commandline tools written in Python to convert IFC models to Openstudio Models
    - ifcarch2osmod.py: input a IFC file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - idf2osmod.py: input a EP+ idf file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - osmod2ifc.py: input an Openstudio format (.osm) and it will extract all the relevant information from the model and convert it to IFC.
- utility tools:
    - idf_transition.py: for linux OS, update version of .idf, written to convert PNNL prototype buildings (https://www.energycodes.gov/prototype-building-models) catalogue to EP+ 23.2 

## Installation
- clone or download the project from github
- pip install dependencies listed in the pyproject.toml file

## Getting started
### ifcarch2osmod + add_sch2osmod + execute_osmod example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the execute_osmod.py program.
    ```
    ifcarch2osmod -i ../test_data/ifc/small_office.ifc -o ../results/osmod/small_office.osm | add_sch2osmod -p -b "Small Office" -c 1A | execute_osmod -p -e ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.epw -d ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.ddy -m ../test_data/json/measure_sel.json -out ../results/osmod/small_office_radiant_pnls
    ```

## Development
### Instructions
1. go to the ifc2osmod directory 
    ```
    cd ifc2osmod/src
    ```
### ifcarch2osmod.py + add_sch2osmod.py + execute_osmod.py example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the execute_osmod.py program.
    ```
    python -m ifc2osmod.ifcarch2osmod -i ../test_data/ifc/small_office.ifc -o ../results/osmod/small_office.osm | python -m ifc2osmod.add_sch2osmod -p -b "Small Office" -c 1A | python -m ifc2osmod.execute_osmod -p -e ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.epw -d ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.ddy -m ../test_data/json/measure_sel.json -out ../results/osmod/small_office_radiant_pnls
    ```
    ```
    python -m ifc2osmod.ifcarch2osmod -i ../test_data/ifc/small_office.ifc -o ../results/osmod/small_office.osm | python -m add_sch2osmod -p -b "Small Office" -c 1A | python -m execute_osmod -p -e ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.epw -d ../test_data/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.ddy -m ../test_data/json/measure_sel.json
    ```
- The results are stored in the 'ifc2osmod/results' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

### ifcarch2osmod.py + add_sch2osmod.py example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the add_sch2osmod.py program.
    ```
    python -m  ifc2osmod.ifcarch2osmod -i ../test_data/ifc/small_office.ifc -o ../results/osmod/small_office.osm | python -m add_sch2osmod -p -b "Small Office" -c 1A
    ```
- The results are stored in the 'ifc2osmod/results' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

### idf_transition.py example
- execute the following command to run an example file. In this command, we update an idf file from 22.1 -> 23.2
    ```
    python -m ifc2osmod.idf_transition -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i ../test_data/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -c 22.1 -t 23.2
    ```
    ```
    python -m ifc2osmod.idf_transition -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i ../test_data/idf/ASHRAE901_OfficeMedium_STD2007_Miami.idf -o ../results/idf/ASHRAE901_OfficeMedium_STD2007_Miami_23.2.idf -c 22.1 -t 23.2
    ```

### idf2osmod.py example
- execute the following command to run an example file. In this command, we convert an idf file to openstudio format
    ```
    python -m ifc2osmod.idf2osmod -i ../test_data/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -o ../results/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm
    ```
    ```
    python -m ifc2osmod.idf2osmod -i ../test_data/idf/ASHRAE901_OfficeMedium_STD2007_Miami_23.2.idf -o ../results/osmod/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.osm
    ```

### osmod2ifcarch.py example
- execute the following command to run an example file. In this command, we convert an .osm file to IFC
    ```
    python -m  ifc2osmod.osmod2ifcarch -o ../test_data/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm -i ../results/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```
    ```
    python -m ifc2osmod.osmod2ifcarch -o ../test_data/osmod/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.osm -i ../results/ifc/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.ifc
    ```

### idf2osmod.py + osmod2ifcarch.py example
- you can pipe the result of idf2osmod.py into the osmod2ifcarch.py program.
    ```
    python -m  ifc2osmod.idf2osmod -i ../test_data/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -o ../results/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm | python -m ifc2osmod.osmod2ifcarch -p -i ../results/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```

### freecad_custom_pset.py example
```
python -m ifc2osmod.freecad_custom_pset -j ../data/json/ifc_psets/ -c ../results/csv/CustomPsets.csv
```

### read_ifc_mat_pset.py example
- generate json file
    ```
    python -m ifc2osmod.read_ifc_mat_pset -i ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/mat_pset.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.read_ifc_mat_pset -i ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/mat_pset.csv -c
    ```

### read_ifc_envlp_mat_pset.py example
- generate json file
    ```
    python -m ifc2osmod.read_ifc_envlp_mat_pset -i  ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/ifc_env_info.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.read_ifc_envlp_mat_pset -i  ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/ifc_env_info.csv -c
    ```

### calc_massless_mat.py example
- generate json file
    ```
    python -m ifc2osmod.calc_massless_mat -i  ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/massless_mat_info.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.calc_massless_mat -i  ../test_data/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/massless_mat_info.csv -c
    ```

### extract_osmod_opq_constr.py example
```
python -m ifc2osmod.extract_osmod_opq_constr -o  ../test_data/osmod -r ../results/json/osmod_opq_constr_info.json
```
### extract_osmod_glz_constr.py example
```
python -m ifc2osmod.extract_osmod_smpl_glz_constr -o  ../test_data/osmod -r ../results/json/osmod_smpl_glz_constr_info.json
```

### eplus_sql2csv.py example
```
python -m ifc2osmod.epsql2csv -s ../results/osmod/small_office_wrkflw/run/eplusout.sql -r ../results/csv/
```
