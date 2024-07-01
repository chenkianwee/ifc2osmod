import json

from jsonschema import validate as json_validate

import ifcopenshell_utils

pset_path = '/home/chenkianwee/kianwee_work/code_workspace/10.ifc2osmod/ifc2osmod/data/json/ifc_psets/osmod_material_schema.json'

with open(pset_path) as f:
    json_schema = json.load(f)

json_default = ifcopenshell_utils.get_default_pset(pset_path)

json_validate(instance=json_default['osmod_material'], schema=json_schema)
print(json_default)
