# ifc2osmod
## Introduction
- actively being developed, still very unstable
- Commandline tools written in Python to convert IFC models to Openstudio Models
    - ifcarch2osmod.py: input a IFC file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - idf2osmod.py: input a EP+ idf file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - osmod2ifc.py: input an Openstudio format (.osm) and it will extract all the relevant information from the model and convert it to IFC.
- utility tools:
    - idf_transition.py: for linux OS, update version of .idf, written to convert PNNL prototype buildings (https://www.energycodes.gov/prototype-building-models) catalogue to EP+ 23.2 


## Getting started
- This tutorial uses Ubuntu 24.04 OS
- install openstudio application 1.8.0 here (https://github.com/openstudiocoalition/OpenStudioApplication/releases/tag/v1.8.0)

1. Create a virtual environment called ifc2osmod
    ```
    python3 -m venv venv/ifc2osmod
    ```
2. Activate the virtual environment.
    ```
    source venv/ifc2osmod/bin/activate
    ```
3. Install the gendgn python library.
    ```
    pip install ifc2osmod
    ```
4. Download the example file from this url https://github.com/chenkianwee/ifc2osmod_gendgn_egs/archive/refs/heads/main.zip
5.  Go to the directory where you have downloaded and unzip the example files for this tutorial.
    ```
    cd ifc2osmod_gendgn_egs
    ```
6. Execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the execute_osmod.py program.
    ```
    ifcarch2osmod -i ifc/small_office.ifc -o res/osmod/small_office.osm | add_sch2osmod -p -b "Small Office" -c 1A | execute_osmod -p -e epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.epw -d epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.ddy -m json/measure_sel.json -out res/osmod/small_office_radiant_pnls
    ```

## Convert idf buildings to osmodel example
- These instructions are only for Ubuntu 24.04. 

### Update the idf to the right version
1. Go to (https://www.energycodes.gov/prototype-building-models) and download [Small Office 90.1-2022 zip file](https://www.energycodes.gov/sites/default/files/2023-10/ASHRAE901_OfficeSmall_STD2022.zip)

2. Once you unzip the file. Look for the file 'ASHRAE901_OfficeSmall_STD2022_NewYork.idf'. Lets conver this idf file to osmodel.

3. We want to open the osmodel in Openstudio Application 1.8. So we need to update the idf file version to 24.1.0. Open the 'ASHRAE901_OfficeSmall_STD2022_NewYork.idf'. It is a text file. Search for the word 'version' using ctrl+f. The version of the idf file should be version 22.1.

4. Download energyplus 24.1.0 from [here](https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/EnergyPlus-24.1.0-9d7789a3ac-Linux-Ubuntu22.04-x86_64.tar.gz). Unzip the file. The IDFVersionUpdater folder is located in the PreProcess folder.

5. Run the following command to transit the file to the target version.
```
idf_transition -u '/EnergyPlus-24.1.0-9d7789a3ac-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater/' -i '/Downloads/ASHRAE901_OfficeSmall_STD2022/ASHRAE901_OfficeSmall_STD2022_NewYork.idf' -c 22.1 -t 24.1 -o 'idf/ASHRAE901_OfficeSmall_STD2022_NewYork_24_1.idf'
```
### Convert the idf to osm 
1. Convert the idf to osm using this command.
```
idf2osmod -i '/idf/ASHRAE901_OfficeSmall_STD2022_NewYork_24_1.idf' -o '/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_NewYork.osm'
```
## Create construction json database to facilitate ifc2osmod conversion
1. This is done by extracting the construction information, either opaque constructions or glazing contruction, from osmodel files in a directory. So put the osmodel files in the same directory.
2. To extract the opaque construction, run the following command.
```
extract_osmod_opq_constr -o '/osmod/' -r '/json/osmod_opq_constr_info.json'  
``` 
3. To extract glazing construction, run the following command:
```
extract_osmod_smpl_glz_constr -o '/osmod/' -r '/json/osmod_smpl_glz_constr_info.json'
```

## Development
1. Download the example files from this url https://github.com/chenkianwee/ifc2osmod_gendgn_egs/archive/refs/heads/main.zip

2. go to the ifc2osmod directory 
    ```
    cd ifc2osmod/src
    ```
### ifcarch2osmod.py + add_sch2osmod.py + execute_osmod.py example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the execute_osmod.py program.
    ```
    python -m ifc2osmod.ifcarch2osmod -i path_to/ifc2osmod_gendgn_egs/ifc/small_office.ifc -o path_to/ifc2osmod_gendgn_egs/res/osmod/small_office.osm | python -m ifc2osmod.add_sch2osmod -p -b "Small Office" -c 1A | python -m ifc2osmod.execute_osmod -p -e path_to/ifc2osmod_gendgn_egs/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.epw -d path_to/ifc2osmod_gendgn_egs/epw/miami/USA_FL_Miami.Intl.AP.722020_TMY3.ddy -m path_to/ifc2osmod_gendgn_egs/json/measure_sel.json -out path_to/ifc2osmod_gendgn_egs/res/osmod/small_office_radiant_pnls
    ```

- The results are stored in the 'ifc2osmod/results' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

### ifcarch2osmod.py + add_sch2osmod.py example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the add_sch2osmod.py program.
    ```
    python -m  ifc2osmod.ifcarch2osmod -i path_to/ifc2osmod_gendgn_egs/ifc/small_office.ifc -o path_to/ifc2osmod_gendgn_egs/res/osmod/small_office.osm | python -m add_sch2osmod -p -b "Small Office" -c 1A
    ```
- The results are stored in the 'path_to/ifc2osmod_gendgn_egs/res' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

### idf_transition.py example
- execute the following command to run an example file. In this command, we update an idf file from 22.1 -> 23.2
    ```
    python -m ifc2osmod.idf_transition -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -c 22.1 -t 23.2
    ```
    ```
    python -m ifc2osmod.idf_transition -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeMedium_STD2007_Miami.idf -o path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeMedium_STD2007_Miami_23.2.idf -c 22.1 -t 23.2
    ```

### idf2osmod.py example
- execute the following command to run an example file. In this command, we convert an idf file to openstudio format
    ```
    python -m ifc2osmod.idf2osmod -i path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -o path_to/ifc2osmod_gendgn_egs/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm
    ```
    ```
    python -m ifc2osmod.idf2osmod -i path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeMedium_STD2007_Miami_23.2.idf -o path_to/ifc2osmod_gendgn_egs/osmod/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.osm
    ```

### osmod2ifcarch.py example
- execute the following command to run an example file. In this command, we convert an .osm file to IFC
    ```
    python -m  ifc2osmod.osmod2ifcarch -o path_to/ifc2osmod_gendgn_egs/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm -i path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```
    ```
    python -m ifc2osmod.osmod2ifcarch -o path_to/ifc2osmod_gendgn_egs/osmod/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.osm -i path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeMedium_STD2007_Miami.ifc
    ```

### idf2osmod.py + osmod2ifcarch.py example
- you can pipe the result of idf2osmod.py into the osmod2ifcarch.py program.
    ```
    python -m  ifc2osmod.idf2osmod -i path_to/ifc2osmod_gendgn_egs/idf/ASHRAE901_OfficeSmall_STD2022_Miami_23.2.idf -o path_to/ifc2osmod_gendgn_egs/osmod/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.osm | python -m ifc2osmod.osmod2ifcarch -p -i path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```

### freecad_custom_pset.py example
```
python -m ifc2osmod.freecad_custom_pset -j ifc2osmod/data/json/ifc_psets/ -c path_to/ifc2osmod_gendgn_egs/csv/CustomPsets.csv
```

### read_ifc_mat_pset.py example
- generate json file
    ```
    python -m ifc2osmod.read_ifc_mat_pset -i path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/json/mat_pset.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.read_ifc_mat_pset -i path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/csv/mat_pset.csv -c
    ```

### read_ifc_envlp_mat_pset.py example
- generate json file
    ```
    python -m ifc2osmod.read_ifc_envlp_mat_pset -i  path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/json/ifc_env_info.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.read_ifc_envlp_mat_pset -i  path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/csv/ifc_env_info.csv -c
    ```

### calc_massless_mat.py example
- generate json file
    ```
    python -m ifc2osmod.calc_massless_mat -i  path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/json/massless_mat_info.json
    ```
- generate csv file
    ```
    python -m ifc2osmod.calc_massless_mat -i  path_to/ifc2osmod_gendgn_egs/ifc/idf2osmod_ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r path_to/ifc2osmod_gendgn_egs/csv/massless_mat_info.csv -c
    ```

### extract_osmod_opq_constr.py example
```
python -m ifc2osmod.extract_osmod_opq_constr -o  path_to/ifc2osmod_gendgn_egs/osmod -r path_to/ifc2osmod_gendgn_egs/json/osmod_opq_constr_info.json
```
### extract_osmod_glz_constr.py example
```
python -m ifc2osmod.extract_osmod_smpl_glz_constr -o  path_to/ifc2osmod_gendgn_egs/osmod -r path_to/ifc2osmod_gendgn_egs/json/osmod_smpl_glz_constr_info.json
```

### eplus_sql2csv.py example
```
python -m ifc2osmod.epsql2csv -s path_to/osmod/small_office_wrkflw/run/eplusout.sql -r ../results/csv/
```
