from pathlib import Path

PSET_DATA_DIR = Path(__file__).parent.parent.joinpath('data', 'json', 'ifc_psets')
OSMOD_DATA_DIR = Path(__file__).parent.parent.joinpath('data', 'json', 'osmod_data')
OSMOD_OPQ_CONSTR_PATH = OSMOD_DATA_DIR.joinpath('osmod_opq_constr_info.json')
OSMOD_SMPL_GLZ_CONSTR_PATH = OSMOD_DATA_DIR.joinpath('osmod_smpl_glz_constr_info.json')
ASHRAE_DATA_DIR = Path(__file__).parent.parent.joinpath('data', 'json', 'ashrae90_1')
PROTOBLDG_DATA_DIR = Path(__file__).parent.parent.joinpath('data', 'osmod')