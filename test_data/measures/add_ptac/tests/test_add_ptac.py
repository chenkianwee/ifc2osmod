"""insert your copyright here."""
import os
import sys
from pathlib import Path

import openstudio
from openstudio import model as osmod
import pytest

# Add the parent directory to the system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from measure import AddPTAC

class TestAddPTAC:
    """Py.test module for AddPTAC."""

    def test_number_of_arguments_and_argument_names(self):
        """Test that the arguments are what we expect."""
        # create an instance of the measure
        measure = AddPTAC()

        # make an empty model
        model = openstudio.model.Model()

        # get arguments and test that they are what we are expecting
        arguments = measure.arguments(model)
        assert arguments.size() == 2
        assert arguments[0].name() == 'heating_type'
        assert arguments[1].name() == 'fan_type'

    def test_good_argument_values(self):
        """Test running the measure with appropriate arguments.

        Asserts that the measure runs fine and with expected results.
        """
        # create an instance of the measure
        measure = AddPTAC()

        # create runner with empty OSW
        osw = openstudio.WorkflowJSON()
        runner = openstudio.measure.OSRunner(osw)

        # load the test model
        osm_filepath = str(Path(__file__).parent.absolute() / "example_model.osm")
        model = osmod.Model.load(osm_filepath)

        assert model.is_initialized()
        model = model.get()

        # store the number of spaces in the seed model
        num_spaces_seed = len(model.getSpaces())

        # get arguments
        arguments = measure.arguments(model)
        argument_map = openstudio.measure.convertOSArgumentVectorToMap(arguments)

        # create hash of argument values.
        # If the argument has a default that you want to use,
        # you don't need it in the dict
        args_dict = {}
        args_dict['heating_type'] = 'Gas'
        args_dict['fan_type'] = 'Cycling'
        # using defaults values from measure.py for other arguments

        # populate argument with specified hash value if specified
        for arg in arguments:
            temp_arg_var = arg.clone()
            if arg.name() in args_dict:
                assert temp_arg_var.setValue(args_dict[arg.name()])
                argument_map[arg.name()] = temp_arg_var

        # run the measure
        measure.run(model, runner, argument_map)
        result = runner.result()

        # show the output
        # show_output(result)
        print(f"results: {result}")

        # assert that it ran correctly
        assert result.value().valueName() == "Success"
        assert len(result.info()) == 1
        assert len(result.warnings()) == 0
        assert result.info()[0].logMessage() == 'Added PTAC with Single Speed DX AC, Gas heating and Cycling fan to all thermal zones'
