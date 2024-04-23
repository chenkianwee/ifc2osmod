import numpy as np
import geomie3d
import ifcopenshell
import ifcopenshell.geom

def get_ifc_facegeom(ifc_object: ifcopenshell.entity_instance) -> tuple[np.ndarray, np.ndarray]:
    """
    get the face geometry of the ifc entty, only works with ifc entity with geometry
    
    Parameters
    ----------
    ifc_object : ifcopenshell.entity_instance.entity_instance
        ifcopenshell entity.
    
    Returns
    -------
    result : tuple[np.ndarray, np.ndarray]
        tuple[np.ndarray[number_of_verts, 3], np.ndarray[number_of_faces, 3]] 
    """
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, ifc_object)
    verts = shape.geometry.verts # X Y Z of vertices in flattened list e.g. [v1x, v1y, v1z, v2x, v2y, v2z, ...]
    verts3d = np.reshape(verts, (int(len(verts)/3), 3))
    verts3d = np.round(verts3d, decimals = 2)
    face_idx = shape.geometry.faces
    face_idx3d = np.reshape(face_idx, (int(len(face_idx)/3), 3))
    return verts3d, face_idx3d

def ifcopenshell_entity_geom2g3d(ifc_object: ifcopenshell.entity_instance) -> list[geomie3d.topobj.Face]:
    """
    Retrive the triangulated faces from the ifc_object. Merge the triangulated face from the ifcopenshell geometry into a single geomie3d face. 

    Parameters
    ----------
    ifc_object: ifcopenshell.entity_instance.entity_instance
        the ifc_object to retrieve geometry from.
    
    Returns
    -------
    faces : list[geomie3d.topobj.Face]
        list of geomie3d faces.
    """
    verts3d, face_idx3d = get_ifc_facegeom(ifc_object)
    g3d_verts = geomie3d.create.vertex_list(verts3d)
    face_pts = np.take(g3d_verts, face_idx3d, axis=0)
    flist = []
    for fp in face_pts:
        f = geomie3d.create.polygon_face_frm_verts(fp)
        flist.append(f)
    
    grp_faces = geomie3d.calculate.grp_faces_on_nrml(flist)
    mfs = []
    for grp_f in grp_faces[0]:
        outline = geomie3d.calculate.find_faces_outline(grp_f)[0]
        # geomie3d.viz.viz([{'topo_list': outline, 'colour': 'blue'}])
        n_loose_edges = 3
        loop_cnt = 0
        while n_loose_edges >= 3:
            path_dict = geomie3d.calculate.a_connected_path_from_edges(outline)
            outline = path_dict['connected']
            # geomie3d.viz.viz([{'topo_list': outline, 'colour': 'blue'}])
            bwire = geomie3d.create.wire_frm_edges(outline)
            mf = geomie3d.create.polygon_face_frm_wires(bwire)
            mfs.append(mf)
            outline = path_dict['loose']
            if loop_cnt == 0:
                n_loose_edges = len(path_dict['loose'])
            else:
                if n_loose_edges - len(path_dict['loose']) == 0:
                    n_loose_edges = 0
                else:        
                    n_loose_edges = len(path_dict['loose'])
            loop_cnt+=1
    return mfs
