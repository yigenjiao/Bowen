<p align="center">
  <a href="https://yigenjiao.github.io/Bowen/"><img src="assets/cover.webp" width="100%" alt="BOWEN —— 把黑盒，拆成白盒。3D 技术美术：Playable / Cocos 逆向提取、GLB 资源还原、Shader 复刻。"></a>
</p>

<p align="center">
  <strong><a href="https://yigenjiao.github.io/Bowen/">个人主页</a></strong> &nbsp;·&nbsp;
  <strong><a href="https://yigenjiao.github.io/Bowen/tools/glb-inspector/">GLB 体检台</a></strong> &nbsp;·&nbsp;
  <a href="skills/luna-playable-extract/">提取工作流文档</a> &nbsp;·&nbsp;
  <a href="#联系">联系我</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Cocos_Creator-3.x-e6480f?style=flat-square" alt="Cocos Creator 3.x">
  <img src="https://img.shields.io/badge/Playable-Luna_%2F_Unity-c98a2b?style=flat-square" alt="Luna / Unity Playable">
  <img src="https://img.shields.io/badge/glTF-2.0-f0e9dc?style=flat-square&labelColor=14110d" alt="glTF 2.0">
</p>

我是 **Bowen**，3D 游戏技术美术。专门处理编译后的 **Cocos Creator / Luna / Unity 试玩广告（Playable）**：
从单个 HTML 包里还原场景节点树、模型、贴图和材质，导出可以二次开发的标准 GLB；
也拆解溶解、河流、卡通渲染这类效果，在引擎里重建等效 Shader。

**不是「会一点引擎」，而是能把黑盒拆成白盒。**

## 🧰 GLB 体检台：把踩过的坑做成工具

<p align="center">
  <a href="https://yigenjiao.github.io/Bowen/tools/glb-inspector/?sample=broken.glb"><img src="assets/inspector.webp" width="100%" alt="GLB 体检台界面：左侧列出错误和修复建议，右侧 3D 视口切到顶点色视图，定位到 COLOR_0 全黑的网格"></a>
</p>

<p align="center">
  <strong><a href="https://yigenjiao.github.io/Bowen/tools/glb-inspector/">打开体检台 →</a></strong> &nbsp;·&nbsp;
  <a href="https://yigenjiao.github.io/Bowen/tools/glb-inspector/?sample=broken.glb">看它怎么抓一个坏样本</a>
</p>

把 `.glb` 拖进浏览器，几秒内告诉你**这个模型交付出去会不会出事**。全部在本地运行，文件不会上传。

它不靠 three.js 的渲染结果猜问题，而是直接读 glTF 的原始字节逐项检查。规则来自真实交付里踩过的坑：

| 检查 | 会发生什么 |
| --- | --- |
| **bindposes 主序写反** | 平移落在 `[3,7,11]`，模型一播动画就被甩飞 |
| **accessor 按 float64 落盘** | 声明 FLOAT 却写了 8 字节，读出来全是乱码 |
| **COLOR_0 乘贴图** | 蓝色贴图被染红，或者整块发黑 |
| **GLB 的 buffer 带 uri** | three.js / Blender 报 `Failed to load buffer` |
| 索引越界 · 法线未归一 · 缺 min/max | 破面、光照异常、某些角度模型消失 |
| 蒙皮权重和 · 骨骼索引越界 | 动起来整块缩放、顶点乱飞 |
| 零缩放节点 · 贴图格式与尺寸 | 运行时隐藏态被误删、移动端贴图加载失败 |

每条问题都附带**成因和修复写法**，可以一键定位到出问题的网格。另有法线、UV 棋盘格、顶点色、骨骼权重四种检查视图，也可以导出 Markdown 体检报告附在交付里。

## 能直接交付的能力

| | 能力 | 内容 |
| --- | --- | --- |
| 01 | **逆向提取** | 从编译后的 Cocos Creator / HTML Playable 包里还原场景节点树、模型、贴图与配置数据 |
| 02 | **资源还原** | 贴图绑定、UV 完整性与摆位逐项校验，导出标准 GLB，定位并补齐缺失资产 |
| 03 | **Shader 复刻** | 拆解溶解、河流、卡通渲染等效果参数，在引擎内重建，并移植到 Unity 管线 |
| 04 | **AI 工作流** | 概念出图、批量素材生成与自动化脚本，把重复劳动交给流水线 |

做过的案例（全资产提取、Shader 复刻、主题改版，以及从 8MB 单文件网页里导出 3732 个模型）见[个人主页](https://yigenjiao.github.io/Bowen/#cases)。

## 仓库里有什么

```
index.html                       个人主页
tools/glb-inspector/             GLB 体检台（单文件，无需构建）
  samples/                       健康样本 / 故意埋坑的样本 + 生成脚本
skills/luna-playable-extract/    Playable 资源提取工作流：包型判断、解码、导出标准与踩坑记录
assets/                          封面、截图、二维码
.github/cover/                   README 封面的源文件（HTML + three.js），可以重新生成
```

## 联系

逆向提取、资源还原、Shader 复刻、Playable 资产管线，都可以直接聊。
说清楚需求和你手上的产物形态，我先判断能不能做。

- **Email**：shiboxun123@gmail.com
- **GitHub**：[@yigenjiao](https://github.com/yigenjiao)
- **微信**：扫下面的二维码

<img src="assets/wechat-qr.jpg" width="180" alt="微信二维码">
