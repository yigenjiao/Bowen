# 失眠

**▶ 试玩：https://yigenjiao.github.io/Bowen/games/insomnia/**

凌晨 3:07，香蕉猫穿过巨大的卧室，走到窗帘边等天亮。车灯扫过来就躲起来。

## 文件夹里有什么

| 位置 | 用途 |
| --- | --- |
| `index.html` | 游戏本体 |
| `models/banana-cat.glb` | 香蕉猫模型 |
| `models/local/` | 本地测试用的模型，不上传仓库（已在 `.gitignore` 里忽略） |
| `vendor/` | 内置的 three.js 和模型加载器 |
| `concept/keyart.webp` | 定调图 |
| `PIPELINE.md` | AI 资产流水线和提示词 |
| `tools/blender_cleanup.py` | Blender 清理脚本 |

## 在自己电脑上跑（PowerShell）

```powershell
cd D:\Bowen
python -m http.server 8000
```

然后打开 http://localhost:8000/games/insomnia/
