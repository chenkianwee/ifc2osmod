# ifc2osmod
## Introduction
- actively being developed, still very unstable
- Commandline tool written in Python to convert IFC models to Openstudio Models
- two commandline tools written currently:
    - ifc2osmod.py: input a IFC file and it will extract all the relevant information from the model and convert it to Openstudio format (.osm).
    - add_ptac2osmod.py: input an Openstudio file and this script will add Packaged Terminal Air-Conditioning Unit in all of the thermal zones.
- utility tools:
    - idf_transition.py: for linux OS, update version of .idf, written to convert PNNL prototype buildings (https://www.energycodes.gov/prototype-building-models) catalogue to EP+ 23.2 

## Installation
- clone or download the project from github
- pip install dependencies listed in the pyproject.toml file

## ifc2osmod.py + add_ptac2psmod.py example
1. go to the ifc2osmod directory 
    ```
    cd ifc2osmod/ifc2osmod
    ```
2. execute the following command to run an example file. In this command, we first convert an IFC file to OSM file using ifc2osmod.py. Then pipe in the generated OSM file path into the add_ptac2osmod.py program.
    ```
    python ifc2osmod.py -b ../test_data/ifc/building_eg.ifc -o ../results/building_eg/building_eg.osm | python add_ptac2osmod.py -p -e ../test_data/epw/SGP_Singapore.486980_IWEC/SGP_Singapore.486980_IWEC.epw -d ../test_data/epw/SGP_Singapore.486980_IWEC/SGP_Singapore.486980_IWEC.ddy -m ../test_data/json/measure_sel.json
    ```
3. The results are stored in the 'ifc2osmod/test_data' folder. You can examine the files using the OpenStudio Application (https://github.com/openstudiocoalition/OpenStudioApplication/releases). Download version >= 1.7.0 to view the OSM generated from this workflow.

## idf_transition.py example
1. go to the ifc2osmod directory 
    ```
    cd ifc2osmod/ifc2osmod
    ```
2. execute the following command to run an example file. In this command, we update an idf file from 22.1 -> 23.2
    ```
    python idf_transition.py -u /EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/PreProcess/IDFVersionUpdater -i ../test_data/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -o ../results/idf/ASHRAE901_OfficeSmall_STD2022_Miami.idf -c 22.1 -t 23.2
    ```