"""Build a rigged, primitive-based 3D model of Nobi in Blender.

Why: the SDXL+ControlNet pipeline needs constant per-shot fighting (color
bleed, proportion drift) because it re-imagines the character from scratch
every generation. A real rigged 3D asset is consistent by construction --
build once, then every future shot is just posing + camera + lighting, no
more regeneration or color-correction fights.

Run headless with Blender itself (NOT a regular python interpreter):
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python build_nobi_3d.py
"""
import math
import os

import bpy

OUT_DIR = r"C:\Users\Isaak\nobi\production\3d"
FACE_TEXTURE = os.path.join(OUT_DIR, "face_texture.png")

# -- palette (sampled/approximated from the approved SDXL renders) --
YELLOW = (0.98, 0.75, 0.05, 1.0)
BLUE = (0.10, 0.28, 0.80, 1.0)
BLUE_DARK = (0.07, 0.20, 0.60, 1.0)
BLACK = (0.06, 0.06, 0.07, 1.0)
BROWN = (0.35, 0.20, 0.10, 1.0)
BROWN_DARK = (0.25, 0.14, 0.07, 1.0)
WHITE = (0.95, 0.95, 0.95, 1.0)

# -- proportions (chibi: huge head, short stubby body/legs, no visible neck) --
HEAD_SIZE = 0.8
TORSO_H = 0.55
TORSO_W = 0.62
TORSO_D = 0.4
LEG_H = 0.5
LEG_W = 0.22
FOOT_H = 0.16
ARM_LEN = 0.4
ARM_R = 0.13
HAND_R = 0.15

FEET_Z = 0.0
LEG_TOP_Z = FEET_Z + FOOT_H + LEG_H
TORSO_BOTTOM_Z = LEG_TOP_Z
TORSO_TOP_Z = TORSO_BOTTOM_Z + TORSO_H
HEAD_CENTER_Z = TORSO_TOP_Z + HEAD_SIZE / 2 - 0.05  # slight overlap, no visible neck


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures):
        for block in list(block_collection):
            block_collection.remove(block)


def make_material(name, color, roughness=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def make_face_material():
    mat = bpy.data.materials.new("Nobi_Face")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(FACE_TEXTURE)
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def add_cube(name, size_xyz, loc, mat, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_xyz[0], size_xyz[1], size_xyz[2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 4
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(mat)
    return obj


def add_cylinder(name, radius, depth, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = radius * 0.15
    mod.segments = 3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(mat)
    return obj


def add_sphere(name, radius, loc, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=24, ring_count=16)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def build_head(mat_yellow, mat_face):
    obj = add_cube("Head", (HEAD_SIZE, HEAD_SIZE, HEAD_SIZE), (0, 0, HEAD_CENTER_Z), mat_yellow, bevel=0.1)
    obj.data.materials.append(mat_face)
    # assign the front-facing polygon (min Y after bevel, largest flat face) to the face material
    mesh = obj.data
    best_i, best_area, best_ny = -1, 0, 1
    for poly in mesh.polygons:
        if poly.normal.y < -0.9 and poly.area > best_area:
            best_area = poly.area
            best_i = poly.index
    if best_i >= 0:
        mesh.polygons[best_i].material_index = 1
        # simple planar UVs for that face
        uv_layer = mesh.uv_layers.active or mesh.uv_layers.new()
        poly = mesh.polygons[best_i]
        xs = [mesh.vertices[mesh.loops[li].vertex_index].co.x for li in poly.loop_indices]
        zs = [mesh.vertices[mesh.loops[li].vertex_index].co.z for li in poly.loop_indices]
        minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
        for li in poly.loop_indices:
            v = mesh.vertices[mesh.loops[li].vertex_index]
            u = (v.co.x - minx) / (maxx - minx) if maxx > minx else 0.5
            vv = (v.co.z - minz) / (maxz - minz) if maxz > minz else 0.5
            uv_layer.data[li].uv = (u, vv)
    return obj


def build_body(mat_blue, mat_black, mat_brown, mat_brown_dark, mat_white, mat_yellow):
    torso_z = (TORSO_BOTTOM_Z + TORSO_TOP_Z) / 2
    torso = add_cube("Torso", (TORSO_W, TORSO_D, TORSO_H), (0, 0, torso_z), mat_blue, bevel=0.08)

    pocket = add_cube("Pocket", (0.32, 0.05, 0.2), (0, -TORSO_D / 2 - 0.01, torso_z - TORSO_H * 0.22), mat_blue, bevel=0.02)

    for dx in (-0.08, 0.08):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.22, location=(dx, -TORSO_D / 2 - 0.02, TORSO_TOP_Z - 0.05))
        s = bpy.context.active_object
        s.name = f"Drawstring_{dx}"
        s.data.materials.append(mat_white)

    backpack = add_cube("Backpack", (0.4, 0.18, 0.48), (0, TORSO_D / 2 + 0.08, torso_z + 0.02), mat_brown, bevel=0.08)
    for dx in (-0.18, 0.18):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(dx, 0, TORSO_TOP_Z - 0.1))
        strap = bpy.context.active_object
        strap.name = f"Strap_{dx}"
        strap.scale = (0.05, TORSO_D / 2 + 0.05, 0.02)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        strap.data.materials.append(mat_brown_dark)

    legs, feet = [], []
    for side, dx in (("L", -0.15), ("R", 0.15)):
        leg = add_cylinder(f"Leg_{side}", LEG_W / 2, LEG_H, (dx, 0, LEG_TOP_Z - LEG_H / 2), mat_black)
        foot = add_cube(f"Foot_{side}", (0.26, 0.42, FOOT_H), (dx, 0.06, FEET_Z + FOOT_H / 2), mat_blue, bevel=0.04)
        sole = add_cube(f"Sole_{side}", (0.26, 0.42, 0.04), (dx, 0.06, FEET_Z + 0.02), mat_white, bevel=0.02)
        legs.append(leg)
        feet.append((foot, sole))

    arms, hands = [], []
    shoulder_z = TORSO_TOP_Z - 0.08
    for side, dx in (("L", -TORSO_W / 2 - ARM_R + 0.02), ("R", TORSO_W / 2 + ARM_R - 0.02)):
        arm = add_cylinder(f"Arm_{side}", ARM_R, ARM_LEN, (dx, 0, shoulder_z - ARM_LEN / 2), mat_blue, rot=(0, 0, 0))
        hand = add_sphere(f"Hand_{side}", HAND_R, (dx, 0, shoulder_z - ARM_LEN - HAND_R * 0.3), mat_yellow)
        arms.append(arm)
        hands.append(hand)

    return {
        "torso": torso, "pocket": pocket, "backpack": backpack,
        "legs": legs, "feet": feet, "arms": arms, "hands": hands,
    }


def build_armature(parts, head_obj):
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = "NobiRig"
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_obj.data.edit_bones
    ebones.remove(ebones[0])

    def add_bone(name, head, tail, parent=None):
        b = ebones.new(name)
        b.head = head
        b.tail = tail
        if parent:
            b.parent = ebones[parent]
        return b

    add_bone("Root", (0, 0, 0), (0, 0, LEG_TOP_Z * 0.5))
    add_bone("Spine", (0, 0, LEG_TOP_Z), (0, 0, TORSO_TOP_Z), parent="Root")
    add_bone("Head", (0, 0, TORSO_TOP_Z), (0, 0, HEAD_CENTER_Z + HEAD_SIZE / 2), parent="Spine")
    shoulder_z = TORSO_TOP_Z - 0.08
    add_bone("Arm_L", (-TORSO_W / 2, 0, shoulder_z), (-TORSO_W / 2 - ARM_R, 0, shoulder_z - ARM_LEN), parent="Spine")
    add_bone("Arm_R", (TORSO_W / 2, 0, shoulder_z), (TORSO_W / 2 + ARM_R, 0, shoulder_z - ARM_LEN), parent="Spine")
    add_bone("Leg_L", (-0.15, 0, LEG_TOP_Z), (-0.15, 0, FEET_Z), parent="Root")
    add_bone("Leg_R", (0.15, 0, LEG_TOP_Z), (0.15, 0, FEET_Z), parent="Root")

    bpy.ops.object.mode_set(mode="OBJECT")

    def parent_to_bone(obj, bone_name):
        obj.parent = arm_obj
        obj.parent_type = "BONE"
        obj.parent_bone = bone_name
        obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()
        # BONE parent offsets by bone length along local Y; compensate so the
        # mesh doesn't jump from its authored world position
        bpy.context.view_layer.update()

    parent_to_bone(head_obj, "Head")
    parent_to_bone(parts["torso"], "Spine")
    parent_to_bone(parts["pocket"], "Spine")
    parent_to_bone(parts["backpack"], "Spine")
    for obj in bpy.data.objects:
        if obj.name.startswith("Strap_") or obj.name.startswith("Drawstring_"):
            parent_to_bone(obj, "Spine")
    parent_to_bone(parts["arms"][0], "Arm_L")
    parent_to_bone(parts["hands"][0], "Arm_L")
    parent_to_bone(parts["arms"][1], "Arm_R")
    parent_to_bone(parts["hands"][1], "Arm_R")
    parent_to_bone(parts["legs"][0], "Leg_L")
    parent_to_bone(parts["feet"][0][0], "Leg_L")
    parent_to_bone(parts["feet"][0][1], "Leg_L")
    parent_to_bone(parts["legs"][1], "Leg_R")
    parent_to_bone(parts["feet"][1][0], "Leg_R")
    parent_to_bone(parts["feet"][1][1], "Leg_R")

    return arm_obj


def setup_render_scene():
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    mat = make_material("Ground_Mat", (0.85, 0.85, 0.88, 1.0), roughness=0.9)
    ground.data.materials.append(mat)

    bpy.ops.object.camera_add(location=(0, -4.2, 1.5), rotation=(math.radians(85), 0, 0))
    cam = bpy.context.active_object
    cam.name = "MainCamera"
    bpy.context.scene.camera = cam

    key = bpy.data.lights.new("Key", type="AREA")
    key.energy = 800
    key_obj = bpy.data.objects.new("Key", key)
    key_obj.location = (-3, -3, 4)
    key_obj.rotation_euler = (math.radians(55), 0, math.radians(-45))
    bpy.context.collection.objects.link(key_obj)

    fill = bpy.data.lights.new("Fill", type="AREA")
    fill.energy = 300
    fill_obj = bpy.data.objects.new("Fill", fill)
    fill_obj.location = (3, -2, 2)
    fill_obj.rotation_euler = (math.radians(70), 0, math.radians(45))
    bpy.context.collection.objects.link(fill_obj)

    world = bpy.context.scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.55, 0.75, 0.95, 1.0)
    bg.inputs[1].default_value = 1.0

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1350
    scene.render.film_transparent = False
    # AgX (Blender 4.x default) desaturates/tone-maps for realism -- fights
    # the flat saturated cartoon look established in the SDXL renders.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"


if __name__ == "__main__":
    clear_scene()

    mat_yellow = make_material("Nobi_Yellow", YELLOW)
    mat_face = make_face_material()
    mat_blue = make_material("Nobi_Blue", BLUE)
    mat_blue_dark = make_material("Nobi_BlueDark", BLUE_DARK)
    mat_black = make_material("Nobi_Black", BLACK, roughness=0.6)
    mat_brown = make_material("Nobi_Brown", BROWN)
    mat_brown_dark = make_material("Nobi_BrownDark", BROWN_DARK)
    mat_white = make_material("Nobi_White", WHITE, roughness=0.3)

    head_obj = build_head(mat_yellow, mat_face)
    parts = build_body(mat_blue, mat_black, mat_brown, mat_brown_dark, mat_white, mat_yellow)
    # NOTE: rigging deferred -- Blender's BONE parent_type offsets children by
    # the bone's tail-relative transform in a way matrix_parent_inverse alone
    # didn't cleanly compensate for (everything flew apart). Validate the
    # static mesh/proportions/colors first, fix rigging as a follow-up.
    # rig = build_armature(parts, head_obj)
    setup_render_scene()

    os.makedirs(OUT_DIR, exist_ok=True)
    blend_path = os.path.join(OUT_DIR, "nobi.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"Saved blend -> {blend_path}")

    fbx_path = os.path.join(OUT_DIR, "nobi.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=False, add_leaf_bones=False)
    print(f"Saved fbx -> {fbx_path}")

    glb_path = os.path.join(OUT_DIR, "nobi.glb")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB")
    print(f"Saved glb -> {glb_path}")

    render_path = os.path.join(OUT_DIR, "nobi_test_render.png")
    bpy.context.scene.render.filepath = render_path
    bpy.ops.render.render(write_still=True)
    print(f"Saved render -> {render_path}")
