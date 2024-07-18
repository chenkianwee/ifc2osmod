# ifc2osmod
## Introduction
- actively being developed, still very unstable
- Commandline tools written in Python to convert IFC models to Openstudio Models
    - ifc2osmod.py: input a IFC file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - add_ptac2osmod.py: input an Openstudio file and this script will add Packaged Terminal Air-Conditioning Unit in all of the thermal zones.
    - idf2osmod.py: input a EP+ idf file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - osmod2ifc.py: input an Openstudio format (.osm) and it will extract all the relevant information from the model and convert it to IFC.
- utility tools:
    - idf_transition.py: for linux OS, update version of .idf, written to convert PNNL prototype buildings (https://www.energycodes.gov/prototype-building-models) catalogue to EP+ 23.2 

## Installation
- clone or download the project from github
- pip install dependencies listed in the pyproject.toml file

## Instructions
1. go to the ifc2osmod directory 
    ```
    cd ifc2osmod/ifc2osmod
    ```
### ifc2osmod.py + add_ptac2psmod.py example
- execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the add_ptac2osmod.py program.
    ```
    python ifc2osmod.py -i ../test_data/ifc/building_eg.ifc -o ../results/building_eg/building_eg.osm | python add_ptac2osmod.py -p -e ../test_data/epw/SGP_Singapore.486980_IWEC/SGP_Singapore.486980_IWEC.epw -d ../test_data/epw/SGP_Singapore.486980_IWEC/SGP_Singapore.486980_IWEC.ddy -m ../test_data/json/measure_sel.json
    ```
- The results are stored in the 'ifc2osmod/test_data' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

### idf_transition.py example
- execute the following command to run an example file. In this command, we update an idf file from 22.1 -> 23.2
    ```
    python idf_transition.py -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i ../test_data/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -c 22.1 -t 23.2
    ```

### idf2osmod.py example
- execute the following command to run an example file. In this command, we convert an idf file to openstudio format
    ```
    python idf2osmod.py -i ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o ../results/osmod/ASHRAE901_OfficeSmall_STD2022_Miami.osm
    ```
    ```
    python idf2osmod.py -i ../results/idf/ASHRAE901_OfficeMedium_STD2007_Miami.idf -o ../results/osmod/ASHRAE901_OfficeMedium_STD2007_Miami.osm
    ```

### osmod2ifc.py example
- execute the following command to run an example file. In this command, we convert an .osm file to IFC
    ```
    python osmod2ifc.py -o ../results/osmod/ASHRAE901_OfficeSmall_STD2022_Miami.osm -i ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```
    ```
    python osmod2ifc.py -o ../results/osmod/ASHRAE901_OfficeMedium_STD2007_Miami.osm -i ../results/ifc/ASHRAE901_OfficeMedium_STD2007_Miami.ifc
    ```

### idf2osmod.py + osmod2ifc.py example
- you can pipe the result of idf2osmod.py into the osmod2ifc.py program.
    ```
    python idf2osmod.py -i ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o ../results/osmod/ASHRAE901_OfficeSmall_STD2022_Miami.osm | python osmod2ifc.py -p -i ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc
    ```

### freecad_custom_pset.py example
```
python freecad_custom_pset.py -j ../data/json/ifc_psets/ -c ../results/csv/CustomPsets.csv
```

### read_ifc_mat_pset.py example
- generate json file
    ```
    python read_ifc_mat_pset.py -i ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/mat_pset.json
    ```
- generate csv file
    ```
    python read_ifc_mat_pset.py -i ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/mat_pset.csv -c
    ```

### read_ifc_envlp_mat_pset.py example
- generate json file
    ```
    python read_ifc_envlp_mat_pset.py -i  ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/ifc_env_info.json
    ```
- generate csv file
    ```
    python read_ifc_envlp_mat_pset.py -i  ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/ifc_env_info.csv -c
    ```

### calc_massless_mat.py example
- generate json file
    ```
    python calc_massless_mat.py -i  ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/json/massless_mat_info.json
    ```
- generate csv file
    ```
    python calc_massless_mat.py -i  ../results/ifc/ASHRAE901_OfficeSmall_STD2022_Miami.ifc -r ../results/csv/massless_mat_info.csv -c
    ```