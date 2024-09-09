"""insert your copyright here.

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/
"""

import typing

import openstudio
from openstudio import model as osmod


class SiteZoneResults(openstudio.measure.ModelMeasure):
    """A ModelMeasure."""

    def name(self):
        """Returns the human readable name.

        Measure name should be the title case of the class name.
        The measure name is the first contact a user has with the measure;
        it is also shared throughout the measure workflow, visible in the OpenStudio Application,
        PAT, Server Management Consoles, and in output reports.
        As such, measure names should clearly describe the measure's function,
        while remaining general in nature
        """
        return "Add site and zone level output variables"

    def description(self):
        """Human readable description.

        The measure description is intended for a general audience and should not assume
        that the reader is familiar with the design and construction practices suggested by the measure.
        """
        return "This measure adds site and zone level output such as temperatures and loads to the output dictonary of EP+ simulation"

    def modeler_description(self):
        """Human readable description of modeling approach.

        The modeler description is intended for the energy modeler using the measure.
        It should explain the measure's intent, and include any requirements about
        how the baseline model must be set up, major assumptions made by the measure,
        and relevant citations or references to applicable modeling resources
        """
        return "This measure uses the adds outputs using the openstudio.model.OutputVariable method"

    def arguments(self, model: typing.Optional[openstudio.model.Model] = None):
        """Prepares user arguments for the measure.

        Measure arguments define which -- if any -- input parameters the user may set before running the measure.
        """
        args = openstudio.measure.OSArgumentVector()
        return args

    def run(
        self,
        model: openstudio.model.Model,
        runner: openstudio.measure.OSRunner,
        user_arguments: openstudio.measure.OSArgumentMap,
    ):
        """Defines what happens when the measure is run."""
        super().run(model, runner, user_arguments)  # Do **NOT** remove this line

        if not (runner.validateUserArguments(self.arguments(model), user_arguments)):
            return False

        # echo the new space's name back to the user
        runner.registerInfo(f"There are no user arguments in this measure")
        vars = []
        # site level variables
        var = osmod.OutputVariable('Site Outdoor Air Drybulb Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Site Outdoor Air Dewpoint Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Site Outdoor Air Relative Humidity', model)
        vars.append(var)
        var = osmod.OutputVariable('Wind Speed', model)
        vars.append(var)
        var = osmod.OutputVariable('Site Wind Direction', model)
        vars.append(var)
        var = osmod.OutputVariable('Site Sky Temperature', model)
        vars.append(var)
        # zone level variables
        var = osmod.OutputVariable('Zone Air Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Mean Air Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Mean Radiant Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Operative Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Thermostat Air Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Thermostat Cooling Setpoint Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Thermostat Heating Setpoint Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Mean Air Dewpoint Temperature', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Air Relative Humidity', model)
        vars.append(var)
        var = osmod.OutputVariable('Zone Air Humidity Ratio', model)
        vars.append(var)
        
        for var in vars:
            var.setReportingFrequency('Hourly')
        
        # report final condition of model
        runner.registerFinalCondition(f"Successfully output variables")

        return True

# register the measure to be used by the application
SiteZoneResults().registerWithApplication()
