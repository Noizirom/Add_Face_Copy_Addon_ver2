
bl_info = {
    "name": "Face Copy Add-on",
    "description":  "Adds a New Object from Selected Faces",
    "author": "Noizirom",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Add > Mesh > Face Copy Object",
    "warning": "", 
    "wiki_url": "https://github.com/Noizirom/Add_Face_Copy_Addon_ver2",
    "tracker_url": "",
    "category": "Add Mesh"
}


import bpy
import numpy as np
from copy import deepcopy as dc
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from bpy.props import (StringProperty,
                       BoolProperty,
                       FloatProperty,
                       PointerProperty
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )


# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------

#get selected verts, edges, and faces information
def get_sel():
    '''
    gs[0] = vert ##[0] = co, [1] = index, [2] = uv, [3] = normal, [4] = undeformed_co
    gs[1] = edge ##[0] = index, [1] = vert indexes
    gs[2] = face ##[0] = area, [1] = index, [2] = normal, [3] = center, [4] = vert indexes
    gs[3] = new from selected ##[0] = new vert index, [1] = new edge vert indexes,
    ##[2] = new face vert indexes, [3] = vert count, [4] = edge count, [5] = face count,
    ##[6] = new vertice index dictionary
    '''
    #vert, edge, face, new = get_sel()
    mode = bpy.context.active_object.mode
    vt = bpy.context.object.data.vertices
    ed = bpy.context.object.data.edges
    fa = bpy.context.object.data.polygons
    bpy.ops.object.mode_set(mode='OBJECT')
    #vertices
    countv = len(vt)
    selv = np.empty(countv, dtype=np.bool)
    vt.foreach_get('select', selv)
    co = np.empty(countv * 3, dtype=np.float32)
    vt.foreach_get('co', co)
    co.shape = (countv, 3)
    vidx = np.empty(countv, dtype=np.int32)
    vt.foreach_get('index', vidx)
    vnorm = np.empty(countv * 3, dtype=np.float32)
    vt.foreach_get('normal', vnorm)
    vnorm.shape = (countv, 3)
    und_co = np.empty(countv * 3, dtype=np.float32)
    vt.foreach_get('undeformed_co', und_co)
    und_co.shape = (countv, 3)
    uv_dict = {}#dc({loop.vertex_index: bpy.context.object.data.uv_layers.active.data[loop.index].uv for loop in bpy.context.object.data.loops})
    uv_co = np.array(1)#np.array([uv_dict[i] for i in vidx[selv]])
    #edges
    counte = len(ed)
    sele = np.empty(counte, dtype=np.bool)
    ed.foreach_get('select', sele)
    eidx = np.empty(counte, dtype=np.int32)
    ed.foreach_get('index', eidx)
    edg = np.array([i.vertices[:] for i in ed])
    #faces
    countf = len(fa)
    selfa = np.empty(countf, dtype=np.bool)
    fa.foreach_get('select', selfa)
    farea = np.empty(countf, dtype=np.float32)
    fa.foreach_get('area', farea)
    fidx = np.empty(countf, dtype=np.int32)
    fa.foreach_get('index', fidx)
    fnorm = np.empty(countf * 3, dtype=np.float32)
    fa.foreach_get('normal', fnorm)
    fnorm.shape = (countf, 3)
    fcnt = np.empty(countf * 3, dtype=np.float32)
    fa.foreach_get('center', fcnt)
    fcnt.shape = (countf, 3)
    fac = np.array([i.vertices[:] for i in fa])
    #New indexes
    v_count = len(vidx[selv])
    e_count = len(eidx[sele])
    f_count = len(fidx[selfa])
    new_idx = [i for i in range(v_count)]
    nv_Dict = {o: n for n, o in enumerate(vidx[selv].tolist())}
    new_e = [[nv_Dict[i] for i in nest] for nest in edg[sele]]
    new_f = [[nv_Dict[i] for i in nest] for nest in fac[selfa]]
    return dc([[co[selv], vidx[selv], uv_co, vnorm[selv], und_co[selv]], [eidx[sele], edg[sele]], [farea[selfa], fidx[selfa], fnorm[selfa], fcnt[selfa], fac[selfa]], [new_idx, new_e, new_f, v_count, e_count, f_count, nv_Dict]])

#creates new mesh
def obj_mesh(co, faces):
    cur = bpy.context.object
    mesh = bpy.data.meshes.new("Obj")
    mesh.from_pydata(co, [], faces)
    mesh.validate()
    mesh.update(calc_edges = True)
    Object = bpy.data.objects.new("Obj", mesh)
    Object.data = mesh
    bpy.context.collection.objects.link(Object)
    bpy.context.view_layer.objects.active = Object
    cur.select_set(False)
    Object.select_set(True)

#creates new object
def obj_new(Name, co, faces):
    obj_mesh(co, faces)
    bpy.data.objects["Obj"].name = Name
    bpy.data.meshes[bpy.data.objects[Name].data.name].name = Name

#find center geometry
def centroid(co):
    xt = [i[0] for i in co]
    yt = [i[1] for i in co]
    zt = [i[2] for i in co]
    count = len(co)
    return [sum(xt) / count, sum(yt) / count, sum(zt) / count]

# ------------------------------------------------------------------------    
#vertex group index list
def vg_idx_list(vgn):
    return([v.index for v in bpy.context.object.data.vertices if v.select and bpy.context.object.vertex_groups[vgn].index in [vg.group for vg in v.groups]])

#vertex group {name: [indexes]} dictionary
def vg_idx_dict(gs):
    #gs = get_sel()
    vn = [v.name for v in bpy.context.object.vertex_groups[:]]
    vd = {n: vg_idx_list(n) for n in vn}
    vdd = {k: vd[k] for k in vd if vd[k] != []}
    return dc({d: [gs[3][6][i] for i in vdd[d]] for d in vdd})

# ------------------------------------------------------------------------ 

#transfer vertex weight to new object
def transfer_vt(viw):
    vg = bpy.data.objects[bpy.context.scene.face_copy.obj_name].vertex_groups
    vt = bpy.data.objects[bpy.context.scene.face_copy.obj_name].data.vertices
    for vgroup in viw:
        nvg = bpy.data.objects[bpy.context.scene.face_copy.obj_name].vertex_groups.new(name=vgroup)
        nvg.add(viw[vgroup], 1.0, "ADD")

# ------------------------------------------------------------------------

# This allows you to right click on a button and link to documentation
def add_face_copy_manual_map():
    url_manual_prefix = "https://docs.blender.org/manual/en/latest/"
    url_manual_mapping = (
        ("bpy.ops.mesh.add_object", "scene_layout/object/types.html"),
    )
    return url_manual_prefix, url_manual_mapping


#Create the Copy Face Object
def add_object(self, context):
    gs = get_sel()
    if bpy.context.object.vertex_groups:
        viw = vg_idx_dict(gs)
        vni = {vg.name: vg.index for vg in bpy.context.object.vertex_groups }
    else:
        viw = {}
        vni = {}
    obj_new(bpy.context.scene.face_copy.obj_name, gs[0][0], gs[3][2])
    if bpy.context.scene.face_copy.add_vg_bool:
        transfer_vt(viw)
    if bpy.context.scene.face_copy.add_origin_bool:
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
    if bpy.context.scene.face_copy.set_smooth_bool:
        bpy.ops.object.shade_smooth()
   


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class FC_Properties(PropertyGroup):

    add_vg_bool: BoolProperty(
        name="Copy Vertex Groups",
        description="Copy Vertex Groups",
        default = False
        )

    add_origin_bool: BoolProperty(
        name="Origin at Centroid",
        description="Place origin at center of object",
        default = False
        )

    set_smooth_bool: BoolProperty(
        name = "Set Smooth",
        description = "New Object Set Smooth",
        default = False
        )

    obj_name: StringProperty(
        name="name",
        description="Enter the Object Name",
        default="Object",
        maxlen=1024,
        )


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class OBJECT_OT_add_face_copy(Operator):
    """Create a new Object from selected faces"""
    bl_idname = "mesh.add_face_copy"
    bl_label = "Add Face Copy"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):
        add_object(self, context)
        return {'FINISHED'}

# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------

class OBJECT_PT_FaceCopyPanel(Panel):
    bl_idname = "object.face_copy_panel"
    bl_label = "Add Face Copy"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Face_copy"
    
    @classmethod
    def poll(self,context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        facecopy = scene.face_copy

        layout.prop(facecopy, "add_vg_bool")
        layout.prop(facecopy, "add_origin_bool")
        layout.prop(facecopy, "set_smooth_bool")
        layout.prop(facecopy, "obj_name")
        layout.operator("mesh.add_face_copy")
        layout.separator()



# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    FC_Properties,
    OBJECT_OT_add_face_copy,
    OBJECT_PT_FaceCopyPanel,
)



def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.face_copy = PointerProperty(type=FC_Properties)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.face_copy


if __name__ == "__main__":
    register()