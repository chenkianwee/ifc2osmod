from math import inf
import sys
import argparse
from pathlib import Path

import openstudio
from openstudio import model as osmod

from .utils import openstudio_utils
#===================================================================================================
# region: FUNCTIONS
#===================================================================================================
def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Add Schedules to the OpenStudio Models")
 
    # defining arguments for parser object
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE',
                        help = 'The file path of the OpenStudio result')
    
    parser.add_argument('-b', '--btype', type = str,
                        metavar = 'VAR',
                        help = 'the building type')

    parser.add_argument('-c', '--climate', type = str,
                        metavar = 'VAR',
                        help = 'the climate of the building')

    parser.add_argument('-p', '--process', action = 'store_true', default=False,
                        help = 'turn it on if piping in ifc filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def add_sch2osmod(osmod_path: str, bldg_type: str, climate_zone: str) -> str:
    '''
    Adds schedule to openstudio model.

    Parameters
    ----------
    osmod_path : str
        The file path of the OpenStudio result.

    bldg_type: str
        The 18 building prototypes 'https://www.energycodes.gov/prototype-building-models#ASHRAE'. 
        - Small Office, Medium Office, Large Office, Stand-alone Retail, Strip Mall, Primary School, Secondary School, Outpatient Healthcare, Hospital,
        - Small Hotel, Large Hotel, Warehouse (non-refrigerated), Quick Service Restaurant, Full Service Restaurant, Mid-rise Apartment, 
        - High-rise Apartment, Single-family, Multi-family low-rise

    climate_zone: str
        The the climate zone covered by the 18 building prototypes 'https://www.energycodes.gov/prototype-building-models#ASHRAE'.
        - 1A, 2A, 2B, 3A, 3B, 3C, 4A, 4B, 4C, 5A, 5B, 5C, 6A, 6B, 7, 8

    Returns
    -------
    str
        The file path of the OpenStudio result
    '''
    osmodel = osmod.Model.load(osmod_path).get()
    #------------------------------------------------------------------------------------------------------
    # region: read the openstudio model file based on the building type and climate
    #------------------------------------------------------------------------------------------------------
    if bldg_type.lower() == 'small office' and climate_zone.lower() == '1a':
        # region: setup the schedules 
        # setup time
        time9 = openstudio.openstudioutilitiestime.Time(0,9,0,0)
        time17 = openstudio.openstudioutilitiestime.Time(0,18,0,0)
        time24 = openstudio.openstudioutilitiestime.Time(0,24,0,0)
        # region:setup schedule type limits
        sch_type_lim_frac = osmod.ScheduleTypeLimits(osmodel)
        sch_type_lim_frac.setName('fractional')
        sch_type_lim_frac.setLowerLimitValue(0.0)
        sch_type_lim_frac.setUpperLimitValue(1.0)
        sch_type_lim_frac.setNumericType('Continuous')

        sch_type_lim_temp = osmod.ScheduleTypeLimits(osmodel)
        sch_type_lim_temp.setName('temperature')
        sch_type_lim_temp.setLowerLimitValue(-60)
        sch_type_lim_temp.setUpperLimitValue(200)
        sch_type_lim_temp.setNumericType('Continuous')
        sch_type_lim_temp.setUnitType('Temperature')

        sch_type_lim_act = osmod.ScheduleTypeLimits(osmodel)
        sch_type_lim_act.setName('activity')
        sch_type_lim_act.setLowerLimitValue(0)
        sch_type_lim_act.setNumericType('Continuous')
        sch_type_lim_act.setUnitType('ActivityLevel')
        # endregion:setup schedule type limits
        # region: always on schedule
        sch_day_on = osmod.ScheduleDay(osmodel)
        sch_day_on.setName('day_on')
        sch_day_on.setScheduleTypeLimits(sch_type_lim_frac)
        sch_day_on.addValue(time24, 1.0)

        sch_ruleset_on = osmod.ScheduleRuleset(osmodel)
        sch_ruleset_on.setName('ruleset_on')
        sch_ruleset_on.setScheduleTypeLimits(sch_type_lim_frac)
        sch_ruleset_on.setSummerDesignDaySchedule(sch_day_on)
        sch_ruleset_on.setWinterDesignDaySchedule(sch_day_on)
        sch_ruleset_on.setHolidaySchedule(sch_day_on)
        sch_ruleset_on.setCustomDay1Schedule(sch_day_on)
        sch_ruleset_on.setCustomDay2Schedule(sch_day_on)

        sch_rule_on = osmod.ScheduleRule(sch_ruleset_on, sch_day_on)
        sch_rule_on.setName('rule_on')
        sch_rule_on.setApplyAllDays(True)
        # endregion: always on schedule
        # region: setup occ schedule
        sch_day_occ = osmod.ScheduleDay(osmodel)
        sch_day_occ.setName('weekday occupancy')
        sch_day_occ.setScheduleTypeLimits(sch_type_lim_frac)
        sch_day_occ.addValue(time9, 0.0)
        sch_day_occ.addValue(time17, 1.0)

        sch_ruleset_occ = osmod.ScheduleRuleset(osmodel)
        sch_ruleset_occ.setName('occupancy schedule')
        sch_ruleset_occ.setScheduleTypeLimits(sch_type_lim_frac)

        sch_rule_occ = osmod.ScheduleRule(sch_ruleset_occ, sch_day_occ)
        sch_rule_occ.setName('occupancy weekdays')
        sch_rule_occ.setApplyWeekdays(True)
        # endregion: setup occ schedule
        # region: setup activity schedule
        sch_day_act = osmod.ScheduleDay(osmodel)
        sch_day_act.setName('weekday activity')
        sch_day_act.setScheduleTypeLimits(sch_type_lim_act)
        sch_day_act.addValue(time24, 70)

        sch_ruleset_act = osmod.ScheduleRuleset(osmodel)
        sch_ruleset_act.setName('activity schedule')
        sch_ruleset_act.setScheduleTypeLimits(sch_type_lim_act)
        sch_ruleset_act.setSummerDesignDaySchedule(sch_day_act)
        sch_ruleset_act.setWinterDesignDaySchedule(sch_day_act)
        sch_ruleset_act.setHolidaySchedule(sch_day_act)
        sch_ruleset_act.setCustomDay1Schedule(sch_day_act)
        sch_ruleset_act.setCustomDay2Schedule(sch_day_act)

        sch_rule_act = osmod.ScheduleRule(sch_ruleset_act, sch_day_act)
        sch_rule_act.setName('activity weekdays')
        sch_rule_act.setApplyAllDays(True)
        # endregion: setup activity schedule
        # region: setup thermostat cooling setpoint
        sch_day_cool_tstat = osmod.ScheduleDay(osmodel)
        sch_day_cool_tstat.setName('thermostat cooling weekday schedule')
        sch_day_cool_tstat.setScheduleTypeLimits(sch_type_lim_temp)
        sch_day_cool_tstat.addValue(time9, 60.0)
        sch_day_cool_tstat.addValue(time17, 25.0)
        sch_day_cool_tstat.addValue(time24, 60.0)

        sch_day_cool_tstat2 = osmod.ScheduleDay(osmodel)
        sch_day_cool_tstat2.setName('thermostat cooling weekends schedule')
        sch_day_cool_tstat2.setScheduleTypeLimits(sch_type_lim_temp)
        sch_day_cool_tstat2.addValue(time24, 60.0)

        sch_day_cool_tstat3 = osmod.ScheduleDay(osmodel)
        sch_day_cool_tstat3.setName('thermostat cooling design day schedule')
        sch_day_cool_tstat3.setScheduleTypeLimits(sch_type_lim_temp)
        sch_day_cool_tstat3.addValue(time9, 25.0)
        sch_day_cool_tstat3.addValue(time17, 25.0)
        sch_day_cool_tstat3.addValue(time24, 25.0)

        sch_ruleset_cool_tstat = osmod.ScheduleRuleset(osmodel)
        sch_ruleset_cool_tstat.setName('thermostat cooling ruleset')
        sch_ruleset_cool_tstat.setScheduleTypeLimits(sch_type_lim_temp)
        sch_ruleset_cool_tstat.setSummerDesignDaySchedule(sch_day_cool_tstat3)

        sch_rule_cool_tstat = osmod.ScheduleRule(sch_ruleset_cool_tstat, sch_day_cool_tstat)
        sch_rule_cool_tstat.setName('thermostat cooling weekday rule')
        sch_rule_cool_tstat.setApplyWeekdays(True)

        sch_rule_cool_tstat = osmod.ScheduleRule(sch_ruleset_cool_tstat, sch_day_cool_tstat2)
        sch_rule_cool_tstat.setName('thermostat cooling weekend rule')
        sch_rule_cool_tstat.setApplyWeekends(True)
        # endregion: setup thermostat cooling setpoint
        # region: setup thermostat heating setpoint
        sch_day_hot_tstat = osmod.ScheduleDay(osmodel)
        sch_day_hot_tstat.setName('thermostat heating weekday schedule')
        sch_day_hot_tstat.setScheduleTypeLimits(sch_type_lim_temp)
        sch_day_hot_tstat.addValue(time9, 20.0)
        sch_day_hot_tstat.addValue(time17, 20.0)
        sch_day_hot_tstat.addValue(time24, 20.0)

        sch_ruleset_hot_tstat = osmod.ScheduleRuleset(osmodel)
        sch_ruleset_hot_tstat.setName('thermostat heating ruleset')
        sch_ruleset_hot_tstat.setScheduleTypeLimits(sch_type_lim_temp)
        sch_ruleset_cool_tstat.setWinterDesignDaySchedule(sch_day_hot_tstat)

        sch_rule_hot_tstat = osmod.ScheduleRule(sch_ruleset_hot_tstat, sch_day_hot_tstat)
        sch_rule_hot_tstat.setName('thermostat heating weekday rule')
        sch_rule_hot_tstat.setApplyAllDays(True)
        # endregion: setup thermostat heating setpoint
        tstat = osmod.ThermostatSetpointDualSetpoint(osmodel)
        tstat.setCoolingSetpointTemperatureSchedule(sch_ruleset_cool_tstat)
        tstat.setHeatingSetpointTemperatureSchedule(sch_ruleset_hot_tstat)
        # endregion: setup the schedules 
    
    # region: TODO INCOMPLETE IMPLEMENTATION
    # bldg_dir = settings.PROTOBLDG_DATA_DIR
    # bldg_path = str(bldg_dir.joinpath('ASHRAE901_OfficeSmall_STD2022_Miami.osm'))
    # proto_osmodel = osmod.Model.load(bldg_path).get()
    # # find the schedules to be apply onto the osmodel
    # ppl_schs = []
    # ppl_sch_handles = []
    # lights_schs = []
    # lights_sch_handles = []
    # elec_schs = []
    # elec_sch_handles = []
    # proto_spaces = osmod.getSpaces(proto_osmodel)
    # for proto_space in proto_spaces[0:]:
    #     print(proto_space.nameString())

    #     people = proto_space.people()
    #     if len(people) != 0:
    #         ppl_sch = people[0].numberofPeopleSchedule() 
    #         if not ppl_sch.empty():
    #             ppl_sch = ppl_sch.get()
    #             ppl_sch_handle = ppl_sch.handle()
    #             if ppl_sch_handle not in ppl_sch_handles:
    #                 ppl_sch_handles.append(ppl_sch_handle)
    #                 ppl_schs.append(ppl_sch)

    #     lights = proto_space.lights()
    #     if len(lights) != 0:
    #         lights_sch = lights[0].schedule()
    #         if not lights_sch.empty():
    #             lights_sch = lights_sch.get()
    #             lights_sch_handle = lights_sch.handle()
    #             if lights_sch_handle not in lights_sch_handles:
    #                 lights_sch_handles.append(lights_sch_handle)
    #                 lights_schs.append(lights_sch)

    #     elec = proto_space.electricEquipment()
    #     if len(elec) != 0:
    #         elec_sch = elec[0].schedule()
    #         if not elec_sch.empty():
    #             elec_sch = elec_sch.get()
    #             elec_sch_handle = elec_sch.handle()
    #             if elec_sch_handle not in elec_sch_handles:
    #                 elec_schs.append(elec_sch)
    #                 elec_sch_handles.append(elec_sch_handle)

    # print(ppl_schs)
    # print(lights_schs)
    # print(elec_schs)
    # endregion: Ideal setup
    #------------------------------------------------------------------------------------------------------
    # endregion: read the openstudio model file based on the building type and climate
    #------------------------------------------------------------------------------------------------------
    #------------------------------------------------------------------------------------------------------
    # region: add the schedules into the openstudio model
    #------------------------------------------------------------------------------------------------------
    spaces = osmod.getSpaces(osmodel)
    thermal_zones =[]
    for cnt,space in enumerate(spaces):
        space_name = space.nameString()
        space.autocalculateFloorArea()
        
        farea_ppl = space.floorAreaPerPerson()
        lpwr_farea = space.lightingPowerPerFloorArea()
        epwr_farea = space.electricEquipmentPowerPerFloorArea()

        # rmv the original ppl def
        orig_ppls = space.people()
        for orig_ppl in orig_ppls:
            orig_ppl_def = orig_ppl.peopleDefinition()
            osmodel.removeObject(orig_ppl.handle())
            osmodel.removeObject(orig_ppl_def.handle())
        # rmv the orig lights
        orig_lights = space.lights()
        for orig_light in orig_lights:
            orig_light_def = orig_light.lightsDefinition()
            osmodel.removeObject(orig_light.handle())
            osmodel.removeObject(orig_light_def.handle())
        # rmv the orig elecs
        orig_elecs = space.electricEquipment()
        for orig_elec in orig_elecs:
            orig_elec_def = orig_elec.electricEquipmentDefinition()
            osmodel.removeObject(orig_elec.handle())
            osmodel.removeObject(orig_elec_def.handle())

        is_plenum = True
        # setup all the schedules
        if farea_ppl != inf and farea_ppl > 0:
            # setup occupancy schedule
            ppl = openstudio_utils.setup_ppl_schedule(osmodel, sch_ruleset_occ, sch_ruleset_act, name = f"{space_name}_ppl_{cnt}")
            space.setFloorAreaPerPerson(farea_ppl, ppl)
            is_plenum = False
        
        if lpwr_farea != inf and lpwr_farea > 0:
            # setup the lighting schedule
            light = openstudio_utils.setup_light_schedule(osmodel, sch_ruleset_occ, name = f"{space_name}_lights_{cnt}")
            space.setLightingPowerPerFloorArea(lpwr_farea, light)
            is_plenum = False

        if epwr_farea != inf and epwr_farea > 0:
            # setup electric equipment schedule
            elec_equip = openstudio_utils.setup_elec_equip_schedule(osmodel, sch_ruleset_occ, name = f"{space_name}_elec_equip_{cnt}")
            space.setElectricEquipmentPowerPerFloorArea(epwr_farea, elec_equip)
            is_plenum = False

        if is_plenum == True:
            # add infiltration rate 
            infiltration = osmod.SpaceInfiltrationDesignFlowRate(osmodel)
            infiltration.setDesignFlowRate(0.2)
            infiltration.setSchedule(sch_ruleset_on)
            infiltration.setSpace(space)
            space.setPartofTotalFloorArea(False)

        # setup the thermostat schedule
        thermalzone = space.thermalZone()
        if thermalzone.empty() == False:
            if is_plenum == False:
                thermalzone_real = thermalzone.get()
                # TODO: figure out what to do with plenum space
                thermalzone_real.setThermostatSetpointDualSetpoint(tstat)
                thermal_zones.append(thermalzone_real)
    #------------------------------------------------------------------------------------------------------
    # endregion: add the schedules into the openstudio model
    #------------------------------------------------------------------------------------------------------
    osmodel.save(osmod_path, True)
    return osmod_path

def main():
    args = parse_args()
    pipe_input = args.process
    if pipe_input == False:
        osmod_path = args.osmod
    else:
        lines = list(sys.stdin)
        osmod_path = lines[0].strip()

    osmod_path = str(Path(osmod_path).resolve())
    bldg_type = args.btype
    climate = args.climate

    osmod_res_path = add_sch2osmod(osmod_path, bldg_type, climate)
    # make sure this output can be piped into another command on the cmd
    print(osmod_res_path)
    sys.stdout.flush()
#===================================================================================================
# endregion: FUNCTIONS
#===================================================================================================
# region: Main
#===================================================================================================
if __name__=='__main__':
    main()
#===================================================================================================
# endregion: Main
#===================================================================================================