"""insert your copyright here.

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/
"""

import openstudio


class HVACResults(openstudio.measure.EnergyPlusMeasure):
    """An EnergyPlusMeasure."""

    def name(self):
        """Returns the human readable name.

        Measure name should be the title case of the class name.
        The measure name is the first contact a user has with the measure;
        it is also shared throughout the measure workflow, visible in the OpenStudio Application,
        PAT, Server Management Consoles, and in output reports.
        As such, measure names should clearly describe the measure's function,
        while remaining general in nature
        """
        return "EnergyPlusMeasure to output variable for user to dissect the HVAC system of the building"

    def description(self):
        """Human readable description.

        The measure description is intended for a general audience and should not assume
        that the reader is familiar with the design and construction practices suggested by the measure.
        """
        return "Outputs the cooling/heating loads of the building, separated into internal, envelope, latent load and surface temperatures"

    def modeler_description(self):
        """Human readable description of modeling approach.

        The modeler description is intended for the energy modeler using the measure.
        It should explain the measure's intent, and include any requirements about
        how the baseline model must be set up, major assumptions made by the measure,
        and relevant citations or references to applicable modeling resources
        """
        return "Outputs the cooling/heating loads of the building, separated into internal, envelope, latent load and surface temperatures. This will support the modeler in understanding the impact of the hvac system on the loads."

    def arguments(self, workspace: openstudio.Workspace):
        """Prepares user arguments for the measure.

        Measure arguments define which -- if any -- input parameters the user may set before running the measure.
        """
        args = openstudio.measure.OSArgumentVector()

        srf_temps = openstudio.measure.OSArgument.makeBoolArgument('srf_temps', True)
        srf_temps.setDisplayName('Surface Temperatures')
        srf_temps.setDescription('Output the surface temperatures of each surface')

        args.append(srf_temps)

        return args

    def add_output(self, workspace: openstudio.Workspace, runner: openstudio.measure.OSRunner, parameters: list, output_variable: bool = True):
        if output_variable == True:
            idfObject = openstudio.IdfObject(openstudio.IddObjectType('Output:Variable'))
            
        else:
            idfObject = openstudio.IdfObject(openstudio.IddObjectType('Output:Meter'))

        for cnt,parm in enumerate(parameters):
            idfObject.setString(cnt, parm)
        
        wsObject_ = workspace.addObject(idfObject)
        if not wsObject_.is_initialized():
            runner.registerError("Couldn't add idfObject to workspace:\n{idfObject}")
        runner.registerInfo(f"Report added:\n'{wsObject_.get()}'")

    def run(
        self,
        workspace: openstudio.Workspace,
        runner: openstudio.measure.OSRunner,
        user_arguments: openstudio.measure.OSArgumentMap,
    ):
        """Defines what happens when the measure is run."""
        super().run(workspace, runner, user_arguments)  # Do **NOT** remove this line

        if not (runner.validateUserArguments(self.arguments(workspace), user_arguments)):
            return False

        srf_temps = runner.getBoolArgumentValue('srf_temps', user_arguments)
        runner.registerInitialCondition('start measure')
        # workspace.removeObject()
        parms = ['', 'Zone Air Temperature', 'Hourly']
        parms2 = ['EnergyTransfer:Facility', 'Timestep']
        self.add_output(workspace, runner, parms)
        self.add_output(workspace, runner, parms2, output_variable=False)

        runner.registerFinalCondition('successfully finished the measure')
        return True

# register the measure to be used by the application
HVACResults().registerWithApplication()
