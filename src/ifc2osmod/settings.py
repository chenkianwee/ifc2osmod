from importlib.resources import files

PSET_DATA_DIR = files('ifc2osmod.data').joinpath('json').joinpath('ifc_psets')
OSMOD_DATA_DIR = files('ifc2osmod.data').joinpath('json').joinpath('osmod_data')
OSMOD_OPQ_CONSTR_PATH = OSMOD_DATA_DIR.joinpath('osmod_opq_constr_info.json')
OSMOD_SMPL_GLZ_CONSTR_PATH = OSMOD_DATA_DIR.joinpath('osmod_smpl_glz_constr_info.json')
ASHRAE_DATA_DIR = files('ifc2osmod.data').joinpath('json').joinpath('ashrae90_1')
