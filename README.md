<p align="center">
  <a href="https://yigenjiao.github.io/Bowen/"><img src="assets/cover.webp" width="100%" alt="BOWEN。香蕉猫抱着电脑，投射出一只半实体、半线框的茶壶在做体检。3D 资产还原：从成品包中原样还原模型、贴图、材质与场景。"></a>
</p>

<p align="center">
  <strong><a href="https://yigenjiao.github.io/Bowen/">个人主页</a></strong> &nbsp;·&nbsp;
  <strong><a href="https://yigenjiao.github.io/Bowen/tools/glb-inspector/">GLB 体检台</a></strong> &nbsp;·&nbsp;
  <a href="#联系">联系我</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Cocos_Creator-3.x-e6480f?style=flat-square" alt="Cocos Creator 3.x">
  <img src="https://img.shields.io/badge/Luna_%2F_Unity-Playable-c98a2b?style=flat-square" alt="Luna / Unity Playable">
  <img src="https://img.shields.io/badge/glTF-2.0-f0e9dc?style=flat-square&labelColor=14110d" alt="glTF 2.0">
</p>

**源文件丢了，资产照样拿得回来。**

手上只有试玩广告（Playable）、WebGL 网页游戏或发布包这样的成品，源工程却找不到了？我把包里的模型、贴图、材质和场景完整还原出来，原来在哪还是在哪，名字都不变，一件不少还给你，导进 Blender / Unity 就能接着用。资产怎么用，由你决定。

> 仅受理具备合法使用权的文件：自有项目，或经权利方授权的素材。

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

每条问题都附带**成因和修复写法**，可以一键定位到出问题的网格。

**能修的直接修**：骨骼矩阵写反、float64 落盘、坏三角形、法线没归一、权重和不为 1、缺 min/max、多余的 buffer uri、黑色顶点色，勾选后点“修复并重新体检”，下载修好的新 GLB。索引越界的三角形会被删掉，留下的小洞可以选择自动补（只在找得到唯一答案时补，UV 沿用周围顶点），补不上的会提示你回建模软件手动补；零缩放节点这类可能是故意设计的，只报告、不乱改。另有法线、UV 棋盘格、顶点色、骨骼权重四种检查视图，也可以导出 Markdown 体检报告附在交付里。

## 服务

| | 能力 | 内容 |
| --- | --- | --- |
| 01 | **资产还原** | 从成品包中完整取出模型、贴图、材质与骨骼，支持 Cocos Creator 3.x、Luna / Unity 等常见 Playable 与 WebGL 打包格式 |
| 02 | **场景还原** | 按原始节点层级、世界坐标和实例复用关系重建场景，摆放原样保留 |
| 03 | **交付校验** | 结构校验、引擎内包围盒与 Blender 逐项对账、多视角渲染比对，附验收记录 |
| 04 | **二次加工（可选）** | 在还原结果上做风格改版、地编调整或 Shader 复刻 |

做过的案例（整场景还原、Shader 效果、主题改版，以及从 8MB 单文件包里还原 3732 个模型）见[个人主页](https://yigenjiao.github.io/Bowen/#cases)。

## 仓库里有什么

```
index.html                       个人主页
tools/glb-inspector/             GLB 体检台（单文件，无需构建）
  samples/                       健康样本 / 故意埋坑的样本 + 生成脚本
assets/                          封面、截图、二维码
.github/cover/                   README 封面的源文件（HTML + three.js），可以重新生成
```

## 联系

手上有拿不出资产的包？发来文件类型、引擎（如果知道）和你想拿到的内容，我先判断能不能还原、需要多久。
仅受理具备合法使用权的文件：自有项目，或经权利方授权的素材。

- **Email**：shiboxun123@gmail.com
- **GitHub**：[@yigenjiao](https://github.com/yigenjiao)
- **微信**：扫下面的二维码

<img src="assets/wechat-qr.jpg" width="180" alt="微信二维码">
