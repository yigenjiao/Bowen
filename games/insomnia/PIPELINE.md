# 《失眠》AI 资产流水线

全部资产用 AI 生成。分工：**AI 出东西，一根蕉把关，Claude 写代码和组装。**
每一步都有“验收”，不过关不进下一步。

价格、免费额度、授权条款以各工具官网为准。**免费版生成的模型和音效，有的要求署名或不能商用，正式上线前逐个确认授权。**

---

## 总览

| 步 | 做什么 | 工具 | 谁 | 产出 |
| --- | --- | --- | --- | --- |
| 0 | 定风格 | 即梦 / Midjourney / GPT 生图（任选一个） | 你出图，你拍板 | 1 张定调主视觉 |
| 1 | 列资产清单和提示词 | 本文件 | Claude | 每个资产一条提示词 |
| 2 | 出单体概念图 | 同第 0 步的生图工具 | 你 | 每个资产 1 张白底单体图 |
| 3 | 图生 3D | Tripo / 腾讯混元 3D / Meshy（任选一个） | 你 | 带贴图的 `.glb` |
| 4 | 清理和体检 | Blender + GLB 体检台 | 你（Claude 提供 Blender 脚本） | 尺寸、朝向、面数合规的 `.glb` |
| 5 | 角色绑骨骼和动画 | Mixamo（或 Tripo 自带的自动绑骨） | 你 | 带 idle / walk / crouch 的香蕉猫 |
| 6 | 地面墙面贴图 | 生图工具（无缝贴图） | 你 | 木地板、墙纸等可平铺贴图 |
| 7 | 音效 | ElevenLabs 音效生成（备选：Claude 用代码合成） | 你 | 心跳、地板吱呀、拖拽声等 |
| 8 | 组装上线 | three.js（游戏代码） | Claude | 可玩的 Demo |

**第 8 步不用等前面全部做完。** Claude 先用占位资产把 v0.2 的玩法、灯光、声音做好，你的资产做好一个就换一个。

---

## 第 0 步：定风格（今天）

用同一句提示词出 4 到 8 张图，挑 1 张作为整个游戏的定调图。之后所有资产都拿它当风格参考（垫图）。

**提示词（英文效果更稳，中文工具可直接用中文版）**

```
A tiny orange-and-white cat wearing a banana costume with pink cat ears, standing alone on the wooden floor of an enormous bedroom at 3 a.m. The bed looms like a cliff, a giant slipper and a stack of books tower over the cat. Cold blue moonlight through tall curtains, one warm night lamp, car headlights sweeping across the wall. Stylized 3D, miniature scale, dark storybook atmosphere, low side camera, 2.5D game screenshot, volumetric fog, film grain, muted palette with a single warm accent.
```

```
一只穿香蕉装、头顶粉色猫耳的橘白小猫，独自站在凌晨三点巨大卧室的木地板上。床像悬崖一样高，巨大的拖鞋和一摞书比小猫高好几倍。冷蓝月光从高高的窗帘透进来，一盏暖色小夜灯，车灯扫过墙面。风格化 3D，微缩比例，暗调绘本氛围，低机位侧视，2.5D 游戏截图，体积雾，胶片颗粒，低饱和配色加一个暖色点缀。
```

**注意**
- 提示词里**不要写任何现有游戏的名字**。借的是氛围和类型，画面必须是自己的。
- 买来的 Unity 场景包可以自己看着找感觉，但不要拿它的截图去垫图生成，也不要照着它的具体资产做。

**验收**：一眼能看出“小、大、冷、孤单”；香蕉猫的形象和你的 IP 一致；你愿意把它设成手机壁纸。

---

## 第 1 步：资产清单（Claude 已列好）

| # | 资产 | 三角面上限 | 备注 |
| --- | --- | --- | --- |
| 1 | 香蕉猫 | 5000 | 要绑骨骼；高约 1.2 单位 |
| 2 | 影子手（怪物） | 4000 | 从床上垂下来的巨大的手，要能做抓取动画 |
| 3 | 床（床架 + 床垫 + 被子 + 枕头） | 6000 | 床底要能让香蕉猫走过 |
| 4 | 床头柜 | 1500 | |
| 5 | 小夜灯 | 800 | |
| 6 | 拖鞋 | 1500 | 香蕉猫能钻进去 |
| 7 | 书 | 600 | 做 1 本，代码里摆成一堆 |
| 8 | 衣服堆 | 3000 | 香蕉猫能钻进去 |
| 9 | 手机 | 400 | 掉在地上，屏幕亮着 |
| 10 | 衣柜 | 2000 | 背景 |
| 11 | 窗户 | 1500 | |
| 12 | 窗帘 | 2000 | |
| 13 | 闹钟 | 800 | 显示 3:07 |
| 14 | 玩具或杂物 | 1500 | 1 到 2 个，增加生活感 |
| 15 | 木地板贴图 | 无缝贴图 | 第 6 步 |
| 16 | 墙纸贴图 | 无缝贴图 | 第 6 步 |

**优先级**：先做 1 香蕉猫、2 影子手、3 床、6 拖鞋。有了这 4 个，Demo 的味道就出来了。

---

## 第 2 步：单体概念图

图生 3D 工具只认“干净的单体图”，背景越干净，出的模型越好。

**提示词模板**（把 `[资产]` 和 `[材质]` 换掉，同时垫上第 0 步选定的图）

```
A single [资产], [材质], stylized game asset in a dark storybook style, clean silhouette, 3/4 view, centered, full object in frame, plain light gray background, soft even lighting, no cast shadow, no text.
```

**例子**：`A single fluffy slipper, faded purple felt with worn edges, ...`

**验收**：只有一个物体、四周留白、没有被裁切；风格和第 0 步的定调图一致。

---

## 第 3 步：图生 3D

| 工具 | 特点 |
| --- | --- |
| **Tripo** | 出模快，自带自动绑骨骼，适合香蕉猫 |
| **腾讯混元 3D** | 国内访问方便，贴图质量好 |
| **Meshy** | 能一边生成一边重做贴图 |

**设置**：导出 `.glb`，带 PBR 贴图，面数按第 1 步的上限设（工具里一般叫“低模”或 face limit）。

**验收**：轮廓和概念图一致；没有明显的破面或融化感；贴图没有大块糊掉。不过关就换一张概念图重来，不要在烂模型上修。

---

## 第 4 步：清理和体检

1. 在 Blender 里导入 `.glb`，用 Claude 提供的脚本一键处理：统一尺寸、原点放到底部中心、正面朝前、按需减面，再导出 `.glb`。
2. 拖进 **GLB 体检台**（https://yigenjiao.github.io/Bowen/tools/glb-inspector/ ）体检，有问题就一键修复。
3. 把文件放进 `games/insomnia/models/`，文件名用英文（比如 `slipper.glb`）。

**验收**：体检台没有红色错误；面数在上限以内。

---

## 第 5 步：香蕉猫绑骨骼和动画

1. 把香蕉猫导出成 `.fbx`，上传到 **Mixamo**，自动绑骨骼。
2. 挑三段动画：站立呼吸（idle）、走路（walk）、蹲下或缩成一团（crouch）。勾选“原地动画”（In Place）。
3. 分别下载，在 Blender 里合并成一个 `.glb`，三段动画分别命名为 `idle`、`walk`、`crouch`。
4. 影子手也可以用同样的办法做“张开、合拢”的抓取动画。

**验收**：在体检台里切到“骨骼”视图，三段动画都能播放，没有扭曲或飞点。

---

## 第 6 步：地面墙面贴图

**提示词模板**

```
Seamless tileable texture of [材质], top-down flat view, even lighting, no shadows, dark storybook style, 1024x1024.
```

做两张：旧木地板、褪色墙纸。

**验收**：四方连续平铺时看不出接缝。

---

## 第 7 步：音效

用 ElevenLabs 的音效生成，每条生成 3 个版本挑 1 个。

| 文件名 | 提示词 |
| --- | --- |
| `heartbeat.mp3` | slow heavy heartbeat, close, muffled, loopable |
| `creak.mp3` | single old wooden floorboard creak, quiet room |
| `drag.mp3` | giant hand slowly dragging across a wooden floor |
| `grab.mp3` | sudden heavy whoosh and thud, a hand slamming shut |
| `room.mp3` | low dark room tone at night, distant traffic, loopable |
| `car.mp3` | car passing outside at night, muffled through a window |

不想做这一步，就告诉 Claude，Claude 用代码合成一套（质量够 Demo 用）。

---

## 第 8 步：组装（Claude）

- v0.2 先用占位资产完成：影子手怪物、脚步声惊动机制、按住才能躲、声音、去掉界面、抓捕画面、暗角和胶片颗粒。
- 资产到一个换一个，最后统一调灯光和后期。
- 上线后挂进主页，录一段完整演示。

---

## 进度表

| 日期 | 目标 |
| --- | --- |
| 11-02（今天） | 第 0 步：选定定调图 |
| 11-08（周日） | 香蕉猫、影子手、床、拖鞋 4 个模型过体检台；香蕉猫绑好骨骼；Claude 完成 v0.2 玩法 |
| 11-15 | 其余模型、两张贴图、音效全部到位，Demo 上线 |
| 11-30 | 挂进主页，录演示视频 |
