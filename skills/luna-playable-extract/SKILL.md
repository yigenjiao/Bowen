\---  
name: luna-playable-extract  
title: "luna-playable-extract"  
summary: "从 Luna / DataEye 试玩广告 HTML 中提取模型、贴图，并在可行时绑定材质、还原场景摆放、导出 Blender 可用 GLB/OBJ。"  
description: "This skill should be used when the user provides a Luna/DataEye/playable ad HTML file and wants to extract 3D models, all scene textures, bind materials, reconstruct scene placement, or export assets for Blender/Unity. It captures the proven workflow for Brotli/base64/base122 resource extraction, mesh buffer decoding, material-texture mapping, static scene reconstruction, and GLB packaging."  
read_when:  
  \- 用户给了一个试玩广告 / playable ad 的 HTML 文件，想提取模型或贴图  
  \- 文件是 Luna Labs / DataEye / 广告平台导出的自包含 HTML 或 live HTML  
  \- 用户想在 Blender / Unity 里复用试玩里的 3D 资源  
  \- 用户要求绑定材质贴图、还原场景位置、导出 GLB/GLTF/OBJ  
agent_created: true  
\---

# Luna / DataEye 试玩广告资源提取工作流

## 目标

从 Luna / DataEye playable HTML 中尽可能离线提取：

- 全部场景贴图；
- mesh 模型，先 OBJ 兜底；
- 在存在 `scenes` / `prefabs` / `materials` / `textures` 清单时，绑定贴图并还原静态场景层级与摆放；
- 最终优先交付 Blender 可直接导入的单文件 `scene_textured.glb`，同时可保留 `scene_textured.gltf`、`.bin`、`textures/`、OBJ 与 manifest 作为排查资料。

## 先做判断，避免走错路

1. 区分本地预览壳和完整 playable：
   - 本地 HTML 可能只是预览壳，只有 UI 或编辑器样式资源。
   - 若能从文件名/hash 推断在线地址，尝试下载完整 live HTML，例如 `https://overseas-material.dataeye.com/<id>/<hash>.html`。
   - 若用户给的是 `*_live.html` 或 `extracted_images/page.html`，通常已经包含完整资源。
2. 不要直接断言“Luna 私有 bundle 不可解析”。已验证多种包可通过 `*_str.dat` 的 `meshes` 清单 + `ArrayBuffer` 偏移离线导出 OBJ/GLB。
3. 优先走离线解析路线。无头浏览器抓 GLB 仅作最后兜底，因为裸 Chromium 常缺广告 SDK / Luna runtime 所需 app systems，容易出现空场景或运行时异常。
4. **先认包型再选分支**（三条主线都有实证章节，别混用解码器）：

   | 判据（grep 原文即可） | 包型 | 去读哪 |
   |---|---|---|
   | `super-html` + `decodeBase122` + `inflateRaw` + `window.__res` + `window.__zip` | Cocos3「polar / Super HTML」单文件包 | 本文「White Bear Studio / polar」节（含九阶段完整流程 + 代码骨架） |
   | `__PLAYABLETOOLS_FORMAT__="cocos3-assetmap"` + `unbrotli` + `base64` | Cocos3 assetmap（PlayCools 变体） | 本文「PlayCools 变体」节 |
   | `*_str.dat` / `meshes` 清单 / Unity 风格 bundle | Luna / Unity playable | 本文主体 + 「Unity / Luna 包补充流程」节 |

   共同骨架永远是：**解包 → 定位场景清单 → 运行时 dump → 顶点按 stride 解析 → 材质选对 pass → 导 GLB → 结构校验 + AABB 对账 + 渲染目检**。任何一类包都别跳过最后三步。

## 工作目录与交付结构

为每个输入 HTML 建独立输出目录，命名建议：

```text
extract_<date_or_hash>_<short_name>/
  raw/                       # 原始 HTML、下载版 HTML、解压块
  extracted_assets/           # 图片、buffer、清单、OBJ
    scene_textures/
    models_obj/
    manifests/
  scene_reconstructed_textured/
    scene_textured.glb         # 首选交付
    scene_textured.gltf
    scene_textured.bin
    textures/
    README.txt
  <name>_extracted_assets.zip
  <name>_scene_reconstructed_textured.zip
```

最终向用户展示：

- 首选：`scene_textured.glb`；
- 辅助：完整 zip；
- 如果只能导 OBJ：`models_obj/all_meshes_combined.obj` + 贴图 zip。

## 资源识别

在 HTML 中搜索这些特征：

- `decompressArrayBuffer("...")` / `decompressString("...")`：Luna 内联资源块，通常是 Brotli 压缩后的 base64 或 base122 字符串。
- `<img id="assets/..." data-src122="...">`：新 live 包的图片入口，`data-src122` 是 Luna base122 编码的原始图片字节，通常不再 Brotli。
- `data:image/png;base64,...`、`iVBORw0KGgo`、`/9j/`：旧包直接内联 PNG/JPG。
- JSON 顶层 key：`meshes`、`textures`、`materials`、`prefabs`、`scenes`、`animations`。

## base122 解码要点

Luna base122 不是标准 base64。使用以下算法还原 bytes，再按魔数判断是否需要 Brotli：

```python
reserved = [0, 10, 13, 34, 38, 92]

def base122_to_bytes(s):
    bitbuf = 0
    bitcnt = 0
    out = bytearray()

    def emit(v):
        nonlocal bitbuf, bitcnt, out
        v <<= 1
        bitbuf |= v >> bitcnt
        bitcnt += 7
        if bitcnt >= 8:
            out.append(bitbuf & 255)
            bitcnt -= 8
            bitbuf = (v << (7 - bitcnt)) & 255

    for ch in s:
        code = ord(ch)
        if code > 127:
            marker = (code >> 8) & 7
            if marker != 7:
                emit(reserved[marker])
            emit(code & 127)
        else:
            emit(code)
    return bytes(out)
```

处理顺序：

1. HTML unescape 字符串；
2. 若是 base122，调用 `base122_to_bytes`；
3. 若解出的 bytes 是 PNG/JPG/WebP 魔数，直接落盘；
4. 若不是图片，尝试 `brotli.decompress`；
5. 对 `decompressString` 产物，按 UTF-8 / JSON 解析；对 `decompressArrayBuffer` 产物，作为二进制 buffer 保存。

## Brotli / base64 解包

对 `decompressArrayBuffer("B64")` / `decompressString("B64")`：

1. `base64.b64decode`；
2. `brotli.decompress`；
3. 输出分类：
   - `*_bin.dat`：大二进制资源 buffer，常含顶点和索引；
   - `*_str.dat`：JSON 清单、反序列化数据、材质/场景结构。
4. 遍历所有 `*_str.dat`：只要出现 `meshes`，就继续模型导出；出现 `scenes/prefabs/materials/textures`，继续 GLB 场景还原。

## 贴图提取

必须覆盖三类来源：

1. base64 data URI：
   - PNG 魔数：`\x89PNG\r\n\x1a\n`；
   - JPG 魔数：`\xff\xd8\xff`；
   - WebP 魔数：`RIFF....WEBP`。
2. `<img data-src122="...">`：base122 解码后按图片魔数落盘。
3. Luna 资源 JSON 中的 `textures` 引用：用 texture id / path / asset id 回连已落盘图片。

贴图去重：按内容 hash 去重，但保留原始 id/path 到文件名的映射，后续材质绑定需要用。

## Mesh 清单字段布局

字段布局不固定，必须自适应，不要写死一种格式。

### 常见旧布局

- `mesh.data[0]` = name
- `mesh.data[3]` = useUInt32IndexFormat / index flag
- `mesh.data[4]` = vertexCount
- `mesh.data[5]` = AABB
- `mesh.data[6]` = streams
- `mesh.data[7]` = `[vertexOffset, vertexBytes]`
- `mesh.data[8]` = subMeshes / index ranges

### 常见新 live 布局

- `mesh.data[0]` = name
- `mesh.data[2]` = indexFormatOrFlags
- `mesh.data[3]` = vertexCount
- `mesh.data[4]` = AABB
- `mesh.data[5]` = streams
- `mesh.data[6]` = `[vertexOffset, vertexBytes]`
- `mesh.data[7]` = subMeshes / index ranges
- `mesh.data[8]` = bindposes / skin data，可能很长

### 解析策略

1. 在候选字段中寻找 `vertexCount`、`streams`、vertex buffer ref、subMeshes。
2. 顶点常见为 little-endian half-float（Python `struct.unpack('<e')`）。
3. stream 中至少提取 position、normal、uv0；tangent 可选。
4. index 先用 `uint16` 读；若 index 越界或 flag 表示 32-bit，再改 `uint32`。
5. submesh 结构要兼容：`[off, len]`、`[[off, len]]`、`[[[off, len]]]`。
6. OBJ 作为保底交付：每个 mesh 单独 OBJ，再生成 `all_meshes_combined.obj`。

## 材质与贴图绑定

当存在 `materials` / `textures`：

1. 建立 `textures_by_id`、`materials_by_id`、`mesh_by_id`。
2. 解析材质贴图槽，优先级：
   - Base color：`_BaseMap`、`_MainTex`、`_BaseTex`；
   - Normal：`_BumpMap`、`_NormalA`、`_NormalB`；
   - Emission：`_EmissionMap`。
3. 贴图槽 type code 不固定，不要依赖固定数字。已见过：
   - `['_MainTex', 11, textureId]`
   - `['_MainTex', 43, textureId]`
4. 以 `textureId in textures_by_id` 作为最终校验。
5. GLB 中优先内嵌图片，避免外部贴图路径丢失。

## 场景 / Prefab / Component 还原

当存在 `scenes` / `prefabs`：

1. 解析节点层级，恢复 Transform 的局部 TRS：translation、rotation quaternion、scale。
2. 建立 GameObject / Entity 到 Component 的关系。
3. 识别 MeshFilter / MeshRenderer / SkinnedMeshRenderer。组件编号因包而异，必须用引用关系判断。

常见编号参考：

### live 新包示例

- `type 19` = Transform，data 常为 `[tx,ty,tz,sx,sy,sz,qx,qy,qz,qw]`
- `type 29` = MeshFilter，mesh ref 常见 `[30, meshId]`
- `type 31` = MeshRenderer，material ref 常见 `[9, materialId]` 或 sharedMaterials 列表
- `type 24` = SkinnedMeshRenderer，可按静态 mesh 导出

### 旧/UnityAds 包示例

- `type 0` = Transform
- `type 9` = MeshFilter，mesh ref 常见 `[10, meshId]`
- `type 11` = MeshRenderer，material ref 常见 `[12, materialId]`
- `type 24` = SkinnedMeshRenderer，mesh ref 常见 `[10, meshId]`

实操识别法：

1. 遍历所有 component 的整数引用；
2. 与 `meshes[].id` 求交集，引用 mesh 最多的组件类型通常是 MeshFilter 或 SkinnedMeshRenderer；
3. 与 `materials[].id` 求交集，引用 material 最多的组件类型通常是 Renderer；
4. 与 GameObject / Transform 层级关系交叉验证；
5. SkinnedMeshRenderer 先静态导出 mesh，注明不含骨骼动画/蒙皮变形。

## glTF / GLB 导出标准

优先导出 glTF 2.0，再封装 GLB：

1. buffers：合并 vertex/index 数据到 `scene_textured.bin`；
2. bufferViews/accessors：为 position、normal、uv、indices 建 accessors；
3. meshes：按 submesh 分 primitive，挂 material；
4. nodes：恢复层级和局部 TRS；
5. images/textures/materials：绑定并内嵌贴图；
6. scene：写默认 scene；
7. GLB：把 JSON chunk + BIN chunk 封装为单文件，图片可走 data URI 或 bufferView 内嵌。

交付前校验：

- GLB 文件能被解析（JSON chunk、BIN chunk 长度正确）；
- 无外部贴图缺失；
- 统计节点数、mesh 实例数、glTF mesh 数、材质数、已绑定贴图数、GLB 大小；
- README 写清限制。

## 已验证产出规格

完成后向用户汇报这些指标：

- 解包资源块数量；
- 源 Mesh 数；
- 导出 OBJ 数；
- 顶点数 / 面数；
- 场景贴图数量；
- 场景节点数；
- Mesh 实例数；
- 材质数；
- 成功绑定并内嵌贴图数量；
- GLB 文件路径和大小；
- 已知限制。

## 已知限制与措辞

必须说明：

- 离线还原的是静态场景，不保证还原脚本运行时显隐、物理、粒子、UI、动画状态。
- SkinnedMeshRenderer 可静态导出，但不包含骨骼动画和蒙皮动态。
- OBJ 不保留完整层级与材质绑定；GLB 才是 Blender 优先交付。
- 若 HTML 只有壳、没有 `meshes` 或可用 buffer，无法凭空还原模型；此时只能交付已提取贴图/资源包，并建议获取完整 live HTML 或 Unity 源工程。

## Unity / Luna 包补充流程（Luna 转 Unity 引擎 playable）

部分 Luna/DataEye playable 实际是把 Unity 场景序列化到 Luna runtime。资源块、组件类型与 Cocos3 完全不同。已验证工作流（2026-08-31 实践）：

### 1. 识别 Unity / Luna 包

- HTML 中无 `cc.director` / `assetManager` 等 Cocos 标志；
- 出现 `decompressArrayBuffer("B64", false/true)`（注意带第二参数 `isBase122`）和 `decompressString("B64", true)`；
- 解压后得到 Luna 引擎 JS、`unknown_21.json` 主清单（含 `meshes/materials/prefabs/scenes/textures`）、`unknown_22.bin` 二进制 buffer；
- 图片资源可能以 `<img data-b122="...">` 形式存在，key 形如 `assets/bundles/-1/<texId>.png`。

### 2. 组件类型识别（Unity 风格）

从引擎 JS 中提取的类型表典型值：

- `type 0` = `RectTransform`（UI 对象）；
- `type 22` = `Transform`；
- `type 25` = `Camera`；
- `type 27` = `Texture2D`；
- `type 33` = `SkinnedMeshRenderer`；
- `type 34` = `Mesh`；
- `type 35` = `Material`；
- `type 36` = `MeshFilter`；
- `type 37` = `MeshRenderer`；
- `type 40` = `ParticleSystem`；
- `type 41` = `ParticleSystemRenderer`；
- `type 45` = `MeshCollider`。

引用对格式 `[typeId, assetId]`，例如：

- `MeshFilter.data = [34, meshId]`；
- `MeshRenderer.sharedMaterial = [35, matId]`，sharedMaterials 为 `[35, id, 35, id, ...]` 扁平列表。

### 3. Mesh 数据布局

`mesh.data` 数组约定（索引固定）：

- `data[0]` = name；
- `data[1]` = `halfPrecision` (bool)；
- `data[2]` = `useSimplification`；
- `data[3]` = `useUInt32IndexFormat` (0/1)；
- `data[4]` = vertexCount；
- `data[5]` = AABB `[cx,cy,cz,ex,ey,ez]`；
- `data[6]` = streams（10 个 bool），语义顺序：  
  `POSITION(3), NORMAL(3), TANGENT(4), BLENDWEIGHT(4), BLENDINDICES(4), COLOR(4), TEXCOORD0(2), TEXCOORD1(2), TEXCOORD2(2), TEXCOORD3(2)`；
- `data[7]` = `[vertexOffset, vertexBytes]`（在 `unknown_22.bin` 中的字节偏移与长度）；
- `data[8]` = subMeshes，每项 `[triangles=[byteOffset, byteSize]]`；
- `data[9]` = bindposes；
- `data[10]` = blendShapes（静态导出可忽略）。

顶点类型：stream 内声明为 `TYPE_FLOAT32`；`halfPrecision=true` 时所有分量按 half float（2 字节）存储。Python 用 `struct.unpack('<e')` 读取。

索引：按 `useUInt32IndexFormat` 选择 `uint16` 或 `uint32`。

### 4. 场景 Transform 池（关键）

Unity 场景对象极多，绝大多数对象没有显式 Transform/RectTransform 组件，而是从一个 transform 池中按 **后序 DFS** 顺序分配。

- 池大小 = `scene.transform_ids.length`；
- 池 TRS 存在 `scene.local_positions` / `scene.local_rotations` / `scene.scales`，长度分别为 `poolCount*3`、`poolCount*4`、`poolCount*3`；
- 分配规则：递归遍历 `scene.objects` 树，先处理 children，再处理自身；若对象没有显式 `type 0` / `type 22` 组件，则消耗池中下一个 slot，TRS 取 `slot` 对应切片；
- UI 对象通常带 `type 0 RectTransform`，直接使用其组件数据，不消耗池。

显式 Transform 数据：

- `type 22`：`data = [px,py,pz, sx,sy,sz, qx,qy,qz,qw]`（10 floats）；
- `type 0 RectTransform`：DTO `{pivot:0, anchorMin:2, anchorMax:4, sizeDelta:6, anchoredPosition3D:8, rotation:11, scale:15}`，共 18 个值。静态导出时可直接用 `anchoredPosition3D` 作位置、`rotation` 作 Z 轴旋转（弧度）、`scale` 三轴缩放。

父链世界矩阵按行主序复合后，转置为 glTF 的 column-major `node.matrix`。

### 5. UV 方向

Unity 纹理坐标 `(0,0)` 在左下角，glTF `(0,0)` 在左上角，因此必须翻转 V：

```
u' = u * sx + ox
v' = 1 - (v * sy + oy)
```

其中 `[sx,sy,ox,oy]` 来自材质的 `_MainTex_ST`。

### 6. 材质与贴图

材质 `data` 数组约定：

- `data[6]` = colors，例如 `[['_Color',r,g,b,a], ['_Tint',r,g,b,a]]`；
- `data[7]` = ST，例如 `[['_MainTex_ST',sx,sy,ox,oy]]`；
- `data[8]` = textures，例如 `[['_MainTex', 27, texId], ['_MaskTex', 27, texId]]`；
- `data[9]` = shader keywords，如 `_ALPHAPREMULTIPLY_ON` / `_ALPHABLEND_ON` 表示透明混合。

glTF 材质：

- baseColorFactor 取 `_Color` 或 `_Tint` 第一个；
- baseColorTexture 取 `_MainTex` 的 `texId`，通过 `img_id_map.json['assets/bundles/-1/<texId>.png']` 找到实际 PNG 文件；
- alphaMode 在关键字启用或 `baseColorFactor[3] < 1` 时设为 `BLEND`；
- 图片内嵌到 GLB bufferView。

### 7. 渲染器导出范围

为“不丢模型”，以下组件全部导出：

- `MeshFilter(36) + MeshRenderer(37)` → 普通 mesh；
- `SkinnedMeshRenderer(33)` → 静态导出（不带骨骼）；
- `ParticleSystemRenderer(41)`：
  - 若 `data[0..1] = [34, meshId]`，按 mesh 粒子导出；
  - 若 mesh 为 null（Billboard / Stretch 粒子），生成一个 billboard quad，把材质的 VFX 贴图保留下来；
- `MeshCollider(45)` → 导出 mesh，可附加 `_collider` 后缀避免与可见模型混淆。


### 8. Prefab 处理

Unity Prefab（Worker/Prisoner/Target 等）对象带完整显式 Transform 层级和 SkinnedMeshRenderer。它们通常是运行时脚本实例化的模板。若其 mesh id 已全部出现在 scene 中，则无需重复导出；若存在 scene 未引用的 mesh，可作为额外根节点补回。

### 9. 验证要点

- 池 slot 数量 + 显式 Transform 数量 = 场景对象总数；
- 解析 GLB JSON/BIN chunk，检查 bufferViews 不越界；
- 检查 POSITION / UV accessor 无 NaN；
- 计算世界空间 AABB，确认范围合理；
- 用 three.js + Playwright 渲染并截图，与原始网页运行效果对比。

### 10. 包间差异速查（2026-09-11 Township 实战验证）

组件类型编号**每个包都不同**，绝不能照抄上一个包的编号。上手先做两件事：

1. 统计 scene 组件类型分布（Counter by type），把 `data=[refType, id]` 且 id 命中 mesh 清单的组件识别为 MeshFilter/SMR/PSR；
2. 用材质 id 命中分析识别 renderer 类型。

已见过的两套编号：

| 组件 | toilet_click(08-31) | Township(09-11) |
|---|---|---|
| MeshFilter | 36 | 3 |
| MeshRenderer | 37 | 5 |
| SkinnedMeshRenderer | 33 | 40 |
| ParticleSystemRenderer | 41 | 43 |
| MeshCollider | 45 | 45 |
| Transform 显式 | 22 | （无，全走池）|
| RectTransform | 0 | 89（不占池）|

Township 包的其他差异：

- **Transform 池有显式映射表**：`scene.transform_ids`（4142 项）存的是 Transform 组件 id，与对象 id 无固定算术偏移（部分 +2、部分 +4）。可靠做法：后序 DFS 遍历树（跳过 RectTransform 对象），与 `transform_ids` 按**位置**对齐（顺序已验证完全一致），直接 zip 出 slot。
- Mesh 索引支持 uint32（`data[3]=1`，本包 70/202 个 mesh 是 u32）；submesh 长度按 4 字节除。
- 材质贴图槽 type code 是 8/None（非 27）；贴图 img 标签扩展名有 `.jpeg`（61 张），get_image 要试 `('png','jpeg','jpg','webp')` 全部组合。
- **顶点色材质**（M_VertexPaint，柏树/花丛）：streams 含 COLOR(5)，导出 COLOR_0(FLOAT VEC4)；材质无 baseColorTexture 时置 `vertexColors:true`，否则渲染一片白。
- **UV V 翻转是必须的**（Unity v=0 在底、glTF 在顶）：平铺贴图（草地/沙地）看不出没翻转，**图集贴图（树叶/树干混合图集）会整树采错颜色区域**——树冠变枯色是典型症状。非恒等 `_MainTex_ST`（6 个材质）用 KHR_texture_transform 编码：scale=[sx,sy]，offset=[ox, 1-sy-oy]。
- UV 修复的验证方法：按顶点高度分组（树冠/树干）分别采样贴图颜色，比整 mesh 平均色更能定位问题。
- SMR（如蛋机里的鸡）可能藏在场景任意深度的巢位节点下，漏导的表现是"场景里有鸡窝没鸡"。

## Cocos Creator 3.x 包补充流程

部分 DataEye  playable 使用 Cocos Creator 3.8.5+，资源以 assetmap 形式打包（非 Luna 私有格式）。处理流程如下：

### 1. 识别 Cocos3 assetmap

- HTML 中出现 `assetManager`、`loadBundle`、`AssetManager._assets`、`cc.pipeline` 等 Cocos 标志；
- 资源 JSON 符合 Cocos3 序列化格式：`[version, local_uuids[], strings[], types[], instances[], data[]]`；
- 解压后的资源文件包含 `.bin`、`.jpg/.png/.webp`、JSON config；
- 网格记录结构形如 `[type, '.bin', hash, struct]`，`type` 不固定，不要只扫描固定 type code。

### 2. UUID 解码

Cocos3 使用压缩 UUID：前 2 字符是十六进制直接字符，后 20 字符是 base64 编码的 15 字节。

```python
import base64, uuid

def decode_cocos_uuid(s):
    head = s[:2]
    tail_b64 = s[2:] + '=='
    tail = base64.b64decode(tail_b64)
    return uuid.UUID(head + tail.hex()).hex
```

运行时 asset map 中的 Mesh UUID 常带 subresource，例如 `1263d74c-8167-4928-91a6-4e2672411f47@fc873`；去掉 `@sub` 后就是对应的 `.bin` 文件 UUID。

### 3. 优先提取运行时场景图

Cocos3 的序列化 scene/prefab JSON 往往不能完整表达运行时实例化结果。推荐用无头浏览器执行一段 JS，把真实运行时场景树 dump 出来：

- 在页面 `cc.director.getScene()` 上递归遍历节点；
- 记录每个节点的 `name`、`uuid`、active、`_lpos`、`_lrot`、`_lscale`、parent 索引；
- 记录每个 `MeshRenderer` 的 `_meshAsset._uuid`（注意是 `base@subresource` 形式）、`_materials` 材质 UUID、`_enabled`、 visibility；
- 保存为 `scene_graph_full.json`。

这个运行时场景图是后续还原世界坐标的权威来源。

### 4. 世界坐标重建

Cocos3 场景节点存储的 `worldMatrix` 在 dump 时通常被截断（例如只有 8 个值，其余为 null），不能直接作为最终矩阵。必须按父链重算：

```python
def mat4_to_trs(M):
    # M 是 4x4 numpy 列主序世界矩阵
    # 返回 (t, r_quaternion_xyzw, s) 或 None（零缩放）
    ...

def compute_world(node, nodes):
    M = np.eye(4)
    chain = []
    while node is not None:
        chain.append(node); node = nodes[node['parent']] if node['parent'] >= 0 else None
    for n in reversed(chain):
        t = n['lpos']; r = n['lrot']; s = n['lscale']
        M = M @ trs_to_mat(t, r, s)
    return M
```

过滤条件：
- 节点或组件 `active == False` 跳过；
- `MeshRenderer._enabled == False` 跳过；
- 世界缩放 `min(sx, sy, sz) < 1e-4` 视为零缩放，跳过避免导出崩溃。
- glTF 的 `node.matrix` 是**局部**矩阵，不能直接写世界矩阵（会层层复合）。优先用节点 TRS；若必须用矩阵，则 `local = inv(parent_world) × own_world`（4x4 列主序）。
- Cocos Mat4 元素访问不固定：属性可能是 `m00..m15`（两位数补零）也可能是 `.m` 数组。访问器要兼容：`getel(m, i) = m['m' + String(i).padStart(2,'0')]`（找不到再回退 `m[i]`）。

### 4b. 零缩放 ≠ 丢弃：可能是运行时隐藏态（2026-09-04 实战验证）

游戏常用 `lscale = [0,0,0]` 来隐藏节点（例：羊剪毛后把 `wool` 节点缩放清零）。抓帧只捕捉到一个瞬间状态，若导出器把零缩放子树直接丢弃，就会"少模型"。要求全状态导出时：**把零缩放按单位缩放 (1,1,1) 还原**再算世界矩阵，而不是跳过/标记 dead。羊有毛/无毛两种状态即由此找回。

### 4c. 运行时 dump 的 Playwright 陷阱（2026-09-04 实战验证）

- **`page.waitForFunction` 默认用 rAF 轮询**——headless 后台页 rAF 不触发，会永远超时（即使场景已就绪）。改用 `waitForTimeout(2000)` + `page.evaluate` 定时轮询（判据用场景节点数 >1000，别用 `cc.MeshRenderer` 类名——裁剪版引擎里可能不存在该全局类）。
- 旧版 Playwright 的 `waitForFunction(fn, arg, options)` 签名：options 传错位置会静默变成默认 30s 超时。报错里 "Timeout 30000ms" 与自己设的值不符时先查签名。
- 引擎 Mat4 存储可能是 `m[16]` 数组而不是 `m00..m15` 属性，dump 矩阵的序列化函数要两者兼容，取不到的分量用单位阵补齐并计数（否则整个 dump 静默变 0 条记录）。
- 场景完全加载可能需要 20s+（LoadScene 完成后还要等 prefab 实例化），轮询上限放宽到 60s。

### 4d. 运行时才生成/穿上的模型（mesh=null 的找回方法，2026-09-04 实战验证）

症状：SMR（如顾客的 `SSD_衣服`）在场景里 mesh=null——毛衣是穿上瞬间才赋值，羊毛球是动态生成，抓帧时不存在。找回方法：

1. 全量 dump 所有 MeshRenderer/SkinnedMeshRenderer（含 inactive），确认目标 SMR 的 mesh 确实为 null；
2. **深扫 `cc.assetManager.assets`**：对每个已加载资产（Prefab 为主）递归遍历对象树（防环、深度 8），收集 mesh uuid 与材质名的**共现对**——prefab 里 mesh 和 material 是成对引用的；
3. 按材质名（如「羊毛」「毛衣」「顾客穿毛衣」）反查目标 mesh uuid，确认它已在 mesh 缓存（dump_runtime.js 抓的是全部已加载 Mesh 资产）；
4. 导出时加一个 `__EXTRA_ASSETS` 根节点组，把找回的 mesh + 配对材质按地面高度摆成展示排（命名带中文名便于用户在 Blender 里识别）。

### 5. Mesh 与 .bin 匹配

- 遍历 assetmap 中所有 `[type, '.bin', hash, struct]` 记录，建立 `(uuid, hash) -> struct` 和 `uuid -> .bin_path` 映射；
- MeshRenderer 的 mesh UUID 形如 `base@subresource`：`base` 对应 `.bin` 文件，`subresource` 是 struct 索引；
- 同一个几何体文件里可能含多个 submesh struct，用 `hash` 或 struct 内 `primitives` 数量辅助定位；
- 解析 struct 中的顶点格式、streams、索引格式（uint16/uint32），输出 glTF accessors。

### 5b. 交错顶点缓冲必须按 stride 读取（2026-09 实战验证）

Cocos3 mesh 顶点在 `.bin` 中默认是**交错布局**（interleaved），例如每顶点依次 `position|normal|texCoord|tangent`。属性字节偏移不能按“连续打包”累加——这是网格错位/噪声几何最常见的根因。

- stride 直接取自 mesh struct 的 `vertexBundles[].view`；
- 单个属性偏移 = 按该 bundle 内声明顺序把前面各 format 的字节数依次累加；
- format→字节参考：`32=12B(f32x3)`、`21=8B(f32x2)`、`44=16B(f32x4)`、`42=8B(u16x4)`；skin 属性 `a_joints/a_weights` 与 position 等在同一个交错块里按序排布；
- 读取器：`read_attr_strided(raw, byte_off, ncomp, vcount, stride)`，逐顶点取 `raw[byte_off + i*stride : byte_off + i*stride + ncomp*字节]`；
- 索引区不交错，按 uint16/uint32 直接读。

### 6. 材质贴图绑定（Cocos3 主流程）

Cocos3 材质贴图通常不在 pass 的 `_textureSet` 里，而在 `_props` 数组中，常见链为：

```
Material._props -> mainTexture (Texture2D uuid+"@6c48a")
Texture2D -> _mipmaps[0] -> ImageAsset uuid
ImageAsset -> native 文件 ".jpg" / ".png" / ".webp"
```

建立映射：
- `material_uuid -> texture2d_uuid -> imageasset_uuid -> image_native_file`；
- 如果 mainTexture 在 `_props` 中没有名字，按 Texture2D 槽位顺序绑定到 glTF 的 `baseColorTexture`；
- 图片以内嵌 data URI 方式写入 GLB，mime type 从文件扩展名推断（png/jpeg/webp）。
- Cocos3 “标准”材质默认无金属度贴图：glTF 统一写 `metallicFactor: 0.0`、`roughnessFactor: 0.9`，否则 three.js/Blender 预览一片黑（metalness=1 且无 envMap 时会全黑）。
- 校验渲染时需对加载后的全部 mesh 强制 `material.side = THREE.DoubleSide`——Cocos3 单面材质经绕序/朝向差异可能整片消失。

### 6b. SkinnedMeshRenderer 运行时蒙皮烘焙（2026-09 实战验证）

序列化 JSON 不足以离线还原骨骼动画，但可以把运行时**当前姿态**烘焙进顶点，让角色/绵羊等蒙皮网格以真实 pose 出现在 GLB：

- runtime dump 把每条 SkinnedMeshRenderer 存成 **array**（不是 dict）——多个实例共享同一 mesh 时按条保留，否则同名节点互相覆盖、实例丢失；
- 每条记录抓：`smrPath`、mesh uuid、`_bindposes`、joints 的 `/` 路径、`nodePos`（该 SMR 节点世界坐标，用于事后与离线场景树配对）、SMR 世界矩阵；
- 关节世界矩阵在 dump 时实时读各 joint node 的 `worldMatrix`（用上面的 `getel` 兼容访问，不要假设属性叫 `m12` 这类简写，joint 矩阵 m00..m15 才有效）；
- 烘焙到 SMR 局部空间：`v' = inv(SMR_W) × Σ_k w_k × (JointWorld_k × BindPose_k) × v`，因此导出的 SMR 节点 glTF matrix 置单位阵即可；
- 与离线场景树的实例/关节匹配：`smrPath|mesh` + 世界坐标距离最近者配对；姿态结果应与运行时截图一致（实战：21 条 skin 记录 → 8 个 skinned glTF mesh，人形与绵羊身体均正确）；
- 烘焙路径与静态网格路径分开处理，已烘焙的 SMR 不要再额外复合 invL 矩阵。

### 6c. 蒙皮烘焙的两个坑（2026-09-09 推小火车实战验证）

- **dump 端 Mat4 序列化**：引擎 Mat4 属性是 `m00..m33`（两位数补零），访问器必须用 `m['m' + String(i).padStart(2,'0')]` 再回退 `.m[i]`。漏了 padStart 会拿到 undefined → 静默回退列主序 `.m` → 矩阵转置 → 蒙皮网格碎裂。
- **path2idx 建 SMR 路径索引**：递归入口用 `rec(0, '')`、`full = prefix ? prefix+'/'+nm : nm`，根节点名不能拼两遍（`scene/scene/...` 会导致所有 smrPath 匹配失败 → Chick/Farmer 顶点留在世界空间）。个别实例 joint 路径解析失败（`0/` 开头）时，按同 mesh 最近 `nodePos` 借用成功实例的姿态。

### 6d. Cocos3 assetmap 的 base122 主块与 WebP 内嵌（2026-09-09 实战验证）

- `__PLAYABLETOOLS_FORMAT__ = "cocos3-assetmap"`：`window.unbrotli(base122ToArrayBuffer("..."))` 的字符串里常带 3 万+ 个 `\u003C` 转义，必须先 unescape；解码时 **base122 按 UTF-16 code unit 遍历**（Python `ord()` 逐 code unit，不是 Unicode codepoint），否则 brotli 解不开。
- WebP 贴图在 assetMap 里以 **base64 文本**形式存在，落盘时统一 base64 解码为二进制再按魔数分类；WebP 用 Pillow 转成 PNG 再进 GLB（Blender/three 兼容）。漏了这步 GLB 里图片魔数是 `UklG` 文本，渲染全白。

### 7. 排除 2D UI / FX 遮罩（2026-09-04 修正判定规则）

运行时场景中 2D UI 通常在 `Game2DUI` / `Canvas` 子树下，节点没有 3D MeshRenderer 或 mesh 为空。在 dump 阶段记录 `is3Dnode` / `_layer` 信息，导出时直接排除该子树。

**FX 遮罩判定只按材质名/自身名**（`黑底`/`brush-fade`/`fadeBrush`、自身名含 fade），识别后整棵平移到相机取景外（如 `__FX_far` y+500），只挪位不删除。**不要按祖先节点名含 `part`/`particle` 扫描**——实战教训：滚雪球项目里羊身模型节点恰名 `part_0000`（材质"羊-001"），名字规则把 3 只羊全部误隔离到远处，用户反馈"少了羊"。名字巧合不代表是特效，必须以材质/贴图性质为准。

**inactive 内容默认原位导出**（用户预期"不丢模型"包含抓帧时 `active=false` 的设备/升级建筑/后续关卡物件，如羊毛机罐子、烘干机）。只有两类例外需要挪位/分组：2D UI（屏幕空间坐标会污染世界盒）和全屏黑底遮罩（挡相机）。同一位置叠放多个互斥状态时在 README 里说明按名称筛选即可。

### 8. 验证清单

最终 GLB 导出后必须做：

- 解析 GLB 两个 chunk，确认 JSON/BIN 长度；
- 检查 nodes/meshes/materials/textures/images/accessors/bufferViews 数量；
- 所有节点变换无 NaN/Inf、无接近零缩放；
- 所有材质 `baseColorTexture` 引用都解析到合法的 texture/image 索引；
- 读取所有 POSITION accessor，确认无 NaN/Inf；
- 计算场景世界包围盒，确认范围合理（例如不出现所有节点集中在一点或坐标爆炸）；
- 用 three.js / Playwright 渲染并截图，目视确认贴图与摆放正常。

## Funplus / DataEye XTEA 内联包（Cocos Creator，2026-09-05 实战验证）

特征：HTML title 为 "Funplus Playable Tech Team"，资产以 `window.__HTML_COMPRESSED`（base64 + pako inflateRaw）单块内联，`window.assetsMap = {path: size}` 按插入顺序顺序切片；部分脚本用 XTEA 加密（`XteaDecrypt.js`、`playableSdkInit.js`、`analyticsInit.js`）；Cocos 主逻辑在 `assets/main/index.js`（明文 SystemJS bundle，未加密）。

### 解包步骤

1. `zlib.decompress(base64decode(__HTML_COMPRESSED), wbits=-15)` → 大 buffer；
2. 按 `assetsMap` 插入顺序顺序切片落盘（offset 累加，不解析额外偏移表）；
3. XTEA 解密（仅加密脚本需要，key 动态派生）：
   - `data-h="<hex1>,<hex2>"` 在 `id="pack-encoder"` script 标签上；
   - 密钥串 = `"PL@Y" + hex1 + hex2 + hex(密文长度) + "SDK!"`；
   - 用 FNV-1a（初值 0x811c9dc5，乘 0x1000193，仅对字母 A-Za-z 参与 xor/mul）对该串按位置 h=0..15 混出 16 字节 key，按 LE 组成 4 个 u32；
   - XTEA 32 轮解密，delta=0x9e3779b9，每块 8 字节 LE；最后一字节为填充长度；
   - Python 复刻时注意 JS 优先级：`s - (((p<<4 ^ p>>>5) + p) ^ (m + v[m>>11 & 3]))`，`+` 先于 `^`。
4. `src/effect.bin`：头 8 字节 `ffffffff 01000000` 后是 zlib 流（wbits=15），解出的是 UBO 反射/默认 uniform 值的 bin，不含 SPIR-V 和 shader 源码；shader 源码在 effect JSON（assets/main/import/xx/*.json 的 `glsl1/glsl3.vert/frag`，JSON 转义需 unicode_escape 还原）。


### 找"动效怎么做的"最短路径

1. 直接在明文 `assets/main/index.js` 里 grep `setProperty("` —— 运行时驱动 shader uniform 的脚本全在这；
2. 材质 JSON 是压缩序列化（`[ver, uuids, strings, types, instances, data]` 打包格式），`_effectAsset` 引用用压缩 uuid（前 2 hex 字符 + base64(15字节)），可直接解码定位 effect 文件；
3. 场景文件：config.json 的 `scenes` 值是 uuids 数组的**索引**，uuid 需先解压缩格式再拼路径。

### 实战案例：海岸扭动/展开（river-dissolve）

- Shader：`lite-stylized-river-dissolve`（自定义 toon 系），片元 `applyRiverDissolve`：`revealValue = clamp(uvAxis + (noiseTex(uv)-0.5)*noiseStrength)`，`cutoff = mix(-edgeWidth, 1+edgeWidth, revealProgress)`，`smoothstep` + `discard` 裁出带噪声扰动的推进边，边缘带宽 `edgeWidth` 混 `dissolveEdgeColor*brightness`；
- 驱动脚本：`LsmyRiverMaskDissolve` 组件 —— 收集子树全部 MeshRenderer，运行时把水材质换成 dissolve 材质（拷 mainTexture/mainColor/tilingOffset/noiseTexture），XTween 以 `sinusoidalInOut` 把 `revealProgress` 0→1（duration≈1.6s，延迟≈10s）写入 uniform；
- 配置在 `LogicConfig.ts`（编译进 index.js）：`riverMaskDissolve:{duration:1.6, edgeWidth:.08, noiseStrength:.12, edgeBrightness:.65, useVAxis:0, invertAxis:0}`；
- 结论：所谓"扭动"不是顶点位移/骨骼，而是**片元级噪声扰动阈值推进**（dissolve reveal），海岸线形状由 noiseTexture 的 UV 分布决定。

### Cocos GLSL → Unity Shader 移植的七个坑（2026-09-28 实机验证）

把提取出的模型+自定义 shader 做成 Unity 可直接用的包时，以下每条都是实测踩过并修掉的：

1. **`[Header(...)]` 里不能出现 `-`**（含 em dash `—`）。ShaderLab 词法器把它判成 `$undefined`，整个 Shader 解析失败 →
   `shader.name` 变空 → `Shader.Find()` 返回 null。日志只写 `Shader error in ''`（名字是空的），极难定位。
   属性**显示名**里有中文/括号没问题，只在 `[Header()]`、`[Enum()]` 这类 attribute 里出事。诊断法：写一个极简对照 shader 逐个删减，看 `shader.isSupported` 与 `propCount`。
2. **`HLSLINCLUDE` 只插入 `HLSLPROGRAM`，`CGINCLUDE` 只插入 `CGPROGRAM`**。双管线 SubShader（URP Pass 用 HLSLPROGRAM、Built-in Pass 用 CGPROGRAM）想共享实现，
   必须抽到同目录 `.hlsl` 里、两个 Pass 各自 `#include`，否则 Built-in Pass 报 `undeclared identifier`。
   （注意 URP 下用普通 `sampler2D`/`tex2D` 会关掉 SRP Batcher，单件透明材质可接受。）
3. **Cocos 的 `tilingOffset` 语义要原样保留**：Cocos 材质里 `tilingOffset` 是 4 分量 `[sx,sy,ox,oy]`，Unity 没有对应标准属性，
   要自己声明 `_TilingOffset (Vector)` 并在片元里写 `uv * xy + zw`。
   ⚠️ 因此 **`mat.SetTextureOffset("_MainTex", v)` / `mat.mainTextureOffset` 完全无效**（shader 没声明 `_MainTex_ST`），材质面板上 `_MainTex` 下面也不会出现 Tiling/Offset 栏。
   另外 `mainColor` 是**乘法基色**不是自发光，别当成 emission。
4. **溶解轴（`axisValue`）不吃 UV 偏移**：原 shader 里 `axisValue` 直接用原始 `uv.x/uv.y`，只有贴图采样走 tilingOffset。
   想让溶解前沿跟着偏移必须改 shader，且 `cutoff` 要用同一套变换，否则 progress 0/1 时头尾留残影。
5. **Blender 导 OBJ→FBX 会被归一化到 ~1m**。导入 Unity 后用 `ModelImporter.globalScale = 100` 补回原尺寸；
   验证法：对比 Unity 里 mesh bounds 与原始 Cocos 网格尺寸（本例 36.5 × 90.6 m）。
6. **进度语义先验证再写进 API**：本例 `_RevealProgress` **0 = 完全显示、1 = 完全消失**（是擦除，不是显现）。
   原始 Cocos 组件 `setRevealProgress(0)` 在 start 里 = 出生即可见，播完置 1 再 `node.active=false`。
   移植时若默认值写反，导出包里的材质就是"看不见的"，用户一打开就以为坏了 —— 用"逐帧渲染 + 统计非背景像素覆盖率"客观验证（0% → 覆盖率最大，100% → 0）。
7. **分发用的 shader 绝对不要 include `Packages/com.unity.render-pipelines.universal/...`**。
   那是 URP 包内路径，**没装 URP 包的 Built-in 工程**里整个 Shader 直接编译失败（"无法打开包含文件"，
   即使目标 SubShader 带 `RenderPipeline=UniversalPipeline` 标签不会被选中，Unity 也会编译它并在 Console 报错）。
   通用做法：只用编辑器内置 `UnityCG.cginc`（恒存在），两个 Pass 都用 `CGPROGRAM`，共享实现放 `CGINCLUDE`
   （同一编译路径，见坑 2 的反例）；URP 下渲染正常，仅失去 SRP Batcher。
   连带修正：Editor 脚本里直接引用 `UnityEngine.Rendering.Universal.*` 类型在无 URP 包工程同样编译不过，
   用反射（`AppDomain.CurrentDomain.GetAssemblies()` 里按全名 `asm.GetType(fullName)`）+ 强转基类
   `RenderPipelineAsset` 即可零依赖。保留两份同名实现不同名的 shader 文件，是为了让已导入工程的材质
   GUID 引用不断。

**无头验证环境（Windows 本机 Unity，实测唯一能跑通的组合）**：

```bash
# ❌ -nographics 会卡死在 Application.AssetDatabase Initial Refresh Start（Library/Artifacts 恒为 0）
# ❌ 上一次异常退出后复用 Library 也会卡在同一个点
# ✅ 组合：不加 -nographics + 每次先清 Library/Temp
rm -rf Library Temp
"/d/Unity/<version>/Editor/Unity.exe" -batchmode -quit \
  -projectPath "D:/Unity/<proj>" \
  -executeMethod <Namespace>.<Class>.BatchRun \
  -logFile "D:/Unity/<proj>/export.log"
```

批处理里要落成"可判定"的输出：`[summary] fails=N` + `grep -c "Shader error"` + `grep -c "error CS"`，
再用 `EditorApplication.Exit(fails > 0 ? 1 : 0)` 让 CI 拿得到非零退出码。
打包前把材质恢复成**可见**状态（本例 `_RevealProgress = 0`）再 `ExportPackage`。

**在同一会话里验证 URP 管线（2026-09-28 实测）**：`GraphicsSettings.defaultRenderPipeline = urpAsset`
运行时赋值即可生效，**不需要重启编辑器**；`UniversalRenderPipelineAsset.Create(rendererData)` 可以凭空造出 URP Asset。
URP 下 `Camera.Render()` 也能出图（URP 按需给相机补 `UniversalAdditionalCameraData`），预览渲染不必跳过 SRP。
⚠️ 测试用的 URP Asset / RendererData 必须放在导出根目录**之外**（如 `Assets/__WbUrpCheck/`），否则会被打进 unitypackage。
⚠️ `Shader.GetPropertyDescription(i)` 在 2022.3 返回的是 `string` 不是结构体；属性名用 `UnityEditor.ShaderUtil.GetPropertyName(shader, i)`。
⚠️ 一个 Shader 的 SubShader 0（URP Pass）即使工程跑 Built-in 也会被导入编译，`isSupported` 只是"当前管线能不能用"。
要确认 URP Pass 真的没问题，必须真的把管线切到 URP 再跑一遍，看 `Shader error` 计数。

## 无头浏览器抓取 GLB 兜底

仅在离线 JSON/buffer 不可用时考虑。已知问题：

- Playwright/Chromium 需要 WebGL 参数：`--enable-unsafe-swiftshader --use-gl=angle --use-angle=swiftshader --ignore-gpu-blocklist`。
- 即使 WebGL 初始化成功，Luna runtime 在裸 Chromium 中可能缺广告 SDK app systems，出现：
  - `Cannot read properties of undefined (reading 'autoSyncTransforms')`
  - `Cannot read properties of null (reading 'onFixedUpdate')`
- 这会导致 scene root 为空，无法抓 GLB。

Cocos3 包则更适合先用运行时 JS dump 场景图，再离线生成 GLB；直接抓 GLB 容易受脚本逻辑、显隐和相机影响。

因此：先离线逆向；浏览器抓取只作验证和最后兜底，不作为主流程。

## 最终交付话术

简洁说明结果，例如：

```text
已保存/导出。推荐用 scene_textured.glb，Blender 里 File > Import > glTF 2.0 直接导入。
本次还原了 X 个场景节点、Y 个 mesh 实例、Z 个材质，内嵌 N 张贴图。
限制：这是静态还原，不包含脚本运行时、粒子、骨骼动画和动态显隐。
```


## 动画数据逆向（Luna/Unity 包）

用户问"XX 动画怎么做的"时的查法（以 Township 解救 playable 为例，2026-09-17 验证）：

- 动画全在主清单 manifest（如 unknown_36.json）的 animation-clips / animator-controllers 键里。
- clip data 格式：[名称, 版本, ..., 时长, [通道...], [], isLoop, sampleRate, ...]；
  通道 = [目标路径, classId, Transform, 属性名, [bin偏移, 字节数], []]
- 控制器 data：[名称, [层...], ..., [clipIds...], 1]，层里含 state→clip 引用。
- 场景对象上找引用：comptype 1 = legacy Animation（data 里含 clip id），comptype 12 = Animator（data[1]=controller id）。全场景 JSON 序列化后按 id 字符串搜即可定位"哪个对象在播哪个动画"。
- 曲线数据按 [偏移,长度] 存在场景二进制（unknown_37.bin），是 Unity 压缩/欧拉曲线格式，float32 直读会得到乱值，但**隔行出现的实值序列即关键帧值序列**（如欧拉角 61.3→0→-61.4 = 一个来回摆动）；不必强解完整格式。
- 经验结论：Luna playable 里"看起来在转"的东西分三类：
  1. 真旋转 = AnimationClip 欧拉角关键帧（如 RotateKnife 0.25s 循环，摆锯）；
  2. 假旋转 = 材质 '_MainTex_ST' UV 偏移滚动（传送带 conv/Conv，10s/64s 循环）；
  3. 脚本旋转 = C# transform.Rotate/DOTween，编译进 WebGL wasm，静态资源里查不到，只能如实告知。


## Cocos 3.x 动画剪辑定位（cconb 直读）

- cc.AnimationClip 在 bundle 里是 .cconb 文件：16 字节头（魔数 CCON + uint32 version + uint32 文件总长 + uint32 JSON 段长）+ 明文 JSON + 二进制曲线 blob。直接 json.loads(data[16:16+json_len]) 即可。
- _tracks 为空且存在 _exoticAnimation 字段 = 曲线被烘焙成压缩二进制（exotic animation），存在 JSON 段之后的 blob 里，JSON 中不可读；普通 track（cc.animation.VectorTrack 等）的曲线 bytes 用 TypedArrayRef(offset,length) 指向同一 blob。
- 定位某物体的动画：dump_scene.json 找节点 → 看父链上 cc.SkeletalAnimation / cc.Animation 组件 → SkeletalAnimation 的骨骼动画 clip 通常与网格同 uuid 不同 sub-asset（@xxxxx.cconb）。
- 中文名节点（如 巨木/电锯机器）搜英文关键词会漏，直接 grep 中文。

## Cocos 3.x 骨骼动画解出 + 蒙皮重建（2026-09-17 巨木实战，完整可复现）

### 1. ExoticAnimation（烘焙骨骼动画）解析
- 结构：`cc.AnimationClip._exoticAnimation` → `cc.animation.ExoticAnimation._nodeAnimations[]`（每项 = `cc.animation.ExoticNodeAnimation`，含 `_path`（相对动画根的骨骼路径）+ `_position/_rotation/_scale` 三条 `cc.animation.ExoticTrack`）。
- Track：`times: TypedArrayRef` + `values: TypedArrayRef`（包在 `ExoticVec3TrackValues` / `ExoticQuatTrackValues`，后者 4 分量 = x,y,z,w，`_isQuantized=False` 时直读 float32）。
- **TypedArrayRef.offset 的基准 = 文件大小 − max(所有 TypedArrayRef 的 offset+length·4)**。不是 16+jsonLen！JSON 之后有 4~10 字节对齐填充（各文件不同）。用"最大 end 紧贴文件尾"反推最稳。
- 验证手段：times 应从 0 单调递增（步长 1/24 或 1/30），quaternion 模长应=1。

### 2. 关节顺序 = bindposes 顺序（最难的一步）
- `dump_renderers.json` 的 SMR 记录有 `bindposes[N]` + `jw[N]`（关节世界矩阵，与 bindposes 同序），但**没存关节路径**。
- 用位置匹配会把同名位置节点搞混（如 juMu/RootNode/Bone001 世界矩阵同为 0.6·I）。**必须用完整 4x4 矩阵距离匹配，且候选池只留真正的骨骼节点**（`^(Bone|Dummy)\d`），排除容器节点（SkeletalAnimation 宿主、RootNode）和网格节点。
- 交叉验证：`JW_bind_i × BP_i` 对所有 i 应等于同一矩阵 = SMR 节点世界矩阵（Cocos bindpose 定义即 `inv(JW_bind) × SMR_W`）。

### 3. glTF 蒙皮重建的 IBM（本包最大的坑）
- **IBM = Cocos bindposes 原值**，不是 inv(关节世界矩阵)！
- 推导：three.js r160 GLTFLoader `mesh.bind(skeleton, _identityMatrix)`，且 SkinnedMesh.updateMatrixWorld（attached 模式）每帧用 `inv(mesh.matrixWorld)` 覆盖 bindMatrixInverse → 渲染语义为 `v_world = Σ w(JW×IBM)×v`（mesh 节点变换被抵消）。绑定姿势要求 `Σ(JW_bind×IBM) = SMR_W`，而 `JW×BP = SMR_W` → IBM = BP。
- Blender glTF importer 遵循同一 glTF 语义，同样适用。
- 若 IBM 用错（如 inv(JW)），症状：t=0 模型横躺/跑位、动画帧剧烈畸变——因为原始顶点被直接当世界坐标。
- 顶点数据：原始未烘焙的 `a_position/a_joints/a_weights`（dump_meshes.json 的 base64 buffer，按 stride 72 交错读：pos12+normal12+uv8+tangent16+joints8+weights16）。注意 export_glb.py 的 bake_skin 对绑定姿势是恒等变换，GLB 里现有顶点=原始顶点，可直接复用。

### 4. 验证三板斧
1. **数学验证**：自实现 glTF 采样（LINEAR + quat slerp）+ 蒙皮，t=0 蒙皮结果 vs `SMR_W × 原始顶点`，偏差应 <1e-5。
2. **three.js 实机渲染**（Playwright + 本地 three@0.160 from unpkg，`--use-gl=angle --use-angle=swiftshader`）：加骨骼标记球（红球绑 bone.matrixWorld 位置），图上球与网格对位 = 蒙皮对；球与网格分离 = IBM/关节映射错。
3. 帧序列对比：绑定姿势（t=0）与中间帧应有形变差异。

### 5. 相机/取景坑
- skinned mesh 的 `Box3.setFromObject` 不含蒙皮结果，自动框选会翻车——用已知的关节世界 bbox 手动设相机。
- `mixer.setTime(duration)` 在 LoopRepeat 下会 wrap 回 t=0，帧序列取 t=dur 会看到绑定姿势，不是 bug。

### 6. 本次产物
- `extract_20260909_traintoy/parse_exotic.py`（cconb 骨骼动画解析器）、`build_jumu_anim.py`（GLB 重建）、`verify_jumu_anim.py`（数学验证）、`render_anim.js`+`serve_anim/`（渲染验证）。
- 交付 `deliver/jumu_anim.glb`（蒙皮+动画，Blender 可直接导入播放）+ `deliver/jumu_animation.json`（原始关键帧）。

## Cocos3 assetmap「PlayCools 变体」+ 骨骼烘焙全量导出（2026-09-21 六边形清理泳池实战）

### 1. 包体识别与解包
- HTML 标志 `window.__PLAYABLETOOLS_FORMAT__="cocos3-assetmap"`，但主块编码是
  `__sa(new TextDecoder().decode(window.unbrotli(base64ToArrayBuffer("<B64>"))))`
  = **base64 + brotli**（不是 base122！别照抄 traintoy 的 base122ToArrayBuffer）。
- 解出的文本就是 `window.assetMap={...}`，Node vm 求值后按扩展名落盘：`.bin/.jpg/.png/.webp/.mp3` 走 base64 解码，其余当文本。
- 场景在 `assets/main/config.json` 的 `packs` 里：`packs['03e2bf6cc'] = [256 个 uuid 索引]`，即 `import/03/03e2bf6cc.json` 是含 256 个资产的大包（Cocos3 序列化格式 `[ver,uuids,strings,classes,masks,instances,data]`）。

### 2. 材质贴图的真实位置（这次最大的坑）
- `Material._props` 是**按 pass 索引的数组**，`_props[i] = {uniform名: 值或Texture}`，贴图就在这里（`mainTexture/normalMap/emissiveMap/heightMap`）。
- 完整默认 uniform（含未覆写的 `mainColor/tilingOffset/roughness/metallic`）在 `_passes[k]._properties[key].value`。
- 描边材质（`standard-outline-Light`）有 7 个 pass：pass 0/4/5/6 是 outline，pass 1~3 才带 `mainTexture` —— 选"第一个带 mainTexture 的 pass"。
- 无贴图材质的颜色回退链：`mainColor → baseColor → debrisColor → color`（`dissolveDebris` 类 shader 用 debrisColor）。
- 透明判定：`_defines[pass].USE_ALPHA_TEST` → MASK；`_states[pass].blend.targets[0]` 非空 → BLEND。

### 3. SkinnedMeshRenderer 骨骼数据位置
- 组件自身的 `SMR._joints` 运行时是**空数组**，`skinInstance` 也是空 —— 别在那找。
- 真身在 **`SMR._skeleton`**（`cc.Skeleton` 资产）：
  - `_joints`：**字符串数组**，路径相对 `_skinningRoot`（注意 `getPathInHierarchy()` 不含 scene 根名，拼路径要补 `scene/` 前缀）；
  - `_bindposes`：Mat4 数组，字段 `m00..m15`（**列主序**，flat[c*4+r]=M[r][c]，与 glTF 一致）。

### 4. 姿态烘焙公式（已验证）
- `v_local = inv(SMR_W) × Σ_k w_k × (JW_now_k × BP_k) × v`，节点保留原 TRS。
- **绑定姿势校验会骗人**：静置物件（鱼）满足 `JW_bind×BP = SMR_W`（全关节相等），但带动画的角色各关节 `JW×BP` 互不相等也不等于 I —— 这是正常现象，直接用当前姿态烘焙即可，结果与游戏画面一致。
- 199 个 SMR 全部烘焙成功、0 缺失关节；按「mesh uuid + 烘焙后顶点 hash」去重，同 pose 的鱼/顾客实例共享网格。

### 5. 顶点格式速查（Cocos3 交错缓冲）
`32=12B f32×3（position/normal）、21=8B f32×2（uv）、44=16B f32×4（tangent/weights/color）、42=8B u16×4（joints）`。
属性偏移按 bundle 内**声明顺序**累加，校验 `Σsize == stride`；索引 `indexView.stride` 2=u16 / 4=u32，`primitiveMode 7=TRIANGLES`。

### 6. 其他要点
- `ParticleSystem` 的贴图在 **`ps.renderer._mainTexture`**（组件顶层 `_mainTexture` 是空的）；粒子无 mesh 时用 billboard quad 表示，水平 quad（XZ 平面）+ 原位置抬高集中成独立根组（如 `VFX_Particles`），Blender 里可整组隐藏。
- **glTF `node.rotation` 是 (x,y,z,w)** —— 写成 (w,x,y,z) 不会报错，只会整体错位；用「导出后世界包围盒 vs 引擎内包围盒对账」最快定位。
- Cocos3 `a_texCoord` 与 glTF 同为左上原点，**不要翻 V**。
- 验证三板斧：GLB 结构校验（chunk 长度 / bufferView 越界 / POSITION NaN）→ 世界 AABB 与引擎对账 → three.js 多视角渲染目检。

### 7. 本次产物
`extract_20260921_poolcools/`：`unpack_main.py`、`dump_assetmap.js`、`dump_runtime2.js`、`export_glb.py`、`export_obj.py`、`verify_glb.py`、`render_glb.js`、`analyze*.py`。
交付 `scene_reconstructed_textured/scene_textured.glb`（4582 节点/1204 实例/398,529 面/6.5MB）+ OBJ 兜底 + 74 张贴图 + README。

## White Bear Studio / Century Games「polar」单文件 Cocos3 包（2026-10-16 STPL307 轨道扩张实战）

### 1. 包体识别与三层解包
- 外壳：`<script super-html="keep">` 里 `(function(){ var polar = window.polar ... })()`，标记 `window.polar.packageToolVersion`；主块是
  `const illegal=[0,10,13,34,38,92]; const source="…"; const expectedLength=N; function decodeBase122(input){…}; const html=utf8(pako.inflateRaw(decodeBase122(source))); document.open(); document.write(html); document.close();`
  → **base122 + pako.inflateRaw**（注意：不是 brotli，也不是单个 base64）。
  - 这里的 base122 变体：`code<128` 直接 push7；否则 `packed=code-128; illegalIndex=packed>>8; nextValue=packed&127` → `push7(illegal[illegalIndex]); push7(nextValue)`；`expectedLength` 是**解压后长度**（可用作校验）。
  - 最省事的做法：不要手写解码器，直接用 Node `new Function('require','pako',...)` 跑官方代码，把 `document.open/write/close` 替换成 `fs.writeFileSync`；pako 就在前一个 `<script>`（UMD）里，`new Function('window','self','global',pakoSrc)(win,win,win)` 取出 `win.pako`。
- 内层 HTML 把资源全内联，**没有外部文件请求**：
  - `window.__res = { "assets/.../xxx.jpg": "data:image/jpeg;base64,…", "assets/.../xxx.json": "<json文本>", … }`
  - `window.__zip = "<base64 ZIP>"` 含 `cocos-js/cc.js`、`assets/*/config.json`、`assets/main/import/**`、`src/**`（JSZip `base64:true` 解，entry 按 `async('string')` 读）
  - 加载器逻辑：`window.__res[super_reg_search(部分路径)]`，图片走 `atob(src.substring(src.indexOf(',')+1))` → 说明值就是 **data URL**。
- 场景在 `assets/main/config.json`：`scenes:{'db://assets/scene/Main.scene': 0}`、`packs:{'0fc097c85':[464 uuids]}`、`extensionMap:{'.cconb': 20}`。

### 2. 最大的坑：`__res` 的值是 data URL，不是裸 base64
- 症状：落盘的 `.jpg` 文件头是 `75ab5a8a 66a07bf8 e97a06da` 之类，真实 JPEG 魔数 `ffd8ff` 出现在**偏移 15**；`.png` 更惨，前 64 字节都找不到 `\x89PNG`。
- 原因：`Buffer.from("data:image/jpeg;base64,/9j/...", 'base64')` 不会跳过 `data:image/jpeg;base64` 这段（字母全是合法 base64 字符），会把它当成数据解出 15 字节垃圾。
- 修正：`/^data:([^;,]*);base64,(.*)$/s` 剥前缀再解码；`main_bundle.zip` 里的 native 文件内容**也是文本 data URL**，同样处理。
- 自检：解包后统计 `(扩展名, 魔数)` 组合，`.png→PNG` / `.jpg→JPEG` 必须 100%。

### 3. 材质（多 pass 描边管线）
- 本包材质典型 7 个 pass：`USE_OUTLINE` 的描边 pass（`lineWidth/depthBias/outlineColor/outlineParams`）+ 基础色 pass。
- 基础色贴图槽的优先链要覆盖：`mainTexture`（`cc-art-outline-*`）→ `baseTexture`（`cc-map`）→ `albedoMap` → `layerRTexture`（`cc-map` 只有 layerR 时）。
- 透明判定：`defines[pass].USE_ALPHA_TEST`→MASK(+`alphaThreshold`)；`CC_IS_TRANSPARENCY_PASS`→BLEND；`mainColor[3]<1`→BLEND。
- 本包 `tilingOffset` 全为默认 `[1,1,0,0]` → 不需要 `KHR_texture_transform`。

### 4. 全图体积特效（雾层）必须隔离
- `layer_fog/fog` 是 `lscale=[400,1,400]` 的扁平 Cube + `cc-noise-fog` 程序化材质 → 导出成白色巨板，**整个场景被挡住**（渲染出来只有一块白面）。
- 判据：节点名或材质名匹配 `/fog/i`。处理：整棵子树移到独立**顶层根组**（如 `__FogVolume_已隔离(可隐藏)`）并 +Y 2000，同时在 three.js 校验页里 `visible=false`。注意别把它挂在 `scene` 根下 —— 会污染主场景 AABB（相机自动取景直接翻车）。
- 隔离嵌套：`layer_fog`（父）与 `fog`（子）都匹配时只隔离**最外层**一次（walk 传 `in_fx` 标志），否则会被叠加平移两次。

### 5. 渲染取景
- 场景里常有超大地面/背景平面（本例 `map1` 世界尺寸 172），自动框选会把主体压成一个小点。做法：先按「世界尺寸 = mesh 局部 extent × 节点最大轴缩放」排序，排除 >100 的实例，再算内容 AABB 手动设相机。

### 6. 验证清单
- GLB 结构：chunk 长度 / bufferView 越界 / accessor 大小 / POSITION NaN / 节点变换有限且无近零缩放 —— 全 0 通过。
- 图像：遍历 `images[].bufferView` 查魔数（PNG/JPEG）+ `mimeType` 一致性。
- three.js 多视角目检（含隐藏雾层、隐藏 prefab 排、单独看 prefab 排）。

### 7. 本次产物
`extract_20261016_track/`：`decode_inner.js`、`dump_res.js`、`dump_zip.js`、`dump_runtime.js`、`dump_prefabs.js`、`export_glb.py`、`export_obj.py`、`verify_glb.py`、`render_glb.js`、`analyze*.py`。
交付 `scene_reconstructed_textured/scene_textured.glb`（3732 节点 / 1187 实例 / 21,926 去重面 / 2.3 MB）+ OBJ 兜底 + 107 张贴图 + `meshes_index.json` + README。

### 8. 完整执行流程（九阶段，下次照这个顺序跑）

> 上述 1~7 是「要点速查」，本节是「执行顺序」。任何一条都不要跳步 —— 跳过 dump 直接读 .bin，属性名和 stride 只能靠猜。

**总览**：`拆 script → 官方解码器解 inner.html → 剥 data URL 落 __res/__zip → 读 main/config.json 定方向 → http server 起站 → probe 探 struct → Playwright dump 六件套 → mesh/bbox 分析 → 导 GLB/OBJ → 结构校验 + AABB 对账 + 渲染目检`

**目录约定**（每个输入 HTML 一个独立目录）：

```text
extract_YYYYMMDD_xxx/
├── raw/                       # 从 HTML 拆出的 <script> 片段
├── unpacked/inner.html        # 解出的内层 HTML（资源全内联）
├── extracted_assets/assets/   # __res / __zip 落盘
│   ├── main/config.json       # 场景 + bundle 索引 ★
│   ├── main/import/**         # Cocos3 序列化资产（.json/.bin/.cconb）
│   └── resources/native/**    # 原始贴图
├── serve_render/              # 可运行站点（喂 Playwright）
├── dump/                      # 6 个运行时 json ★
├── scene_reconstructed_textured/  # glb + gltf + textures/ + meshes_index.json + README
├── models_obj/                # OBJ 兜底
└── renders/                   # 目检图
```

| 阶段 | 做什么 | 产出 / 验收 |
|---|---|---|
| **A 拆壳** | 正则切 `<script[^>]*>([\s\S]*?)</script>` 到 `raw/script_NN.js`，认准哪个含 `pako`（主块前一个）、哪个含 `decodeBase122`（主块） | `raw/` 齐全，`grep -l` 能定位 |
| **B 解内层** | 不手写 base122：`new Function('require','pako',...)` 跑官方代码，把 `document.open/write/close` 换成 `fs.writeFileSync(inner.html)` | `inner.html` 出现，本例 ~7 MB |
| **C 拆资源** | 字符串感知花括号扫描取 `window.__res=` 字面量 → `new Function` 求值 → 逐 key 落盘；`window.__zip` 走 JSZip `base64:true` | `(扩展名, 魔数)` 统计：`.png→PNG` / `.jpg→JPEG` 必须 100% |
| **D 起站** | `serve_render/` = inner.html + 解出的 assets，`python -m http.server 8496 --bind 127.0.0.1` | `probe_boot.js` 能看到 `window.cc`、无 PAGEERROR |
| **E 探路** | 一次问清：组件类型分布 / 资产类型分布 / `mesh.struct.vertexBundles[0].attributes[].format` + `view.stride` / `primitives[0]` / `Skeleton._joints` 形态 | 拿到顶点格式表，决定后面怎么解 |
| **F dump** | 场景树 + 全部 Mesh(struct+buffer) + 材质 + 贴图 + Skeleton + Prefab → `dump/*.json` 六件套 | 节点数 `>1000` 且**连续 3 次不变**才算就绪（本例 3732） |
| **G 分析** | `mesh_stats.py` 找 0 面/NaN/超大平面；`analyze_bbox.py` 记下**引擎世界 AABB** | AABB 就是阶段 I 的唯一硬标准，先存 |
| **H 导出** | 顶点按 stride 解 → 骨骼当前姿态烘焙 → 材质选带贴图 pass → 雾层隔离 → 导 GLB + OBJ | 结构 0 错误、去重面/实例面统计合理 |
| **I 验证** | 结构校验 → **AABB 对账** → three.js 多视角目检 | 三样全过才交付 |

**dump 字段速查**（写导出器只看这张表）：

| 文件 | 内容 |
|---|---|
| `dump_scene.json` | `nodes[]`：`i`(索引) `p`(父) `path`(全路径) `name` `lpos/lrot/lscale` `wmat`(16 元素世界矩阵) `comps[]` |
| `dump_meshes.json` | `uuid → {name, struct, buf(base64)}` |
| `dump_mats.json` | `uuid → {name, passes[{textures}], passUniforms[], defines[], states[]}` |
| `dump_texs.json` | `uuid → {name, image uuid}` |
| `dump_skeletons.json` | `uuid → {joints[], bindposes[]}` |
| `dump_prefabs.json` | prefab 树 + 网格用法（未实例化的模板也在） |

**核心三段代码**（导出器骨架，可直接抄）：

```python
# 1) 顶点：交错缓冲按声明顺序累加偏移，校验 Σsize == stride
FMT = {32:(12,3,'f'), 21:(8,2,'f'), 44:(16,4,'f'), 42:(8,4,'u2'),
       43:(8,4,'u2'), 30:(4,4,'u1'), 24:(4,2,'u2'), 16:(4,1,'u1'), 28:(8,4,'i2')}
cur = 0
for a in bundle['attributes']:
    size, ncomp, kind = FMT[a['format']]
    attrs.append((a['name'], cur, size, ncomp, kind)); cur += size
assert cur == bundle['view']['stride']
view = np.lib.stride_tricks.as_strided(arr[base:], shape=(n, stride), strides=(stride, 1))
vals = np.ascontiguousarray(view[:, aoff:aoff+size]).reshape(-1).view(dt).reshape(n, ncomp)
# u1 额外 /255.0；a_texCoord 左上原点，不要翻 V

# 2) 蒙皮：当前姿态烘焙，节点保留原 TRS
JMs = [mat_mul(joint_world_k, flat_to_M(bindpose_k)) for k in range(len(bps))]
acc = Σ_k w_k * (hom @ JMs[k].T)          # 对 JOINTS_0 的 4 个槽位逐槽累加
POSITION = (acc @ inv(SMR_W).T)[:, :3]     # 法线只取 3x3 再归一化
key = md5(uuid + md5(烘焙后 POSITION))      # 同姿态实例共享网格

# 3) 材质：7 pass 描边里只取带贴图的基础色 pass
for key in ('mainTexture', 'baseTexture', 'albedoMap', 'layerRTexture'):
    for p in mat['passes']:
        if (p.get('textures') or {}).get(key, {}).get('tex'):
            return p
```

**三条不能省的收尾**：结构校验 0 错误 → 世界 AABB 与引擎一致 → 多视角渲染目检（全景 / 隐藏雾层组 / 隐藏 prefab 排 / 独看 prefab 排）。

**最贵的三条经验**（同类包 90% 的时间浪费都在这）：
1. `__res` 值是 **data URL**，不剥前缀贴图全废（魔数会整体偏 15 字节）。
2. `Material._props` 是**按 pass 索引的数组**，7 pass 描边材质里基础色只在 pass 1~3。
3. 骨骼真身在 `SMR._skeleton`（组件 `_joints` 运行时为空），必须用**当前姿态**烘焙，绑定姿势校验会骗人。

**同类包量级基线**（用来判断"是不是解漏了"）：内层 HTML ~7 MB、场景节点 ~3700、mesh 资产 59 → 实例 1187、材质 29、内嵌贴图 18 + 外部 107、去重面 21,926 / 实例面 579,074、GLB 2.3 MB、全程约 50 分钟。
