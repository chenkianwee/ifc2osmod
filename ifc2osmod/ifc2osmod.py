import sys
import argparse
from pathlib import Path

import numpy as np
import geomie3d
import ifcopenshell
import ifcopenshell.geom
import openstudio
from openstudio import model as osmod

import openstudio_utils
import ifcopenshell_utils

#===================================================================================================
# region: FUNCTIONS

def parse_args():
    # create parser object
    parser = argparse.ArgumentParser(description = "Convert IFC Models to OpenStudio Models")
 
    # defining arguments for parser object
    parser.add_argument('-i', '--ifc', type = str, 
                        metavar = 'FILE', 
                        help = 'The file path of the IFC to convert')
    
    parser.add_argument('-o', '--osmod', type = str,
                        metavar = 'FILE', default = None,
                        help = 'The file path of the OpenStudio result')
    
    parser.add_argument('-n', '--ndecimals', type = int,
                        metavar = 'INT', default = 3,
                        help = 'The number of decimals to round to for the geometries')

    parser.add_argument('-v', '--viz', action = 'store_true', default=False,
                        help = 'visualize the calculation procedure if turned on')
    
    parser.add_argument('-p', '--process', action = 'store_true', default=False,
                        help = 'turn it on if piping in ifc filepath')
    
    # parse the arguments from standard input
    args = parser.parse_args()
    return args

def create_rays_frm_verts(vertices: list[geomie3d.topobj.Vertex], dir_xyz: list[float]) -> list[geomie3d.utility.Ray]:
    rays = []
    for v in vertices:
        ray = geomie3d.create.ray(v.point.xyz, dir_xyz)
        rays.append(ray)
    return rays

def extract_intx_frm_hit_rays(hit_rays: list[geomie3d.utility.Ray]) -> list[geomie3d.topobj.Vertex]:
    vs = []
    for r in hit_rays:
        att = r.attributes['rays_faces_intersection']
        intx = att['intersection'][0]
        v = geomie3d.create.vertex(intx)
        vs.append(v)
    return vs

def calc_vobj_height_width(xyzs: np.ndarray, zdir: list[float], ydir: list[float], viz: bool = False) -> tuple[float, float]:
    '''
    Calculates the height and width of a vertical element using the directions of the normal and x and y direction of the local coordinate.

    Parameters
    ----------
    xyzs : np.ndarray
        np.ndarray[shape(number of points, 3)]. Must be more than 3 points at least.
    
    xdir : list[float]
        The x direction of the vertical object

    ydir : list[float]
        the up/y direction of the vertical object. Obtained by cross product of nrml and xdir

    Returns
    -------
    height_width : tuple[float, float]
        the first value is the height, the second value is width
    '''
    bbox = geomie3d.calculate.bbox_frm_xyzs(xyzs)
    center_xyz = geomie3d.calculate.bboxes_centre([bbox])[0]
    # check the bounding box if it is a flat surface we can get the dimension easier
    xdim = bbox.maxx - bbox.minx
    ydim = bbox.maxy - bbox.miny
    zdim = bbox.maxz - bbox.minz
    win_dims = np.array([xdim, ydim, zdim])
    dim_cond = win_dims == 0
    dim_cond = np.where(dim_cond)[0]
    if dim_cond.size == 0:
        # the bbox is a box
        # project the center xyz up down left right to get the height and width
        r_up = geomie3d.create.ray(center_xyz, ydir)
        ydir_rev = geomie3d.calculate.reverse_vectorxyz(ydir)
        r_dn = geomie3d.create.ray(center_xyz, ydir_rev)
        r_z = geomie3d.create.ray(center_xyz, zdir)
        zdir_rev = geomie3d.calculate.reverse_vectorxyz(zdir)
        r_zneg = geomie3d.create.ray(center_xyz, zdir_rev)
        box = geomie3d.create.boxes_frm_bboxes([bbox])[0]
        box_faces = geomie3d.get.faces_frm_solid(box)
        box_faces = [geomie3d.modify.reverse_face_normal(wf) for wf in box_faces]
        dim_proj_res = geomie3d.calculate.rays_faces_intersection([r_up, r_dn, r_z, r_zneg], box_faces)
        hit_rays = dim_proj_res[0]
        intxs = extract_intx_frm_hit_rays(hit_rays)
        intxs_xyzs = [intx.point.xyz for intx in intxs]
        ct_pts = np.array([center_xyz, center_xyz, center_xyz, center_xyz])
        dists = geomie3d.calculate.dist_btw_xyzs(ct_pts, intxs_xyzs)
        height = dists[0] + dists[1]
        width = dists[2] + dists[3]
        if viz == True:
            center_vert = geomie3d.create.vertex(center_xyz)
            geomie3d.viz.viz([{'topo_list': [box], 'colour': 'blue'},
                              {'topo_list': [center_vert], 'colour': 'red'},
                              {'topo_list': intxs, 'colour': 'red'}])

    elif dim_cond.size == 1:
        #  the bbox is just a surface
        if dim_cond[0] == 0:
            height = zdim
            width = ydim
        if dim_cond[0] == 1:
            height = zdim
            width = xdim
    else:
        print('the bbox is either a line or a point, there is no height nor width')

    return height, width

def ifc2osmod(ifc_path: str, osmod_path: str, ndecimals: int, viz: bool) -> str:
    '''
    Converts ifc to openstudio model.

    Parameters
    ----------
    ifc_path : str
        The file path of the IFC to convert.
    
    osmod_path : str
        The file path of the OpenStudio result.

    ndecimals : int
        The number of decimals to round to for the geometries.

    viz : bool
        visualize the calculation procedure if turned on.

    Returns
    -------
    str
        The file path of the OpenStudio result
    '''
    #------------------------------------------------------------------------------------------------------
    # region: read the ifc file and extract all the necessary information for conversion to osm
    #------------------------------------------------------------------------------------------------------
    model = ifcopenshell.open(ifc_path)

    # region: get all the spaces
    spaces = model.by_type('IfcSpace')
    envelope = []
    env_dict = {}
    for space in spaces:
        space_info = space.get_info()
        space_name = space_info['LongName']
        mfs = ifcopenshell_utils.ifcopenshell_entity_geom2g3d(space)
        for cnt, mf in enumerate(mfs):
            proj_srfs = mfs[:]
            del proj_srfs[cnt]
            mf_mid = geomie3d.calculate.face_midxyz(mf)
            mf_mid_v = geomie3d.create.vertex(mf_mid)
            nrml = geomie3d.get.face_normal(mf)
            geomie3d.modify.update_topo_att(mf, {'space': space_name})
            env_name = space_name + '_envelope_' + str(cnt)
            geomie3d.modify.update_topo_att(mf, {'name': env_name})
            geomie3d.modify.update_topo_att(mf, {'normal': nrml})
            env_dict[env_name] = mf
            envelope.append(mf)
            # vs = geomie3d.create.vertex_list([space_center, mf_mid])
            # dir_edge = geomie3d.create.pline_edge_frm_verts(vs)
            # fedge = geomie3d.create.pline_edges_frm_face_normals([mf])
            
    face_plines = geomie3d.create.pline_edges_frm_face_normals(envelope)
    if viz == True:
        geomie3d.viz.viz([{'topo_list': envelope, 'colour': 'blue', 'attribute': 'space'}, 
                          {'topo_list': face_plines, 'colour': 'red'}])

    # endregion: get all the spaces
    
    # region: get all the windows
    ifc_windows = model.by_type('IfcWindow')
    # flip all the envelope so that the wall is facing both sides
    envelope_flip = [geomie3d.modify.reverse_face_normal(envf) for envf in envelope]
    proj_env_srf = envelope[:]
    proj_env_srf.extend(envelope_flip)
    windows = []
    for win in ifc_windows:
        # find the center point of the window
        verts3d, face_idx3d = ifcopenshell_utils.get_ifc_facegeom(win)
        g3d_verts = geomie3d.create.vertex_list(verts3d)
        bbox = geomie3d.calculate.bbox_frm_xyzs(verts3d)
        center_xyz = geomie3d.calculate.bboxes_centre([bbox])[0]
        center_vert = geomie3d.create.vertex(center_xyz)

        # using the center point, project rays out and find the closest envelope surfaces
        rays = geomie3d.create.rays_d4pi_frm_verts([center_vert], ndirs = 12, vert_id = False)
        ray_res = geomie3d.calculate.rays_faces_intersection(rays, proj_env_srf)
        hit_rays = ray_res[0]
        dists = []
        hit_faces = []
        win_wall_intxs = []
        for r in hit_rays:
            orig = r.origin
            att = r.attributes['rays_faces_intersection']
            hit_face = att['hit_face'][0]
            intx = att['intersection'][0]
            dist = geomie3d.calculate.dist_btw_xyzs(orig, intx)
            hit_faces.append(hit_face)
            dists.append(dist)
            win_wall_intxs.append(intx)

        min_id = np.argmin(dists)
        min_face = hit_faces[min_id]
        min_face_intx = win_wall_intxs[min_id]
        # get the normal of the wall srf and use it for projection later
        n = geomie3d.get.topo_atts(min_face)['normal']
        n_rev = geomie3d.calculate.reverse_vectorxyz(n)
        n_rev = np.round(n_rev, decimals=ndecimals)
        # move the points alittle further away from the surface so that all can be projected properly to the surface
        cmp_verts = geomie3d.create.composite(g3d_verts)
        target_xyz = geomie3d.calculate.move_xyzs([center_xyz], [n], 1.0)[0]
        mv_cmp_verts = geomie3d.modify.move_topo(cmp_verts, target_xyz, ref_xyz=center_xyz)
        mv_verts = geomie3d.get.vertices_frm_composite(mv_cmp_verts)
        # check if the window is contain within the wall project all the points onto the wall
        rays = create_rays_frm_verts(mv_verts, n_rev)
        min_f_orig_nrml = geomie3d.get.face_normal(min_face)
        is_nrml_eq = np.array_equal(min_f_orig_nrml, n)
        if is_nrml_eq != True:
            # look for the equivalent
            min_face_att = geomie3d.get.topo_atts(min_face)
            min_face_name = min_face_att['name']
            min_face = env_dict[min_face_name]

        proj_res = geomie3d.calculate.rays_faces_intersection(rays, [min_face])
        if len(proj_res[0]) == len(g3d_verts):
            is_win_in_wall = True
        else:
            is_win_in_wall = False

        # region: for viz
        # intx_v = extract_intx_frm_hit_rays(proj_res[0])
        # geomie3d.viz.viz([{'topo_list': intx_v, 'colour': 'red'},
        #                   {'topo_list': [min_face], 'colour': 'blue'},
        #                   {'topo_list': mv_verts, 'colour': 'green'}])
        # endregion: for viz
        
        if is_win_in_wall:
            # if the window is contain within the wall
            # project the bbox onto the closest surface base on the reverse surface normal
            fuse1 = []
            box = geomie3d.create.boxes_frm_bboxes([bbox])[0]
            box_faces = geomie3d.get.faces_frm_solid(box)
            for box_face in box_faces:
                verts = geomie3d.get.vertices_frm_face(box_face)
                bface_rays = create_rays_frm_verts(verts, n_rev)
                ray_res2 = geomie3d.calculate.rays_faces_intersection(bface_rays, [min_face])
                hit_rays2 = ray_res2[0]
                intx_v = extract_intx_frm_hit_rays(hit_rays2)
                fused_intx = geomie3d.modify.fuse_vertices(intx_v, decimals=ndecimals)
                if len(fused_intx) > 3:
                    fuse1.extend(fused_intx)
            
            if len(fuse1) != 0:
                fuse2 = geomie3d.modify.fuse_vertices(fuse1, decimals=ndecimals)
                fuse_face = geomie3d.create.polygon_face_frm_verts(fuse2)
                if 'children' in min_face.attributes.keys():
                    min_face.attributes['children'].append(fuse_face)
                else:
                    min_face.attributes['children'] = [fuse_face]
                windows.append(fuse_face)
        else:
            # use the center point and project out to the bbox to get the win height and width
            up_dir = [0,0,1]        
            angle = geomie3d.calculate.angle_btw_2vectors(n, up_dir)
            if -90 <= angle <= 90: # the surface is vertical
                if round(angle, 1) != 90:
                    # that means the wall is not straight but slanted
                    z_dir = geomie3d.calculate.cross_product(n, up_dir)
                    rot_mat = geomie3d.calculate.rotate_matrice(z_dir, angle)
                    y_dir = geomie3d.calculate.trsf_xyzs([n], rot_mat)[0]
                else:
                    y_dir = up_dir
                    # get the x-dir of the wall, considering if up is Y and the normal is X
                    z_dir = geomie3d.calculate.cross_product(n, y_dir)
                    # region: for visualizing the wall local coordinate system
                    # y_pt = geomie3d.calculate.move_xyzs([center_xyz], [y_dir], [10])[0]
                    # y_v = geomie3d.create.vertex_list([center_xyz, y_pt])
                    # yedge = geomie3d.create.pline_edge_frm_verts(y_v)

                    # z_pt = geomie3d.calculate.move_xyzs([center_xyz], [z_dir], [10])[0]
                    # z_v = geomie3d.create.vertex_list([center_xyz, z_pt])
                    # zedge = geomie3d.create.pline_edge_frm_verts(z_v)
                    
                    # x_pt = geomie3d.calculate.move_xyzs([center_xyz], [n], [10])[0]
                    # x_v = geomie3d.create.vertex_list([center_xyz, x_pt])
                    # xedge = geomie3d.create.pline_edge_frm_verts(x_v)
                    # endregion: for visualizing the wall local coordinate system
                    # get the window height and width
                    win_height, win_width = calc_vobj_height_width(verts3d, z_dir, y_dir, viz = False)

            # get wall height and width
            wall_verts = geomie3d.get.vertices_frm_face(min_face)
            wall_xyzs = [wall_vert.point.xyz for wall_vert in wall_verts]
            wall_height, wall_width = calc_vobj_height_width(wall_xyzs, z_dir, y_dir, viz = False)
            # compare their dimension and make adjustment for the 
            win_dims = np.array([win_height, win_width])
            wall_dims = np.array([wall_height, wall_width])
            dim_cond = win_dims >= wall_dims
            win_dims_rev = np.where(dim_cond, wall_dims-0.5, win_dims)
            # create a rectangle based on the height and width
            win = geomie3d.create.polygon_face_frm_midpt(center_xyz, win_dims_rev[1], win_dims_rev[0],)
            # cs transfer and map the rectangle onto the wall
            orig_xdir = geomie3d.get.face_normal(win)
            orig_ydir = [0, 1, 0]
            orig_cs = geomie3d.utility.CoordinateSystem(center_xyz, orig_xdir, orig_ydir)
            dest_cs = geomie3d.utility.CoordinateSystem(min_face_intx, n, y_dir)
            win_trsf = geomie3d.modify.trsf_topo_based_on_cs(win, orig_cs, dest_cs)

            if 'children' in min_face.attributes.keys():
                    min_face.attributes['children'].append(win_trsf)
            else:
                min_face.attributes['children'] = [win_trsf]

            windows.append(win_trsf)
    # endregion: get all the windows

    # region: get all the shading surfaces
    ifc_shadings = model.by_type('IfcShadingDevice')
    shade_list = []
    for ifcshade in ifc_shadings:
        # get the geometrical data from the shadings
        shade_faces = ifcopenshell_utils.ifcopenshell_entity_geom2g3d(ifcshade)
        shade_list.extend(shade_faces)
    # endregion: get all the shading surfaces

    if viz == True:
        win_nrml_edges = geomie3d.create.pline_edges_frm_face_normals(windows)
        env_nrml_edges = geomie3d.create.pline_edges_frm_face_normals(envelope)
        if len(shade_list) != 0:    
            shade_nrml_edges = geomie3d.create.pline_edges_frm_face_normals(shade_list, magnitude=1)
            geomie3d.viz.viz([{'topo_list': windows, 'colour': 'blue'},
                            {'topo_list': envelope, 'colour': 'red'},
                            {'topo_list': win_nrml_edges, 'colour': 'green'},
                            {'topo_list': env_nrml_edges, 'colour': 'white'},
                            {'topo_list': shade_list, 'colour': 'green'},
                            {'topo_list': shade_nrml_edges, 'colour': 'red'}])
            
        else:
            geomie3d.viz.viz([{'topo_list': windows, 'colour': 'blue'},
                            {'topo_list': envelope, 'colour': 'red'},
                            {'topo_list': win_nrml_edges, 'colour': 'green'},
                            {'topo_list': env_nrml_edges, 'colour': 'white'},])
    #------------------------------------------------------------------------------------------------------
    # endregion: read the ifc file and extract all the necessary information for conversion to osm
    #------------------------------------------------------------------------------------------------------
    # region: setup openstudio model
    #------------------------------------------------------------------------------------------------------
    m = osmod.Model()
    
    # region: convert the geometry 
    osbldgstry = osmod.BuildingStory(m)
    osbldgstry.setName('Mezzanine Level')

    # region: create wall materials and construction
    # defining wall material Material:NoMass, this is used when only the R value is known
    roughness = 'Rough'
    therm_resistance = 0.36 # m2-K/W
    therm_absorp = 0.9 # fraction of incident long wavelength (>2.5 µm) radiation that is absorbed by the material
    solar_absorp = 0.7 #  fraction of incident solar radiation that is absorbed by the materia
    viz_absorp = 0.7 # fraction of incident visible wavelength radiation that is absorbed by the material

    metal_clad_mat = osmod.MasslessOpaqueMaterial(m, roughness, therm_resistance)
    metal_clad_mat.setThermalAbsorptance(therm_absorp)
    metal_clad_mat.setSolarAbsorptance (solar_absorp)
    metal_clad_mat.setVisibleAbsorptance (viz_absorp)

    roughness = 'Smooth'
    thickness = 0.009 # meter
    conductivity = 0.58 # W/(m-K)
    density = 1900 # kg/m3
    specific_heat = 1400 # J/(kg-K)
    cement_board_mat = osmod.StandardOpaqueMaterial(m, roughness, thickness, 
                                                    conductivity, density, specific_heat)
    wall_const = osmod.Construction(m)
    wall_const.setName('wall_construction')
    wall_const.setLayers([metal_clad_mat, cement_board_mat])
    # endregion: create wall materials and construction

    # region: create window material and construction
    ufactor = 1.4 # w/m2-K
    shgc = 0.62 # solar heat gain coefficient
    viz_tran = 0.78 # visible transmittance
    lowe_glz_mat = osmod.SimpleGlazing(m, ufactor, shgc)
    lowe_glz_mat.setVisibleTransmittance(viz_tran)
    win_const = osmod.Construction(m)
    win_const.setName('win_construction')
    win_const.setLayers([lowe_glz_mat])
    # endregion: create window material and construction

    # region: convert ifc 2 osm geometries
    space_ls = []
    for env_srf in envelope:
        srf_att = env_srf.attributes
        osspace_name = srf_att['space']
        if osspace_name not in space_ls:
            oszone = osmod.ThermalZone(m)
            osspace = osmod.Space(m)
            osspace.setName(osspace_name)
            osspace.setBuildingStory(osbldgstry)
            osspace.setThermalZone(oszone)
            space_ls.append(osspace_name)

        nrml = geomie3d.get.face_normal(env_srf)
        are_convex = geomie3d.calculate.are_polygon_faces_convex([env_srf])[0]
        if are_convex:
            vs = geomie3d.get.vertices_frm_face(env_srf)
            pt3ds = openstudio_utils.g3dverts2ospt3d(vs, decimals = ndecimals)
            ossrf = osmod.Surface(pt3ds, m)
            ossrf.setSpace(osspace)
            ossrf.setConstruction(wall_const)
        else:
            tri_faces = geomie3d.modify.triangulate_face(env_srf)
            for tri in tri_faces:
                tnmrl = geomie3d.get.face_normal(tri)
                vs = geomie3d.get.vertices_frm_face(tri)
                pt3ds = openstudio_utils.g3dverts2ospt3d(vs, decimals = ndecimals)
                ossrf = osmod.Surface(pt3ds, m)
                ossrf.setSpace(osspace)
                ossrf.setConstruction(wall_const)

        if 'children' in srf_att.keys():
            children = env_srf.attributes['children']
            parent_nrml = geomie3d.get.face_normal(env_srf)
            parent_nrml = np.round(parent_nrml, decimals=3)
            for child_srf in children:
                child_nrml = geomie3d.get.face_normal(child_srf)
                child_nrml = np.round(child_nrml, decimals=ndecimals)
                child_vs = geomie3d.get.vertices_frm_face(child_srf)
                child_pt3ds = openstudio_utils.g3dverts2ospt3d(child_vs, decimals=ndecimals)
                if not np.array_equal(child_nrml, parent_nrml):
                    child_pt3ds.reverse()
                child_ossrf = osmod.SubSurface(child_pt3ds, m)
                child_ossrf.setSurface(ossrf)
                child_ossrf.setConstruction(win_const)
    # endregion: convert ifc 2 osm geometries

    # region: convert the shading
    osshade_grp = osmod.ShadingSurfaceGroup(m)
    for shade in shade_list:
        is_convex = geomie3d.calculate.are_polygon_faces_convex([shade])[0]
        if is_convex:
            shade_verts = geomie3d.get.vertices_frm_face(shade)
            os3dpts = openstudio_utils.g3dverts2ospt3d(shade_verts)
            os_shade = osmod.ShadingSurface(os3dpts, m)
            os_shade.setShadingSurfaceGroup(osshade_grp)
        else:
            tri_faces = geomie3d.modify.triangulate_face(shade)
            for tri in tri_faces:
                shade_verts = geomie3d.get.vertices_frm_face(tri)
                os3dpts = openstudio_utils.g3dverts2ospt3d(shade_verts)
                os_shade = osmod.ShadingSurface(os3dpts, m)
                os_shade.setShadingSurfaceGroup(osshade_grp)

    # endregion: convert the shading

    # endregion: convert the geometry 
    
    # region: setup the schedules 
    #------------------------------------------------------------------------------------------------------
    # setup time
    time9 = openstudio.openstudioutilitiestime.Time(0,9,0,0)
    time17 = openstudio.openstudioutilitiestime.Time(0,17,0,0)
    time24 = openstudio.openstudioutilitiestime.Time(0,24,0,0)
    # region:setup schedule type limits
    sch_type_lim_frac = osmod.ScheduleTypeLimits(m)
    sch_type_lim_frac.setName('fractional')
    sch_type_lim_frac.setLowerLimitValue(0.0)
    sch_type_lim_frac.setUpperLimitValue(1.0)
    sch_type_lim_frac.setNumericType('Continuous')

    sch_type_lim_temp = osmod.ScheduleTypeLimits(m)
    sch_type_lim_temp.setName('temperature')
    sch_type_lim_temp.setLowerLimitValue(-60)
    sch_type_lim_temp.setUpperLimitValue(200)
    sch_type_lim_temp.setNumericType('Continuous')
    sch_type_lim_temp.setUnitType('Temperature')

    sch_type_lim_act = osmod.ScheduleTypeLimits(m)
    sch_type_lim_act.setName('activity')
    sch_type_lim_act.setLowerLimitValue(0)
    sch_type_lim_act.setNumericType('Continuous')
    sch_type_lim_act.setUnitType('ActivityLevel')
    # endregion:setup schedule type limits
    # region: setup occ schedule
    sch_day_occ = osmod.ScheduleDay(m)
    sch_day_occ.setName('weekday occupancy')
    sch_day_occ.setScheduleTypeLimits(sch_type_lim_frac)
    sch_day_occ.addValue(time9, 0.0)
    sch_day_occ.addValue(time17, 1.0)

    sch_ruleset_occ = osmod.ScheduleRuleset(m)
    sch_ruleset_occ.setName('occupancy schedule')
    sch_ruleset_occ.setScheduleTypeLimits(sch_type_lim_frac)

    sch_rule_occ = osmod.ScheduleRule(sch_ruleset_occ, sch_day_occ)
    sch_rule_occ.setName('occupancy weekdays')
    sch_rule_occ.setApplyWeekdays(True)
    # endregion: setup occ schedule
    # region: setup activity schedule
    sch_day_act = osmod.ScheduleDay(m)
    sch_day_act.setName('weekday activity')
    sch_day_act.setScheduleTypeLimits(sch_type_lim_act)
    sch_day_act.addValue(time24, 70)

    sch_ruleset_act = osmod.ScheduleRuleset(m)
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
    sch_day_cool_tstat = osmod.ScheduleDay(m)
    sch_day_cool_tstat.setName('thermostat cooling weekday schedule')
    sch_day_cool_tstat.setScheduleTypeLimits(sch_type_lim_temp)
    sch_day_cool_tstat.addValue(time9, 60.0)
    sch_day_cool_tstat.addValue(time17, 25.0)
    sch_day_cool_tstat.addValue(time24, 60.0)

    sch_day_cool_tstat2 = osmod.ScheduleDay(m)
    sch_day_cool_tstat2.setName('thermostat cooling weekends schedule')
    sch_day_cool_tstat2.setScheduleTypeLimits(sch_type_lim_temp)
    sch_day_cool_tstat2.addValue(time24, 60.0)

    sch_day_cool_tstat3 = osmod.ScheduleDay(m)
    sch_day_cool_tstat3.setName('thermostat cooling design day schedule')
    sch_day_cool_tstat3.setScheduleTypeLimits(sch_type_lim_temp)
    sch_day_cool_tstat3.addValue(time9, 25.0)
    sch_day_cool_tstat3.addValue(time17, 25.0)
    sch_day_cool_tstat3.addValue(time24, 25.0)

    sch_ruleset_cool_tstat = osmod.ScheduleRuleset(m)
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
    sch_day_hot_tstat = osmod.ScheduleDay(m)
    sch_day_hot_tstat.setName('thermostat heating weekday schedule')
    sch_day_hot_tstat.setScheduleTypeLimits(sch_type_lim_temp)
    sch_day_hot_tstat.addValue(time9, 20.0)
    sch_day_hot_tstat.addValue(time17, 20.0)
    sch_day_hot_tstat.addValue(time24, 20.0)

    sch_ruleset_hot_tstat = osmod.ScheduleRuleset(m)
    sch_ruleset_hot_tstat.setName('thermostat heating ruleset')
    sch_ruleset_hot_tstat.setScheduleTypeLimits(sch_type_lim_temp)
    sch_ruleset_cool_tstat.setWinterDesignDaySchedule(sch_day_hot_tstat)

    sch_rule_hot_tstat = osmod.ScheduleRule(sch_ruleset_hot_tstat, sch_day_hot_tstat)
    sch_rule_hot_tstat.setName('thermostat heating weekday rule')
    sch_rule_hot_tstat.setApplyAllDays(True)
    # endregion: setup thermostat heating setpoint

    tstat = osmod.ThermostatSetpointDualSetpoint(m)
    tstat.setCoolingSetpointTemperatureSchedule(sch_ruleset_cool_tstat)
    tstat.setHeatingSetpointTemperatureSchedule(sch_ruleset_hot_tstat)
    # endregion: setup the schedules 
    
    # region: setup the thermalzones 
    #------------------------------------------------------------------------------------------------------
    # set the internal loads of the space
    # setup the lighting schedule
    light = openstudio_utils.setup_light_schedule(m, sch_ruleset_occ)
    # setup electric equipment schedule
    elec_equip = openstudio_utils.setup_elec_equip_schedule(m, sch_ruleset_occ)

    spaces = osmod.getSpaces(m)
    # occ_numbers = [34, 71]
    occ_numbers = [25, 50]
    light_watts_m2 = 5
    elec_watts_m2 = 10
    thermal_zones =[]
    for cnt, space in enumerate(spaces):
        space_name = space.nameString()
        space.autocalculateFloorArea()
        outdoor_air = osmod.DesignSpecificationOutdoorAir(m)
        outdoor_air.setOutdoorAirFlowperPerson(0.006) #m3/s
        space.setDesignSpecificationOutdoorAir(outdoor_air)
        # setup people schedule
        ppl = openstudio_utils.setup_ppl_schedule(m, sch_ruleset_occ, sch_ruleset_act, name = space_name + '_people')
        space.setNumberOfPeople(occ_numbers[cnt], ppl)
        space.setLightingPowerPerFloorArea(light_watts_m2, light)
        space.setElectricEquipmentPowerPerFloorArea(elec_watts_m2, elec_equip)
        # setup the thermostat schedule
        thermalzone = space.thermalZone()
        if thermalzone.empty() == False:
            thermalzone_real = thermalzone.get()
            thermalzone_real.setThermostatSetpointDualSetpoint(tstat)
            thermal_zones.append(thermalzone_real)
    #------------------------------------------------------------------------------------------------------
    # endregion: setup the thermalzones 
    
    #------------------------------------------------------------------------------------------------------
    # endregion: setup openstudio model
    #------------------------------------------------------------------------------------------------------
    m.save(osmod_path, True)
    return osmod_path
    
# endregion: FUNCTIONS
#===================================================================================================
#===================================================================================================
# region: Main
if __name__=='__main__':
    args = parse_args()
    # number of decimal places to round the geometry coordinates to
    ndecimals = args.ndecimals
    pipe_input = args.process
    if pipe_input == False:
        ifc_path = args.ifc
    else:
        lines = list(sys.stdin)
        ifc_path = lines[0].strip()

    osmod_path = args.osmod
    if osmod_path == None:
        ifc_parent_path = Path(ifc_path).parent
        ifc_name = Path(ifc_path).name
        ifc_name = ifc_name.lower().replace('.ifc', '')
        res_folder = ifc_parent_path.joinpath(ifc_name)
        if res_folder.exists() == False:
            res_folder.mkdir(parents=True)
        osmod_path = res_folder.joinpath(ifc_name + '.osm')
    else:
        res_folder = Path(osmod_path).parent
        if res_folder.exists() == False:
            res_folder.mkdir(parents=True)

    viz = args.viz

    osmod_res_path = ifc2osmod(ifc_path, osmod_path, ndecimals, viz)
    # make sure this output can be piped into another command on the cmd
    print(osmod_res_path)
    sys.stdout.flush()
# endregion: Main
#===================================================================================================