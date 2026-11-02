"""《失眠》资产一键清理：统一尺寸、原点放到底部中心、按需减面，再导出 GLB。

用法（在命令行里运行，Blender 3.6 / 4.x 都可以）：

    blender -b -P blender_cleanup.py -- 输入.glb 输出.glb [--height 1.2] [--max-tris 5000] [--rotate 0]

参数：
    --height    把模型等比缩放到这个高度（单位：米 / three.js 单位）。不写就不缩放。
    --max-tris  三角面上限，超过就自动减面。不写就不减面。
    --rotate    绕竖直轴旋转多少度，用来把正面转到朝前（-Y，即 Blender 的前视图方向）。

带骨骼的角色（香蕉猫）请不要用 --max-tris，减面会弄坏蒙皮权重；面数在图生 3D 工具里控制。
"""
import argparse
import math
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--height", type=float, default=None)
    p.add_argument("--max-tris", type=int, default=None)
    p.add_argument("--rotate", type=float, default=0.0)
    return p.parse_args(argv)


def tri_count(objs):
    n = 0
    for o in objs:
        me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        n += sum(len(f.vertices) - 2 for f in me.polygons)
        o.to_mesh_clear()
    return n


def world_bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def main():
    a = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.src)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        sys.exit("文件里没有网格")
    has_armature = any(o.type == "ARMATURE" for o in bpy.context.scene.objects)

    # 所有顶层物体挂到一个空物体下，整体变换
    root = bpy.data.objects.new("root", None)
    bpy.context.scene.collection.objects.link(root)
    for o in list(bpy.context.scene.objects):
        if o is not root and o.parent is None:
            o.parent = root
    bpy.context.view_layer.update()

    if a.rotate:
        root.rotation_euler.z = math.radians(a.rotate)
        bpy.context.view_layer.update()

    lo, hi = world_bbox(meshes)
    size_z = hi.z - lo.z
    if a.height and size_z > 0:
        s = a.height / size_z
        root.scale = (s, s, s)
        bpy.context.view_layer.update()
        lo, hi = world_bbox(meshes)

    # 原点放到底部中心：把模型挪到脚底中心落在世界原点
    center = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    root.location -= center
    bpy.context.view_layer.update()

    before = tri_count(meshes)
    if a.max_tris and before > a.max_tris:
        if has_armature:
            print("警告：模型带骨骼，跳过减面，请在图生 3D 工具里控制面数")
        else:
            ratio = a.max_tris / before
            for o in meshes:
                m = o.modifiers.new("decimate", "DECIMATE")
                m.ratio = ratio
                bpy.context.view_layer.objects.active = o
                bpy.ops.object.modifier_apply(modifier=m.name)
    after = tri_count(meshes)

    lo, hi = world_bbox(meshes)
    print(f"三角面 {before} -> {after}")
    print(f"尺寸 宽 {hi.x - lo.x:.3f} 深 {hi.y - lo.y:.3f} 高 {hi.z - lo.z:.3f}")

    bpy.ops.export_scene.gltf(filepath=a.dst, export_format="GLB", export_yup=True, export_apply=True)
    print("已导出", a.dst)


main()
