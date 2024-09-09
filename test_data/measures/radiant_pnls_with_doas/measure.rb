# *******************************************************************************
# OpenStudio(R), Copyright (c) Alliance for Sustainable Energy, LLC.
# See also https://openstudio.net/license
# Copyright (c) 2024, Chen Kian Wee (chenkianwee@gmail.com)
# *******************************************************************************

require 'openstudio-standards'

def model_add_low_temp_radiant(std, model,
                              thermal_zones,
                              hot_water_loop,
                              chilled_water_loop,
                              two_pipe_system: false,
                              two_pipe_control_strategy: 'outdoor_air_lockout',
                              two_pipe_lockout_temperature: 65.0,
                              plant_supply_water_temperature_control: false,
                              plant_supply_water_temperature_control_strategy: 'other',
                              hwsp_at_oat_low: 120.0,
                              hw_oat_low: 55.0,
                              hwsp_at_oat_high: 80.0,
                              hw_oat_high: 70.0,
                              chwsp_at_oat_low: 70.0,
                              chw_oat_low: 65.0,
                              chwsp_at_oat_high: 55.0,
                              chw_oat_high: 75.0,
                              radiant_temperature_control_type: 'MeanAirTemperature',
                              radiant_setpoint_control_type: 'ZeroFlowPower',
                              control_strategy: 'proportional_control',
                              use_zone_occupancy_for_control: true,
                              occupied_percentage_threshold: 0.10,
                              model_occ_hr_start: 6.0,
                              model_occ_hr_end: 18.0,
                              proportional_gain: 0.3,
                              switch_over_time: 24.0,
                              slab_sp_at_oat_low: 73,
                              slab_oat_low: 65,
                              slab_sp_at_oat_high: 68,
                              slab_oat_high: 80,
                              radiant_availability_type: 'other',
                              radiant_lockout: false,
                              radiant_lockout_start_time: 12.0,
                              radiant_lockout_end_time: 20.0)

    # create internal source constructions for surfaces
    OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', "Replacing ceiling constructions with new radiant slab constructions.")
    version = OpenstudioStandards::VERSION
    if version == '0.5.0'
      climate_zone = std.model_standards_climate_zone(model)
    elsif (version == '0.6.0' or version == '0.6.1') 
      climate_zone = OpenstudioStandards::Weather.model_get_climate_zone(model)
    end

    if climate_zone.empty?
      OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', 'Unable to determine climate zone for radiant slab insulation determination.  Defaulting to climate zone 5, R-20 insulation, 110F heating design supply water temperature.')
      cz_mult = 4
      radiant_htg_dsgn_sup_wtr_temp_f = 110
    else
      climate_zone_set = std.model_find_climate_zone_set(model, climate_zone)
      case climate_zone_set.gsub('ClimateZone ', '').gsub('CEC T24 ', '')
      when '1'
        cz_mult = 2
        radiant_htg_dsgn_sup_wtr_temp_f = 90
      when '2', '2A', '2B', 'CEC15'
        cz_mult = 2
        radiant_htg_dsgn_sup_wtr_temp_f = 100
      when '3', '3A', '3B', '3C', 'CEC3', 'CEC4', 'CEC5', 'CEC6', 'CEC7', 'CEC8', 'CEC9', 'CEC10', 'CEC11', 'CEC12', 'CEC13', 'CEC14'
        cz_mult = 3
        radiant_htg_dsgn_sup_wtr_temp_f = 100
      when '4', '4A', '4B', '4C', 'CEC1', 'CEC2'
        cz_mult = 4
        radiant_htg_dsgn_sup_wtr_temp_f = 100
      when '5', '5A', '5B', '5C', 'CEC16'
        cz_mult = 4
        radiant_htg_dsgn_sup_wtr_temp_f = 110
      when '6', '6A', '6B'
        cz_mult = 4
        radiant_htg_dsgn_sup_wtr_temp_f = 120
      when '7', '8'
        cz_mult = 5
        radiant_htg_dsgn_sup_wtr_temp_f = 120
      else # default to 4
        cz_mult = 4
        radiant_htg_dsgn_sup_wtr_temp_f = 100
      end
      OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', "Based on model climate zone #{climate_zone} using R-#{(cz_mult * 5).to_i} slab insulation, R-#{((cz_mult + 1) * 5).to_i} exterior floor insulation, R-#{((cz_mult + 1) * 2 * 5).to_i} exterior roof insulation, and #{radiant_htg_dsgn_sup_wtr_temp_f}F heating design supply water temperature.")
    end

    # create materials
    mat_concrete_5in_0_127mm = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'MediumRough', 0.127, 2.31, 2322, 832)
    mat_concrete_5in_0_127mm.setName('Radiant Slab Concrete - 1.5 in')

    mat_gypsum_0_625in_0_0159mm = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', 0.0159, 0.16, 640, 1150)
    mat_gypsum_0_625in_0_0159mm.setName('mat_gypsum_0_625in_0_0159mm')

    mat_gypsum_0_472in_0_012mm = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', 0.012, 0.16, 640, 1150)
    mat_gypsum_0_472in_0_012mm.setName('mat_gypsum_0_472in_0_012mm')

    mat_alum_0_001 = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Smooth', 0.001, 13, 8230, 470)
    mat_alum_0_001.setName('mat_alum_0_001')

    mat_insulation_0_05 = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', 0.05, 0.02, 56, 1210)
    mat_insulation_0_05.setName('mat_insulation_0_05')

    mat_rval = OpenStudio::Model::MasslessOpaqueMaterial.new(model, 'Rough', 0.18)
    mat_rval.setName('mat_rval')
    mat_rval.setThermalAbsorptance(0.9)
    mat_rval.setSolarAbsorptance(0.7)
    mat_rval.setVisibleAbsorptance(0.7)
    
    mat_refl_roof_membrane = model.getStandardOpaqueMaterialByName('Roof Membrane - Highly Reflective')
    if mat_refl_roof_membrane.is_initialized
      mat_refl_roof_membrane = model.getStandardOpaqueMaterialByName('Roof Membrane - Highly Reflective').get
    else
      mat_refl_roof_membrane = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'VeryRough', 0.0095, 0.16, 1121.29, 1460)
      mat_refl_roof_membrane.setThermalAbsorptance(0.75)
      mat_refl_roof_membrane.setSolarAbsorptance(0.45)
      mat_refl_roof_membrane.setVisibleAbsorptance(0.7)
      mat_refl_roof_membrane.setName('Roof Membrane - Highly Reflective')
    end

    # set exterior slab insulation thickness based on climate zone
    slab_insulation_thickness_m = 0.0254 * cz_mult
    mat_slab_insulation = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', slab_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_slab_insulation.setName("Radiant Ground Slab Insulation - #{cz_mult} in.")

    ext_insulation_thickness_m = 0.0254 * (cz_mult + 1)
    mat_ext_insulation = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', ext_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_ext_insulation.setName("Radiant Exterior Slab Insulation - #{cz_mult + 1} in.")

    roof_insulation_thickness_m = 0.0254 * (cz_mult + 1) * 2
    mat_roof_insulation = OpenStudio::Model::StandardOpaqueMaterial.new(model, 'Rough', roof_insulation_thickness_m, 0.02, 56.06, 1210)
    mat_roof_insulation.setName("Radiant Exterior Ceiling Insulation - #{(cz_mult + 1) * 2} in.")

    # create radiant internal source constructions
    OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', 'New constructions exclude the metal deck, as high thermal diffusivity materials cause errors in EnergyPlus internal source construction calculations.')

    layers = []
    layers << mat_concrete_5in_0_127mm
    layers << mat_gypsum_0_625in_0_0159mm
    # layers << mat_rval
    # layers << mat_gypsum_0_472in_0_012mm
    layers << mat_insulation_0_05
    layers << mat_alum_0_001

    radiant_pnl_construction = OpenStudio::Model::ConstructionWithInternalSource.new(layers)
    radiant_pnl_construction.setName('radiant_pnl_construction')
    radiant_pnl_construction.setSourcePresentAfterLayerNumber(2)
    radiant_pnl_construction.setTemperatureCalculationRequestedAfterLayerNumber(2)
    # radiant_pnl_construction.setTubeSpacing(0.2286) # 9 inches
    radiant_pnl_construction.setTubeSpacing(0.116)
    radiant_pnl_construction.setDimensionsForTheCTFCalculation(2)

    layers = []
    layers << mat_refl_roof_membrane
    layers << mat_roof_insulation
    layers << mat_concrete_5in_0_127mm
    layers << mat_gypsum_0_625in_0_0159mm
    # layers << mat_rval
    # layers << mat_gypsum_0_472in_0_012mm
    layers << mat_insulation_0_05
    layers << mat_alum_0_001

    radiant_pnl_ext_construction = OpenStudio::Model::ConstructionWithInternalSource.new(layers)
    radiant_pnl_ext_construction.setName('radiant_pnl_ext_construction')
    radiant_pnl_ext_construction.setSourcePresentAfterLayerNumber(5)
    radiant_pnl_ext_construction.setTemperatureCalculationRequestedAfterLayerNumber(5)
    # radiant_ceiling_slab_construction.setTubeSpacing(0.2286) # 9 inches
    radiant_pnl_ext_construction.setTubeSpacing(0.116)
    radiant_pnl_ext_construction.setDimensionsForTheCTFCalculation(2)

    # adjust hot and chilled water loop temperatures and set new setpoint schedules
    radiant_htg_dsgn_sup_wtr_temp_delt_r = 10.0
    radiant_htg_dsgn_sup_wtr_temp_c = OpenStudio.convert(radiant_htg_dsgn_sup_wtr_temp_f, 'F', 'C').get
    radiant_htg_dsgn_sup_wtr_temp_delt_k = OpenStudio.convert(radiant_htg_dsgn_sup_wtr_temp_delt_r, 'R', 'K').get
    hot_water_loop.sizingPlant.setDesignLoopExitTemperature(radiant_htg_dsgn_sup_wtr_temp_c)
    hot_water_loop.sizingPlant.setLoopDesignTemperatureDifference(radiant_htg_dsgn_sup_wtr_temp_delt_k)

    if version == '0.5.0'
      hw_temp_sch = std.model_add_constant_schedule_ruleset(model,radiant_htg_dsgn_sup_wtr_temp_c, 
                                                            name = "#{hot_water_loop.name} Temp - #{radiant_htg_dsgn_sup_wtr_temp_f.round(0)}F")
    elsif (version == '0.6.0' or version == '0.6.1') 
      hw_temp_sch = OpenstudioStandards::Schedules.create_constant_schedule_ruleset(model,
                                                                                    radiant_htg_dsgn_sup_wtr_temp_c,
                                                                                    name: "#{hot_water_loop.name} Temp - #{radiant_htg_dsgn_sup_wtr_temp_f.round(0)}F",
                                                                                    schedule_type_limit: 'Temperature')
    end

    hot_water_loop.supplyOutletNode.setpointManagers.each do |spm|
      if spm.to_SetpointManagerScheduled.is_initialized
        spm = spm.to_SetpointManagerScheduled.get
        spm.setSchedule(hw_temp_sch)
        OpenStudio.logFree(OpenStudio::Info, 'openstudio.Model.Model', "Changing hot water loop setpoint for '#{hot_water_loop.name}' to '#{hw_temp_sch.name}' to account for the radiant system.")
        end
    end

    radiant_clg_dsgn_sup_wtr_temp_f = 55
    radiant_clg_dsgn_sup_wtr_temp_delt_r = 5.0
    radiant_clg_dsgn_sup_wtr_temp_c = OpenStudio.convert(radiant_clg_dsgn_sup_wtr_temp_f, 'F', 'C').get
    radiant_clg_dsgn_sup_wtr_temp_delt_k = OpenStudio.convert(radiant_clg_dsgn_sup_wtr_temp_delt_r, 'R', 'K').get
    chilled_water_loop.sizingPlant.setDesignLoopExitTemperature(radiant_clg_dsgn_sup_wtr_temp_c)
    chilled_water_loop.sizingPlant.setLoopDesignTemperatureDifference(radiant_clg_dsgn_sup_wtr_temp_delt_k)

    if version == '0.5.0'
      chw_temp_sch = std.model_add_constant_schedule_ruleset(model,radiant_clg_dsgn_sup_wtr_temp_c,
                                                            name = "#{chilled_water_loop.name} Temp - #{radiant_clg_dsgn_sup_wtr_temp_f.round(0)}F")
    elsif (version == '0.6.0' or version == '0.6.1') 
      chw_temp_sch = OpenstudioStandards::Schedules.create_constant_schedule_ruleset(model,
                                                        radiant_clg_dsgn_sup_wtr_temp_c,
                                                        name: "#{chilled_water_loop.name} Temp - #{radiant_clg_dsgn_sup_wtr_temp_f.round(0)}F",
                                                        schedule_type_limit: 'Temperature')
    end

    chilled_water_loop.supplyOutletNode.setpointManagers.each do |spm|
      if spm.to_SetpointManagerScheduled.is_initialized
        spm = spm.to_SetpointManagerScheduled.get
        spm.setSchedule(chw_temp_sch)
        OpenStudio.logFree(OpenStudio::Info, 'openstudio.Model.Model', "Changing chilled water loop setpoint for '#{chilled_water_loop.name}' to '#{chw_temp_sch.name}' to account for the radiant system.")
      end
    end

    # create preset availability schedule for radiant loop
    radiant_avail_sch = OpenStudio::Model::ScheduleRuleset.new(model)
    radiant_avail_sch.setName('Radiant System Availability Schedule')

    unless radiant_lockout
      case radiant_availability_type.downcase
        when 'all_day'
          start_hour = 24
          start_minute = 0
          end_hour = 24
          end_minute = 0
        when 'afternoon_shutoff'
          start_hour = 15
          start_minute = 0
          end_hour = 22
          end_minute = 0
        when 'precool'
          start_hour = 10
          start_minute = 0
          end_hour = 22
          end_minute = 0
        when 'occupancy'
          start_hour = model_occ_hr_end.to_i
          start_minute = ((model_occ_hr_end % 1) * 60).to_i
          end_hour = model_occ_hr_start.to_i
          end_minute = ((model_occ_hr_start % 1) * 60).to_i
        else
          OpenStudio.logFree(OpenStudio::Warn, 'openstudio.Model.Model', "Unsupported radiant availability preset '#{radiant_availability_type}'. Defaulting to all day operation.")
          start_hour = 24
          start_minute = 0
          end_hour = 24
          end_minute = 0
      end
    end

    # create custom availability schedule for radiant loop
    if radiant_lockout
      start_hour = radiant_lockout_start_time.to_i
      start_minute = ((radiant_lockout_start_time % 1) * 60).to_i
      end_hour = radiant_lockout_end_time.to_i
      end_minute = ((radiant_lockout_end_time % 1) * 60).to_i
    end

    # create availability schedules
    if end_hour > start_hour
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, start_hour, start_minute, 0), 1.0)
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, end_hour, end_minute, 0), 0.0)
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, 24, 0, 0), 1.0) if end_hour < 24
    elsif start_hour > end_hour
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, end_hour, end_minute, 0), 0.0)
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, start_hour, start_minute, 0), 1.0)
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, 24, 0, 0), 0.0) if start_hour < 24
    else
      radiant_avail_sch.defaultDaySchedule.addValue(OpenStudio::Time.new(0, 24, 0, 0), 1.0)
    end

    # convert to a two-pipe system if required
    # if two_pipe_system
    #   std.model_two_pipe_loop(model, hot_water_loop, chilled_water_loop,
    #                           control_strategy: two_pipe_control_strategy,
    #                           lockout_temperature: two_pipe_lockout_temperature,
    #                           thermal_zones: thermal_zones)
    # end

    # add supply water temperature control if enabled
    # if plant_supply_water_temperature_control
    #   # add supply water temperature for heating plant loop
    #   std.model_add_plant_supply_water_temperature_control(model, hot_water_loop,
    #                           control_strategy: plant_supply_water_temperature_control_strategy,
    #                           sp_at_oat_low: hwsp_at_oat_low,
    #                           oat_low: hw_oat_low,
    #                           sp_at_oat_high: hwsp_at_oat_high,
    #                           oat_high: hw_oat_high,
    #                           thermal_zones: thermal_zones)

    #   # add supply water temperature for cooling plant loop
    #   std.model_add_plant_supply_water_temperature_control(model, chilled_water_loop,
    #                           control_strategy: plant_supply_water_temperature_control_strategy,
    #                           sp_at_oat_low: chwsp_at_oat_low,
    #                           oat_low: chw_oat_low,
    #                           sp_at_oat_high: chwsp_at_oat_high,
    #                           oat_high: chw_oat_high,
    #                           thermal_zones: thermal_zones)
    # end

    # default temperature controls for radiant system
    zn_radiant_htg_dsgn_temp_f = 68.0
    zn_radiant_htg_dsgn_temp_c = OpenStudio.convert(zn_radiant_htg_dsgn_temp_f, 'F', 'C').get
    zn_radiant_clg_dsgn_temp_f = 74.0
    zn_radiant_clg_dsgn_temp_c = OpenStudio.convert(zn_radiant_clg_dsgn_temp_f, 'F', 'C').get

    if version == '0.5.0'
      htg_control_temp_sch = std.model_add_constant_schedule_ruleset(model, zn_radiant_htg_dsgn_temp_c,
                                                                    name = "Zone Radiant Loop Heating Threshold Temperature Schedule - #{zn_radiant_htg_dsgn_temp_f.round(0)}F")
      clg_control_temp_sch = std.model_add_constant_schedule_ruleset(model, zn_radiant_clg_dsgn_temp_c,
                                                                    name = "Zone Radiant Loop Cooling Threshold Temperature Schedule - #{zn_radiant_clg_dsgn_temp_f.round(0)}F")
    elsif (version == '0.6.0' or version == '0.6.1') 
      htg_control_temp_sch = OpenstudioStandards::Schedules.create_constant_schedule_ruleset(model,
                                                                                            zn_radiant_htg_dsgn_temp_c,
                                                                                            name: "Zone Radiant Loop Heating Threshold Temperature Schedule - #{zn_radiant_htg_dsgn_temp_f.round(0)}F",
                                                                                            schedule_type_limit: 'Temperature')
      clg_control_temp_sch = OpenstudioStandards::Schedules.create_constant_schedule_ruleset(model,
                                                                                            zn_radiant_clg_dsgn_temp_c,
                                                                                            name: "Zone Radiant Loop Cooling Threshold Temperature Schedule - #{zn_radiant_clg_dsgn_temp_f.round(0)}F",
                                                                                            schedule_type_limit: 'Temperature')
    end

    throttling_range_f = 4.0 # 2 degF on either side of control temperature
    throttling_range_c = OpenStudio.convert(throttling_range_f, 'F', 'C').get

    # make a low temperature radiant loop for each zone
    radiant_loops = []
    thermal_zones.each do |zone|
      OpenStudio.logFree(OpenStudio::Info, 'openstudio.Model.Model', "Adding radiant loop for #{zone.name}.")
      if zone.name.to_s.include? ':'
        OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model', "Thermal zone '#{zone.name}' has a restricted character ':' in the name and will not work with some EMS and output reporting objects. Please rename the zone.")
      end

      # create radiant coils
      if hot_water_loop
        radiant_loop_htg_coil = OpenStudio::Model::CoilHeatingLowTempRadiantVarFlow.new(model, htg_control_temp_sch)
        radiant_loop_htg_coil.setName("#{zone.name} Radiant Loop Heating Coil")
        radiant_loop_htg_coil.setHeatingControlThrottlingRange(throttling_range_c)
        hot_water_loop.addDemandBranchForComponent(radiant_loop_htg_coil)
      else
        OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model', 'Radiant loops require a hot water loop, but none was provided.')
      end

      if chilled_water_loop
        radiant_loop_clg_coil = OpenStudio::Model::CoilCoolingLowTempRadiantVarFlow.new(model, clg_control_temp_sch)
        radiant_loop_clg_coil.setName("#{zone.name} Radiant Loop Cooling Coil")
        radiant_loop_clg_coil.setCoolingControlThrottlingRange(throttling_range_c)
        radiant_loop_clg_coil.setCondensationControlType('Off')
        chilled_water_loop.addDemandBranchForComponent(radiant_loop_clg_coil)
      else
        OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model', 'Radiant loops require a chilled water loop, but none was provided.')
      end

      radiant_loop = OpenStudio::Model::ZoneHVACLowTempRadiantVarFlow.new(model,
                                                                          radiant_avail_sch,
                                                                          radiant_loop_htg_coil,
                                                                          radiant_loop_clg_coil)

      # assign internal source construction to ceilings in zone
      zone.spaces.each do |space|
        space.surfaces.each do |surface|
          if surface.surfaceType == 'RoofCeiling'
            surface.setConstruction(radiant_pnl_ext_construction)
            # if surface.outsideBoundaryCondition == 'Outdoors'
            #   surface.setConstruction(radiant_pnl_ext_construction)
            # else # interior ceiling
            #   surface.setConstruction(radiant_pnl_construction)
            # end
              # # also assign construction to adjacent surface
              # if surface.adjacentSurface.is_initialized
              #   adjacent_surface = surface.adjacentSurface.get
              #   adjacent_surface.setConstruction(rev_radiant_interior_ceiling_slab_construction)
              # end
          end
        end
      end
    

      # radiant loop surfaces
      radiant_loop.setName("#{zone.name} Radiant Loop")
      radiant_loop.setRadiantSurfaceType('Ceilings')

      # radiant loop layout details
      radiant_loop.setHydronicTubingInsideDiameter(0.015875) # 5/8 in. ID, 3/4 in. OD
      # @todo include a method to determine tubing length in the zone
      # loop_length = 7*zone.floorArea
      # radiant_loop.setHydronicTubingLength()
      radiant_loop.setNumberofCircuits('CalculateFromCircuitLength')
      radiant_loop.setCircuitLength(106.7)

      # radiant loop temperature controls
      radiant_loop.setTemperatureControlType(radiant_temperature_control_type)

      # radiant loop setpoint temperature response
      radiant_loop.setSetpointControlType(radiant_setpoint_control_type)
      radiant_loop.addToThermalZone(zone)
      radiant_loops << radiant_loop

      # rename nodes before adding EMS code
      std.rename_plant_loop_nodes(model)

      # set radiant loop controls
      # case control_strategy.downcase
      # when 'proportional_control'
      #   # slab setpoint varies based on previous day zone conditions
      #   std.model_add_radiant_proportional_controls(model, zone, radiant_loop,
      #                   radiant_temperature_control_type: radiant_temperature_control_type,
      #                   use_zone_occupancy_for_control: use_zone_occupancy_for_control,
      #                   occupied_percentage_threshold: occupied_percentage_threshold,
      #                   model_occ_hr_start: model_occ_hr_start,
      #                   model_occ_hr_end: model_occ_hr_end,
      #                   proportional_gain: proportional_gain,
      #                   switch_over_time: switch_over_time)
      # when 'oa_based_control'
      #   # slab setpoint varies based on outdoor weather
      #   std.model_add_radiant_basic_controls(model, zone, radiant_loop,
      #             radiant_temperature_control_type: radiant_temperature_control_type,
      #             slab_setpoint_oa_control: true,
      #             switch_over_time: switch_over_time,
      #             slab_sp_at_oat_low: slab_sp_at_oat_low,
      #             slab_oat_low: slab_oat_low,
      #             slab_sp_at_oat_high: slab_sp_at_oat_high,
      #             slab_oat_high: slab_oat_high)
      # when 'constant_control'
      #   # constant slab setpoint control
      #   model_add_radiant_basic_controls(std, model, zone, radiant_loop,
      #                                   radiant_temperature_control_type: radiant_temperature_control_type,
      #                                   slab_setpoint_oa_control: false,
      #                                   switch_over_time: switch_over_time,
      #                                   slab_sp_at_oat_low: slab_sp_at_oat_low,
      #                                   slab_oat_low: slab_oat_low,
      #                                   slab_sp_at_oat_high: slab_sp_at_oat_high,
      #                                   slab_oat_high: slab_oat_high)
      # end
    end
    return radiant_loops
end

def model_add_radiant_basic_controls(std, model, zone, radiant_loop,
                                      slab_clg_setpoint: 25,
                                      slab_htg_setpoint: 20,
                                      radiant_temperature_control_type: 'MeanAirTemperature',
                                      slab_setpoint_oa_control: false,
                                      switch_over_time: 24.0,
                                      slab_sp_at_oat_low: 73,
                                      slab_oat_low: 65,
                                      slab_sp_at_oat_high: 68,
                                      slab_oat_high: 80)

  zone_name = zone.name.to_s.gsub(/[ +-.]/, '_')

  if model.version < OpenStudio::VersionString.new('3.1.1')
    coil_cooling_radiant = radiant_loop.coolingCoil.to_CoilCoolingLowTempRadiantVarFlow.get
    coil_heating_radiant = radiant_loop.heatingCoil.to_CoilHeatingLowTempRadiantVarFlow.get
  else
    coil_cooling_radiant = radiant_loop.coolingCoil.get.to_CoilCoolingLowTempRadiantVarFlow.get
    coil_heating_radiant = radiant_loop.heatingCoil.get.to_CoilHeatingLowTempRadiantVarFlow.get
  end

  # Define radiant system parameters
  # set radiant system temperature and setpoint control type
  # unless ['surfacefacetemperature', 'surfaceinteriortemperature'].include? radiant_temperature_control_type.downcase
  #   OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model',
  #   "Control sequences not compatible with '#{radiant_temperature_control_type}' radiant system control. Defaulting to 'SurfaceFaceTemperature'.")
  #   radiant_temperature_control_type = 'SurfaceFaceTemperature'
  # end

  # radiant_loop.setTemperatureControlType(radiant_temperature_control_type)

  # get existing switchover time schedule or create one if needed
  sch_radiant_switchover = model.getScheduleRulesetByName('Radiant System Switchover')
  if sch_radiant_switchover.is_initialized
    sch_radiant_switchover = sch_radiant_switchover.get
  else
    sch_radiant_switchover = std.model_add_constant_schedule_ruleset(model,
                                switch_over_time,
                                name = 'Radiant System Switchover',
                                sch_type_limit: 'Dimensionless')
  end

  # set radiant system switchover schedule
  radiant_loop.setChangeoverDelayTimePeriodSchedule(sch_radiant_switchover.to_Schedule.get)

  if slab_setpoint_oa_control
    # get weather file from model
    weather_file = model.getWeatherFile
    if weather_file.initialized
      # get annual outdoor dry bulb temperature
      annual_oat = weather_file.file.get.data.collect { |dat| dat.dryBulbTemperature.get }

      # calculate a nhrs rolling average from annual outdoor dry bulb temperature
      nhrs = 24
      last_nhrs_oat_in_year = annual_oat.last(nhrs - 1)
      combined_oat = last_nhrs_oat_in_year + annual_oat
      oat_rolling_average = combined_oat.each_cons(nhrs).map { |e| e.reduce(&:+).fdiv(nhrs).round(2) }

      # use rolling average to calculate slab setpoint temperature

      # convert temperature from IP to SI units
      slab_sp_at_oat_low_si = OpenStudio.convert(slab_sp_at_oat_low, 'F', 'C').get
      slab_oat_low_si = OpenStudio.convert(slab_oat_low, 'F', 'C').get
      slab_sp_at_oat_high_si = OpenStudio.convert(slab_sp_at_oat_high, 'F', 'C').get
      slab_oat_high_si = OpenStudio.convert(slab_oat_high, 'F', 'C').get

      # calculate relationship between slab setpoint and slope
      slope_num = slab_sp_at_oat_high_si - slab_sp_at_oat_low_si
      slope_den = slab_oat_high_si - slab_oat_low_si
      sp_and_oat_slope = slope_num.fdiv(slope_den).round(4)

      slab_setpoint = oat_rolling_average.map { |e| (slab_sp_at_oat_low_si + ((e - slab_oat_low_si) * sp_and_oat_slope)).round(1) }

      # input upper limits on slab setpoint
      slab_sp_upper_limit = [slab_sp_at_oat_high_si, slab_sp_at_oat_low_si].max
      slab_sp_lower_limit = [slab_sp_at_oat_high_si, slab_sp_at_oat_low_si].min
      slab_setpoint.map! { |e| e > slab_sp_upper_limit ? slab_sp_upper_limit.round(1) : e }

      # input lower limits on slab setpoint
      slab_setpoint.map! { |e| e < slab_sp_lower_limit ? slab_sp_lower_limit.round(1) : e }

      # create ruleset for slab setpoint
      sch_type_limits_obj = std.model_add_schedule_type_limits(model, standard_sch_type_limit: 'Temperature')
      sch_radiant_slab_setp = make_ruleset_sched_from_8760(model, slab_setpoint,
                              'Sch_Radiant_SlabSetP_Based_On_Rolling_Mean_OAT',
                              sch_type_limits_obj)

      coil_heating_radiant.setHeatingControlTemperatureSchedule(sch_radiant_slab_setp)
      coil_cooling_radiant.setCoolingControlTemperatureSchedule(sch_radiant_slab_setp)
    else
      OpenStudio.logFree(OpenStudio::Error, 'openstudio.Model.Model',
      'Model does not have a weather file associated with it. Define to implement slab setpoint based on outdoor weather.')
    end
  else
    # TODO: use schedule from occupancy
    # radiant system cooling control setpoint
    sch_radiant_clgsetp = std.model_add_constant_schedule_ruleset(model,
                              slab_clg_setpoint,
                              name = "#{zone_name}_Sch_Radiant_ClgSetP")

    coil_cooling_radiant.setCoolingControlTemperatureSchedule(sch_radiant_clgsetp)
    

    # radiant system heating control setpoint
    sch_radiant_htgsetp = std.model_add_constant_schedule_ruleset(model,
                              slab_htg_setpoint,
                              name = "#{zone_name}_Sch_Radiant_HtgSetP")
    coil_heating_radiant.setHeatingControlTemperatureSchedule(sch_radiant_htgsetp)
  end
end

# start the measure
class RadiantPnlsWithDoas < OpenStudio::Measure::ModelMeasure
  # human readable name
  def name
    # Measure name should be the title case of the class name.
    return 'Radiant Panels with DOAS'
  end

  # human readable description
  def description
    return 'This measure adds radiant panels with dedicated outdoor air system to conditioned zones in the model. Radiant systems are comfortable with wider zone air temperature range. 
      Use the CBE Thermal Comfort Tool or other method to set thermostat setpoint temperatures. This measure optionally removes existing HVAC systems (recommended).
      This measure is dependent on an ASHRAE climate zone to set insulation and design supply temperature levels, so make sure this is set in the site parameters of the model.
      Plant equipment options are an Air Source Heat Pump or a Boiler for hot water, and an Air Cooled Chiller or Water Cooled Chiller for chilled water.
      The Air Source Heat Pump object uses a user-defined plant component in EnergyPlus and may not be compatible with several reporting measures, including the *Enable Detailed Output for Each Node in a Loop* measure.
      If Water Cooled Chiller is selected, the measure will add a condenser loop with a variable speed cooling tower, and optionally enable water-side economizing when wet bulb conditions allow.
      The measure includes several control parameters for radiant system operation. Use the defaults unless you have strong reasons to deviate from them.
      This measure runs a sizing run to set equipment efficiency values, so it may take up to a few minutes to run.
      This measure adds many EnergyManagementSystem objects to the model. **DO NOT** change design days after running this measure.  Adding additional HVAC measures after applying this measure may break the model.
      Radiant systems are particularly limited in cooling capacity and the model may have many unmet hours as a result.
      To reduce unmet hours, use an expanded comfort range as mentioned above, reduce internal loads, reduce solar and envelope gains during peak times, or disable the lockout.'
  end

  # human readable description of modeling approach
  def modeler_description
    return 'This measure adds radiant panels with dedicated outdoor air system to conditioned zones in the model. Radiant systems are comfortable with wider zone air temperature range. 
      Use the CBE Thermal Comfort Tool or other method to set thermostat setpoint temperatures. This measure optionally removes existing HVAC systems (recommended).
      This measure is dependent on an ASHRAE climate zone to set insulation and design supply temperature levels, so make sure this is set in the site parameters of the model.
      Plant equipment options are an Air Source Heat Pump or a Boiler for hot water, and an Air Cooled Chiller or Water Cooled Chiller for chilled water.
      The Air Source Heat Pump object uses a user-defined plant component in EnergyPlus and may not be compatible with several reporting measures, including the *Enable Detailed Output for Each Node in a Loop* measure.
      If Water Cooled Chiller is selected, the measure will add a condenser loop with a variable speed cooling tower, and optionally enable water-side economizing when wet bulb conditions allow.
      The measure includes several control parameters for radiant system operation. Use the defaults unless you have strong reasons to deviate from them.
      This measure runs a sizing run to set equipment efficiency values, so it may take up to a few minutes to run.
      This measure adds many EnergyManagementSystem objects to the model. **DO NOT** change design days after running this measure.  Adding additional HVAC measures after applying this measure may break the model.
      Radiant systems are particularly limited in cooling capacity and the model may have many unmet hours as a result.
      To reduce unmet hours, use an expanded comfort range as mentioned above, reduce internal loads, reduce solar and envelope gains during peak times, or disable the lockout.'
  end

  # define the arguments that the user will input
  def arguments(model)
    args = OpenStudio::Measure::OSArgumentVector.new

    # make bool argument to remove existing HVAC system
    remove_existing_hvac = OpenStudio::Measure::OSArgument.makeBoolArgument('remove_existing_hvac', true)
    remove_existing_hvac.setDisplayName('Remove existing HVAC system (keeps service water heating and zone exhaust fans)')
    remove_existing_hvac.setDefaultValue(true)
    args << remove_existing_hvac

    # make an argument for heating plant type
    heating_plant_types = OpenStudio::StringVector.new
    heating_plant_types << 'Air Source Heat Pump'
    heating_plant_types << 'Boiler'
    heating_plant_type = OpenStudio::Measure::OSArgument.makeChoiceArgument('heating_plant_type', heating_plant_types, true)
    heating_plant_type.setDisplayName('Heating Plant Type')
    heating_plant_type.setDefaultValue('Air Source Heat Pump')
    args << heating_plant_type

    # make an argument for cooling plant type
    cooling_plant_types = OpenStudio::StringVector.new
    cooling_plant_types << 'Air Cooled Chiller'
    cooling_plant_types << 'Water Cooled Chiller'
    cooling_plant_type = OpenStudio::Measure::OSArgument.makeChoiceArgument('cooling_plant_type', cooling_plant_types, true)
    cooling_plant_type.setDisplayName('Cooling Plant Type')
    cooling_plant_type.setDefaultValue('Air Cooled Chiller')
    args << cooling_plant_type

    # make string argument for water-side economizing if water-cooled chiller
    economizer_types = OpenStudio::StringVector.new
    economizer_types << 'none'
    economizer_types << 'integrated'
    economizer_types << 'non-integrated'
    waterside_economizer = OpenStudio::Measure::OSArgument.makeChoiceArgument('waterside_economizer', economizer_types, true)
    waterside_economizer.setDisplayName('Water-side economizer (water cooled chiller only)')
    waterside_economizer.setDefaultValue('none')
    args << waterside_economizer

    # make an argument for control strategy
    control_strategys = OpenStudio::StringVector.new
    control_strategys << 'proportional_control'
    control_strategys << 'oa_based_control'
    control_strategys << 'constant_control'
    control_strategy = OpenStudio::Measure::OSArgument.makeChoiceArgument('control_strategy', control_strategys, true)
    control_strategy.setDisplayName('Control Strategy')
    control_strategy.setDefaultValue('constant_control')
    args << control_strategy

    # make an argument for proportional gain
    proportional_gain = OpenStudio::Measure::OSArgument.makeDoubleArgument('proportional_gain', true)
    proportional_gain.setDisplayName('Proportional Gain')
    proportional_gain.setDefaultValue(0.3)
    args << proportional_gain

    # make an argument for switch over time
    switch_over_time = OpenStudio::Measure::OSArgument.makeDoubleArgument('switch_over_time', true)
    switch_over_time.setDisplayName('Switch Over Time')
    switch_over_time.setDescription('Minimum time limitation for when the system can switch between heating and cooling.  Fractional hours allowed, e.g. 30 min = 0.5.')
    switch_over_time.setDefaultValue(24.0)
    args << switch_over_time

    # make and argument for including radiant lockout
    radiant_lockout = OpenStudio::Measure::OSArgument.makeBoolArgument('radiant_lockout', true)
    radiant_lockout.setDisplayName('Enable radiant lockout')
    radiant_lockout.setDescription('Lockout the radiant system to avoid operating during peak hours.')
    radiant_lockout.setDefaultValue(false)
    args << radiant_lockout

    # make an argument for lockout start time
    lockout_start_time = OpenStudio::Measure::OSArgument.makeDoubleArgument('lockout_start_time', true)
    lockout_start_time.setDisplayName('Lockout Start Time')
    lockout_start_time.setDescription('Decimal hour of when radiant lockout starts.  Fractional hours allowed, e.g. 30 min = 0.5.')
    lockout_start_time.setDefaultValue(12.0)
    args << lockout_start_time

    # make an argument for lockout end time
    lockout_end_time = OpenStudio::Measure::OSArgument.makeDoubleArgument('lockout_end_time', true)
    lockout_end_time.setDisplayName('Lockout End Time')
    lockout_end_time.setDescription('Decimal hour of when radiant lockout ends.  Fractional hours allowed, e.g. 30 min = 0.5.')
    lockout_end_time.setDefaultValue(20.0)
    args << lockout_end_time

    # make and argument for output variables
    add_output_variables = OpenStudio::Measure::OSArgument.makeBoolArgument('add_output_variables', true)
    add_output_variables.setDisplayName('Add output variables for radiant system')
    add_output_variables.setDefaultValue(true)
    args << add_output_variables

    # make an argument for standards template
    standards_templates = OpenStudio::StringVector.new
    standards_templates << '90.1-2013'
    standards_templates << 'DEER 2017'
    standards_templates << 'DEER 2020'
    standards_template = OpenStudio::Measure::OSArgument.makeChoiceArgument('standards_template', standards_templates, true)
    standards_template.setDisplayName('Standards Template')
    standards_template.setDescription('Standards template to use for HVAC equipment efficiencies and controls.')
    standards_template.setDefaultValue('90.1-2013')
    args << standards_template

    return args
  end

  # define what happens when the measure is run
  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)  # Do **NOT** remove this line

    # use the built-in error checking
    if !runner.validateUserArguments(arguments(model), user_arguments)
      return false
    end

    # assign user inputs
    remove_existing_hvac = runner.getBoolArgumentValue('remove_existing_hvac', user_arguments)
    heating_plant_type = runner.getStringArgumentValue('heating_plant_type', user_arguments)
    cooling_plant_type = runner.getStringArgumentValue('cooling_plant_type', user_arguments)
    waterside_economizer = runner.getStringArgumentValue('waterside_economizer', user_arguments)
    control_strategy = runner.getStringArgumentValue('control_strategy', user_arguments)
    proportional_gain = runner.getDoubleArgumentValue('proportional_gain', user_arguments)
    switch_over_time = runner.getDoubleArgumentValue('switch_over_time', user_arguments)
    radiant_lockout = runner.getBoolArgumentValue('radiant_lockout', user_arguments)
    lockout_start_time = runner.getDoubleArgumentValue('lockout_start_time', user_arguments)
    lockout_end_time = runner.getDoubleArgumentValue('lockout_end_time', user_arguments)
    add_output_variables = runner.getBoolArgumentValue('add_output_variables', user_arguments)
    standards_template = runner.getStringArgumentValue('standards_template', user_arguments)

    # standard to access methods in openstudio-standards
    std = Standard.build(standards_template)

    # remove existing hvac systems
    if remove_existing_hvac
      runner.registerInfo('Removing existing HVAC systems from the model')
      if std.respond_to?('remove_HVAC')
        std.remove_HVAC(model) # OpenStuido 3.2.1 and earlierop use this, future versions will use snake_case method
      else
        std.remove_hvac(model)
      end
    end

    # exclude plenum zones, zones without thermostats, and zones with no floor area
    conditioned_zones = []
    model.getThermalZones.each do |zone|
      next if std.thermal_zone_plenum?(zone)
      next if !std.thermal_zone_heated?(zone) && !std.thermal_zone_cooled?(zone)

      conditioned_zones << zone
    end
    
    # make sure the model has conditioned zones
    if conditioned_zones.empty?
      runner.registerAsNotApplicable('No conditioned zones identified in model. Make sure thermostats are assigned to zones.')
      return false
    end

    # get the climate zone
    climate_zone_obj = model.getClimateZones.getClimateZone('ASHRAE', 2006)
    if climate_zone_obj.empty
      climate_zone_obj = model.getClimateZones.getClimateZone('ASHRAE', 2013)
    end

    if climate_zone_obj.empty || climate_zone_obj.value == ''
      runner.registerError('Please assign an ASHRAE climate zone to the model before running the measure.')
      return false
    else
      climate_zone = climate_zone_obj.value
    end

    # get the radiant hot water temperature based on the climate zone
    case climate_zone
    when '1'
      radiant_htg_dsgn_sup_wtr_temp_f = 90.0
    when '2', '2A', '2B', 'CEC15'
      radiant_htg_dsgn_sup_wtr_temp_f = 100.0
    when '3', '3A', '3B', '3C', 'CEC3', 'CEC4', 'CEC5', 'CEC6', 'CEC7', 'CEC8', 'CEC9', 'CEC10', 'CEC11', 'CEC12', 'CEC13', 'CEC14'
      radiant_htg_dsgn_sup_wtr_temp_f = 100.0
    when '4', '4A', '4B', '4C', 'CEC1', 'CEC2'
      radiant_htg_dsgn_sup_wtr_temp_f = 100.0
    when '5', '5A', '5B', '5C', 'CEC16'
      radiant_htg_dsgn_sup_wtr_temp_f = 110.0
    when '6', '6A', '6B'
      radiant_htg_dsgn_sup_wtr_temp_f = 120.0
    when '7', '8'
      radiant_htg_dsgn_sup_wtr_temp_f = 120.0
    else # default to 4
      radiant_htg_dsgn_sup_wtr_temp_f = 100.0
    end
    runner.registerInitialCondition("This measure will add radiant systems to #{conditioned_zones.size} conditioned zones with a hot water loop served by a #{heating_plant_type} and chilled water loop served by a #{cooling_plant_type}.")
    runner.registerInfo("Based on model climate zone #{climate_zone}, using #{radiant_htg_dsgn_sup_wtr_temp_f}F heating supply water temperature.")

    # establish hot water and chilled water loops
    case heating_plant_type
    when 'Air Source Heat Pump'
      boiler_fuel_type = 'ASHP'
    when 'Boiler'
      boiler_fuel_type = 'NaturalGas'
    end
    hot_water_loop = std.model_add_hw_loop(model, boiler_fuel_type, dsgn_sup_wtr_temp: radiant_htg_dsgn_sup_wtr_temp_f, dsgn_sup_wtr_temp_delt: 10.0)

    case cooling_plant_type
    when 'Air Cooled Chiller'
      # make chilled water loop
      chilled_water_loop = std.model_add_chw_loop(model,
                                                  chw_pumping_type: 'const_pri_var_sec',
                                                  dsgn_sup_wtr_temp: 55.0,
                                                  dsgn_sup_wtr_temp_delt: 5.0,
                                                  chiller_cooling_type: 'AirCooled')
    when 'Water Cooled Chiller'
      # make condenser water loop
      fan_type = std.model_cw_loop_cooling_tower_fan_type(model)
      condenser_water_loop = std.model_add_cw_loop(model,
                                                  cooling_tower_type: 'Open Cooling Tower',
                                                  cooling_tower_fan_type: 'Propeller or Axial',
                                                  cooling_tower_capacity_control: fan_type,
                                                  number_of_cells_per_tower: 1,
                                                  number_cooling_towers: 1)
      # make chilled water loop
      chilled_water_loop = std.model_add_chw_loop(model,
                                                  chw_pumping_type: 'const_pri_var_sec',
                                                  dsgn_sup_wtr_temp: 55.0,
                                                  dsgn_sup_wtr_temp_delt: 5.0,
                                                  chiller_cooling_type: 'WaterCooled',
                                                  condenser_water_loop: condenser_water_loop,
                                                  waterside_economizer: waterside_economizer)
    end

    # add radiant system to conditioned zones
    radiant_loop = model_add_low_temp_radiant(std, model, conditioned_zones, hot_water_loop, chilled_water_loop,
                                              control_strategy: control_strategy,
                                              proportional_gain: proportional_gain,
                                              switch_over_time: switch_over_time,
                                              radiant_lockout: radiant_lockout,
                                              radiant_lockout_start_time: lockout_start_time,
                                              radiant_lockout_end_time: lockout_end_time)

    # add DOAS system to conditioned zones
    # std.model_add_doas(model, conditioned_zones)
    std.rename_air_loop_nodes(model)

    # set the heating and cooling sizing parameters
    std.model_apply_prm_sizing_parameters(model)

    runner.registerInfo("Adjusting HVAC equipment efficiencies and controls to follow template #{standards_template}.")

    # perform a sizing run
    if std.model_run_sizing_run(model, "#{Dir.pwd}/radiant_sizing_run") == false
      runner.registerError('Sizing run failed. See errors in sizing run directory of this measure')
      return false
    end

    # Apply the HVAC efficiency standard
    building_data = std.model_get_building_properties(model)
    std.model_apply_hvac_efficiency_standard(model, building_data['climate_zone'])

    # add output variables
    vars = []
    if add_output_variables
      # zone hvac low temperature radiant system object variables
      vars << OpenStudio::Model::OutputVariable.new('Zone Radiant HVAC Cooling Energy', model)
      vars << OpenStudio::Model::OutputVariable.new('Zone Radiant HVAC Heating Energy', model)
      vars << OpenStudio::Model::OutputVariable.new('Zone Radiant HVAC Inlet Temperature', model)
      vars << OpenStudio::Model::OutputVariable.new('Zone Radiant HVAC Outlet Temperature', model)
      vars << OpenStudio::Model::OutputVariable.new('Zone Radiant HVAC Mass Flow Rate', model)

      # air system 
      vars << OpenStudio::Model::OutputVariable.new('Air System Electricity Energy', model)
      vars << OpenStudio::Model::OutputVariable.new('Air System Total Heating Energy', model)
      vars << OpenStudio::Model::OutputVariable.new('Air System Total Cooling Energy', model)

      # plant loop variables
      vars << OpenStudio::Model::OutputVariable.new('Chiller Electricity Rate', model)
      vars << OpenStudio::Model::OutputVariable.new('Chiller Electricity Energy', model)

      var = OpenStudio::Model::OutputVariable.new('System Node Mass Flow Rate', model)
      var.setKeyValue('Chilled Water Loop Supply Outlet Node')
      vars << var
      var = OpenStudio::Model::OutputVariable.new('System Node Mass Flow Rate', model)
      var.setKeyValue('Hot Water Loop Supply Outlet Node')
      vars << var
      var = OpenStudio::Model::OutputVariable.new('System Node Temperature', model)
      var.setKeyValue('Chilled Water Loop Supply Outlet Node')
      vars << var
      var = OpenStudio::Model::OutputVariable.new('System Node Temperature', model)
      var.setKeyValue('Hot Water Loop Supply Outlet Node')
      vars << var
      var = OpenStudio::Model::OutputVariable.new('System Node Setpoint Temperature', model)
      var.setKeyValue('Chilled Water Loop Supply Outlet Node')
      vars << var
      var = OpenStudio::Model::OutputVariable.new('System Node Setpoint Temperature', model)
      var.setKeyValue('Hot Water Loop Supply Outlet Node')
      vars << var

      conditioned_space_names = []
      conditioned_zones.each do |zone|
        zone.spaces.each { |space| conditioned_space_names << space.name.get }
      end

      # radiant surface temperatures
      
      model.getSurfaces.each do |surface|
        # next if radiant_type == 'floor' && surface.surfaceType != 'Floor'
        # next if radiant_type == 'ceiling' && surface.surfaceType != 'RoofCeiling'
        
        next if surface.surfaceType != 'RoofCeiling'
        next unless surface.space.is_initialized
        surface_space_name = surface.space.get.name.to_s

        next unless conditioned_space_names.include? surface_space_name

        var = OpenStudio::Model::OutputVariable.new('Surface Inside Face Temperature', model)
        var.setKeyValue(surface.name.to_s)
        vars << var
      end

      # set to hourly
      vars.each { |var| var.setReportingFrequency('Hourly') }
    end

    # runner register final condition
    runner.registerFinalCondition("This measure created #{model.getZoneHVACLowTempRadiantVarFlows.size} radiant ceiling objects.")

    return true
  end
end

# register the measure to be used by the application
RadiantPnlsWithDoas.new.registerWithApplication
