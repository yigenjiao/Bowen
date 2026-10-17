# luna-playable-extract

从 **Luna / DataEye / Cocos Creator 试玩广告（playable ad）单文件 HTML** 中离线提取全部 3D 模型与贴图，绑定材质、还原场景摆放，导出 Blender 可直接导入的 `scene_textured.glb`（同时给 OBJ 兜底）。

整理自 2026-07 ~ 2026-10 的十余次实战（Township、PlayCools 泳池、STPL307 轨道扩张、推小火车、雪球机等），记录的是**跑通过的路径和踩过的坑**，不是理论方案。

## 能处理哪几类包

| 判据（grep 原文即可） | 包型 | 章节 |
|---|---|---|
| `*_str.dat` / `meshes` 清单 / Unity 风格 bundle | Luna / Unity playable | 主体 + 「Unity / Luna 包补充流程」 |
| `__PLAYABLETOOLS_FORMAT__="cocos3-assetmap"` + `unbrotli` | Cocos3 assetmap（PlayCools 变体） | 「PlayCools 变体」 |
| `super-html` + `decodeBase122` + `inflateRaw` + `window.__res` + `window.__zip` | Cocos3「polar / Super HTML」单文件包 | 「polar」节（九阶段完整流程 + 代码骨架） |
| `window.__HTML_COMPRESSED` + XTEA | Funplus Playable Tech Team | 「XTEA 内联包」 |

## 安装

```bash
git clone https://github.com/yigenjiao/Bowen.git
cp -r Bowen/skills/luna-playable-extract ~/.workbuddy/skills/
```

放进 `~/.workbuddy/skills/` 后，给 WorkBuddy 一个 playable HTML 并说「把里面所有模型和贴图导出，摆好位置绑好贴图」，就会自动走这套流程。

## 里面有什么

单文件 `SKILL.md`，按「要点速查 + 执行顺序 + 可抄的代码骨架」组织：

- 包型分诊表（先判包，再选解码器 —— 混用 base122 / brotli / XTEA 是最常见的翻车点）
- 各包型的解包流程、组件类型表、Mesh 字段布局
- 顶点交错缓冲按 stride 解析、蒙皮当前姿态烘焙公式
- 材质多 pass 描边管线里怎么挑对那个 pass
- 导出后的三板斧：结构校验 → 世界 AABB 与引擎对账 → three.js 多视角目检

## 典型产出

| 项目 | 节点 | 实例 | 面数（去重） | GLB |
|---|---|---|---|---|
| STPL307 轨道扩张 | 3732 | 1187 | 21,926 | 2.3 MB |
| 六边形清理泳池 | 4582 | 1204 | — | 6.5 MB |

## 说明

- 还原的是**静态场景**：不含脚本运行时、粒子动态、骨骼动画播放（蒙皮按抓帧姿态烘焙成静态网格）。
- 仅供技术学习与个人研究，提取出的模型、贴图版权归原厂所有，请勿商用或再分发。
