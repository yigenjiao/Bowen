"""生成 GLB 体检台的两个演示样本（纯 numpy，无其他依赖）。

  healthy.glb  —— 贴图 + 两骨蒙皮 + 摆动动画的方柱，应当全部通过。
  broken.glb   —— 同一个模型，故意埋了 SKILL 文档里踩过的坑：
                  bindposes 按行主序写入 / 黑色 COLOR_0 乘贴图 / 法线没归一 /
                  索引越界 / 零缩放节点 / 权重和不为 1 / POSITION 缺 min/max。

用法：python3 make_samples.py   （在本目录输出两个 .glb）
"""
import json
import struct
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent


# ---------------------------------------------------------------- PNG
def png_bytes(rgb: np.ndarray) -> bytes:
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def checker(size=128, cells=8):
    y, x = np.mgrid[0:size, 0:size]
    on = ((x * cells // size) + (y * cells // size)) % 2 == 0
    img = np.where(on[..., None], [230, 72, 15], [240, 233, 220])
    return png_bytes(img)


# ---------------------------------------------------------------- 几何
def column(segments=8, half=0.25, height=2.0):
    pos, nrm, uv, idx = [], [], [], []
    sides = [((1, 0, 0), (0, 0, -1)), ((0, 0, 1), (1, 0, 0)),
             ((-1, 0, 0), (0, 0, 1)), ((0, 0, -1), (-1, 0, 0))]
    for s, (n, t) in enumerate(sides):
        n, t = np.array(n, float), np.array(t, float)
        base = len(pos)
        for j in range(segments + 1):
            y = height * j / segments
            for i in (0, 1):
                p = n * half + t * (half if i else -half)
                pos.append([p[0], y, p[2]])
                nrm.append(n.tolist())
                uv.append([(s + i) / 4, 1 - j / segments])
        for j in range(segments):
            a, b = base + j * 2, base + j * 2 + 1
            c, d = a + 2, b + 2
            idx += [a, b, d, a, d, c]
    for y, ny in ((0.0, -1), (height, 1)):  # 顶 / 底
        base = len(pos)
        for cx, cz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pos.append([cx * half, y, cz * half])
            nrm.append([0, ny, 0])
            uv.append([(cx + 1) / 2, (cz + 1) / 2])
        quad = [0, 2, 1, 0, 3, 2] if ny > 0 else [0, 1, 2, 0, 2, 3]
        idx += [base + q for q in quad]
    pos = np.array(pos, np.float32)
    w1 = np.clip((pos[:, 1] - 0.6) / 0.8, 0, 1)
    weights = np.stack([1 - w1, w1, np.zeros_like(w1), np.zeros_like(w1)], 1).astype(np.float32)
    joints = np.tile(np.array([0, 1, 0, 0], np.uint8), (len(pos), 1))
    return (pos, np.array(nrm, np.float32), np.array(uv, np.float32),
            np.array(idx, np.uint16), joints, weights)


def quat_z(deg):
    r = np.radians(deg) / 2
    return [0, 0, float(np.sin(r)), float(np.cos(r))]


# ---------------------------------------------------------------- GLB 写入
class Builder:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors = [], []

    def view(self, data: bytes, target=None):
        while len(self.bin) % 4:
            self.bin += b"\x00"
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, arr, ctype, typ, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        count = arr.shape[0]
        a = {"bufferView": self.view(arr.tobytes(), target), "componentType": ctype,
             "count": count, "type": typ}
        if normalized:
            a["normalized"] = True
        if minmax:
            flat = arr.reshape(count, -1)
            a["min"] = flat.min(0).tolist()
            a["max"] = flat.max(0).tolist()
        self.accessors.append(a)
        return len(self.accessors) - 1


def write_glb(path, gltf, binary):
    js = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary = bytes(binary) + b"\x00" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


def build(broken: bool):
    pos, nrm, uv, idx, joints, weights = column()
    b = Builder()
    if broken:
        nrm = nrm * 1.7                      # 法线未归一
        idx = idx.copy(); idx[5] = 9999      # 索引越界
        weights = weights.copy(); weights[:10, 0] = 0.3   # 权重和 ≠ 1

    attrs = {
        "POSITION": b.accessor(pos, 5126, "VEC3", 34962, minmax=not broken),
        "NORMAL": b.accessor(nrm, 5126, "VEC3", 34962),
        "TEXCOORD_0": b.accessor(uv, 5126, "VEC2", 34962),
        "JOINTS_0": b.accessor(joints, 5121, "VEC4", 34962),
        "WEIGHTS_0": b.accessor(weights, 5126, "VEC4", 34962),
    }
    if broken:   # 黑色顶点色 × 贴图 → 整块发黑
        attrs["COLOR_0"] = b.accessor(np.tile([0.02, 0.02, 0.02, 1], (len(pos), 1)).astype(np.float32),
                                      5126, "VEC4", 34962)
    indices = b.accessor(idx, 5123, "SCALAR", 34963)

    # bindposes：joint0 在原点，joint1 在 y=1 → inverse 平移 (0,-1,0)
    ibm = np.stack([np.eye(4), np.eye(4)]).astype(np.float32)
    ibm[1][1, 3] = -1.0
    # glTF 要求列主序；正确写法是转置后按行展开。broken 版直接按行主序写（坑 1）
    ibm_flat = ibm if broken else ibm.transpose(0, 2, 1)
    ibm_acc = b.accessor(ibm_flat.reshape(2, 16), 5126, "MAT4")

    times = np.array([0, 1, 2], np.float32)
    rots = np.array([quat_z(-25), quat_z(25), quat_z(-25)], np.float32)
    t_acc = b.accessor(times, 5126, "SCALAR", minmax=True)
    r_acc = b.accessor(rots, 5126, "VEC4")

    img_view = b.view(checker())

    nodes = [
        {"name": "Column", "mesh": 0, "skin": 0},
        {"name": "Bone_Root", "children": [2]},
        {"name": "Bone_Tip", "translation": [0, 1, 0]},
    ]
    scene_nodes = [0, 1]
    if broken:
        nodes.append({"name": "HiddenProp", "scale": [0, 0, 0], "mesh": 0})
        scene_nodes.append(3)
    gltf = {
        "asset": {"version": "2.0", "generator": "bowen glb-inspector sample"},
        "scene": 0,
        "scenes": [{"name": "Sample", "nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": [{"name": "ColumnMesh", "primitives": [{"attributes": attrs, "indices": indices, "material": 0}]}],
        "skins": [{"name": "Rig", "joints": [1, 2], "inverseBindMatrices": ibm_acc, "skeleton": 1}],
        "materials": [{"name": "M_Checker",
                       "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                "metallicFactor": 0, "roughnessFactor": 0.7}}],
        "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987}],
        "images": [{"name": "checker", "mimeType": "image/png", "bufferView": img_view}],
        "animations": [{"name": "Sway",
                        "samplers": [{"input": t_acc, "output": r_acc, "interpolation": "LINEAR"}],
                        "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}]}],
    }
    if broken:
        # 零缩放节点挂一个无蒙皮的小方块 mesh（复用位置/法线，不带 JOINTS）
        gltf["meshes"].append({"name": "PropMesh", "primitives": [{
            "attributes": {"POSITION": attrs["POSITION"], "NORMAL": attrs["NORMAL"],
                           "TEXCOORD_0": attrs["TEXCOORD_0"]},
            "indices": indices, "material": 0}]})
        nodes[3]["mesh"] = 1
    gltf["bufferViews"] = b.views
    gltf["accessors"] = b.accessors
    gltf["buffers"] = [{"byteLength": len(b.bin) + (-len(b.bin) % 4)}]
    return gltf, b.bin


if __name__ == "__main__":
    for name, broken in (("healthy.glb", False), ("broken.glb", True)):
        g, binary = build(broken)
        write_glb(OUT / name, g, binary)
        print("wrote", OUT / name, (OUT / name).stat().st_size, "bytes")
