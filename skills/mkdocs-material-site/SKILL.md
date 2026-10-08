---
name: mkdocs-material-site
description: |
  mkdocs-material 文档站的搭建与维护：mkdocs.yml 与 docs/ 结构、用 mkdocs-static-i18n 做中英双语、
  GitHub Pages 部署管道与自定义域名的归属陷阱、中文标题锚点、favicon 与页眉 logo、
  CHANGELOG 内嵌、本地构建环境、写正文的核对纪律，以及给 PR 配截图的通用做法。
  适用任何用这套技术栈的仓库（多个仓库共用同一套踩坑结论）。
  Triggers: "文档站", "文档页面", "写文档", "补文档", "docs site", "mkdocs", "mkdocs.yml",
  "material", "mkdocs-static-i18n", "双语文档", "英文文档", "文档 i18n",
  "GitHub Pages", "Pages", "自定义域名", "custom domain", "deploy-pages",
  "deploy-docs", "部署文档", "mkdocs build", "--strict", "锚点", "anchor", "slugify",
  "favicon", "图标", "页眉", "header logo", "CHANGELOG 文档", "界面截图", "README 截图".
agent_created: true
---

# mkdocs-material 文档站

用 mkdocs-material + GitHub Pages 搭文档站的通用套路，以及一套**只有踩过才知道**的坑。
大部分坑在框架层面，换仓库一样会踩。

## 最小结构

```
<repo>/
├── mkdocs.yml          # 唯一配置：主题、i18n、nav、markdown 扩展
├── docs/               # 中文（默认语言）
│   ├── *.md
│   ├── assets/images/  # favicon、页眉 logo
│   ├── stylesheets/    # 少量样式覆盖
│   └── en/             # 英文，与上层一一对应
└── .github/workflows/deploy-docs.yml
```

- **`nav` 是唯一的目录来源**：文件放在 `docs/` 下但不写进 `nav`，就不会出现在站点上。
- 构建产物在 `site/`，**记得进 `.gitignore`**（mkdocs 不会替你加）。
- 如果仓库本来就有 `docs/` 目录放截图之类，先确认没有别的东西依赖它 —— 复用目录名可以避免搬家，但要检查一遍。

## 双语：mkdocs-static-i18n

mkdocs-material **本身不带多语言**（这点和 VitePress 不同），要装插件：

```bash
pip install mkdocs-material mkdocs-static-i18n
```

```yaml
plugins:
  - search
  - i18n:
      docs_structure: folder        # 默认语言在 docs/*.md，其他语言在 docs/<locale>/
      languages:
        - locale: zh
          default: true
          name: 中文
        - locale: en
          name: English
          nav_translations:          # nav 里的标题逐条翻译
            首页: Home
            使用指南: User Guide
```

页眉会出现语言切换器，`hreflang` 互指也由插件生成。

### 缺翻译是**静默回落**，不是报错（实测 2026-10-08）

这条最容易翻车：只写 `docs/xxx.md`、不写 `docs/en/xxx.md`，构建**退出码 0、连告警都没有**。
英文站点会在**同样的路径**下**直接渲染中文内容** —— 英文导航列着英文标题，点进去是中文页面。

**没有任何东西会替你发现。** 同样地，页面不在 `nav` 里时 mkdocs 只打 INFO 级日志，`--strict` 也不失败。

所以中英成对只能自己数：

```bash
diff <(cd docs && find . -name '*.md' -not -path './en/*' | sort) \
     <(cd docs/en && find . -name '*.md' | sort)
# 输出为空才是一一对应
```

## 部署到 GitHub Pages

workflow 模板（`actions/upload-pages-artifact@v3` + `actions/deploy-pages@v4`）：

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
    paths: ["docs/**", "mkdocs.yml", ".github/workflows/deploy-docs.yml"]
  workflow_dispatch:

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read            # 只 clone + pip install + build，不需要写权限
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false   # 别把 token 留给构建期的第三方代码读
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install mkdocs-material mkdocs-static-i18n
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      pages: write              # 只有这一层需要发布权限
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

`upload-pages-artifact` 走的是 runner 注入的 runtime token，**不需要** `pages: write`，
所以 build job 收成 `contents: read` 是安全的。

`--strict` 意味着**任何告警都会让 CI 红**。本地先跑通再推。

### 自定义域名：先搞清楚归谁，别急着填

GitHub Pages 有两种模型，**填错会直接报错**：

| 模型 | 域名挂在哪 | 项目站点地址 |
|---|---|---|
| 用户站点 | 仓库 `<user>.github.io` 的 CNAME | 自动继承 → `<域名>/<仓库名>/` |
| 项目站点自持 | 该仓库自己的 Pages 设置 | `<域名>/` |

**如果是用户站点持有域名**（常见于一个自定义域名下挂多个项目站点），那么：
- 该账号下**每个**项目仓库都自动挂在 `<域名>/<仓库名>/` 下；
- 项目仓库的 Pages 设置里**不要**填这个域名 —— 会报
  `The custom domain is already taken by another repository in your account`；
- 只要把 Pages 的 **Source 设成 GitHub Actions** 就够了，`mkdocs.yml` 的 `site_url` 直接写
  `https://<域名>/<仓库名>/`。

判断方法：

```bash
# 项目页面若 301 跳到自定义域名，说明是用户站点持有的
curl -sI https://<user>.github.io/<repo>/ | grep -i location

# 看用户站点仓库有没有 CNAME
gh api repos/<user>/<user>.github.io/contents/CNAME --jq '.content' | base64 -d
```

### 首次部署报 404 的两种原因

`deploy-pages` 报 `Failed to create deployment (status: 404) ... Ensure GitHub Pages has been enabled`：

1. **Pages 还没启用**，或 Source 不是 GitHub Actions —— 去 Settings → Pages 改。
2. 改完之后**不用重新跑整个 workflow**：`gh run rerun <run-id> --failed` 即可，
   build job 的产物还在，只重跑 deploy（实测 9 秒过）。

### 验证部署

```bash
B=https://<域名>/<仓库名>
for p in "" "en/" "guide/getting-started/" ; do
  printf '%-28s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' $B/$p)"
done
# 静态资源也要查，别只看首页
curl -s -o /dev/null -w '%{http_code}\n' $B/assets/images/favicon.png
```

## 坑

### 中文标题的锚点是按位置编号的

mkdocs 默认 slugify 会把中文标题削成 `_1`、`_2` 这种**按位置递增**的 id ——
往文档上面加一个标题，**所有锚点全部错位**。换成保留 Unicode 的实现：

```yaml
markdown_extensions:
  - toc:
      permalink: true
      slugify: !!python/object/apply:pymdownx.slugs.slugify {kwds: {case: lower}}
```

改完之后 `## 字体` 的锚点才是稳定的 `#字体`，可以放心写 `[见字体](docker.md#字体)`。
（`pymdownx` 随 mkdocs-material 一起装，不用额外加依赖。）

### favicon 和页眉 logo 是**两处**，别只改一处

```yaml
theme:
  favicon: assets/images/favicon.png   # 浏览器页签
  logo: assets/images/logo.png         # 页眉标题左边那个
```

只设 `favicon` 的话，页眉挂的还是 Material 自带的默认 logo —— 用户会说「图标没变」。
反过来也一样。两处都要设。

路径都相对 `docs/`；放在 `docs/assets/images/` 正好覆盖主题自带的那张 favicon，产物里不会有两个。

### 站点图标多半是「白底方图」，直接当页眉 logo 会是一块白方块

很多项目的 PWA 图标是**近白底的方图**（不是透明底的标记）。查一下：

```python
from PIL import Image
im = Image.open('favicon-512.png').convert('RGBA')
w, h = im.size
trans = sum(1 for y in range(h) for x in range(w) if im.getpixel((x, y))[3] < 10)
print('透明像素', trans, '共', w * h)   # 透明占比很小 → 是白底方图
```

Material 的顶栏是深色的（`primary: black` 时两种配色都是），白方块压上去很难看。
做法：**取亮度当 alpha、颜色统一成白** —— 深色笔迹变成不透明浅色笔迹，白底变全透明。

调 alpha 曲线有两个**方向相反**的坑，都踩过：

| 做法 | 结果 |
|---|---|
| 只反转、不额外处理 | 缩到 24px（Material 页眉里 logo 的实际尺寸）**笔迹洗淡发虚** |
| 直接提 alpha（gamma < 1） | **底色被一起抬起来**，整块泛白，又变回一块浅色砖 |
| 按原图底色/笔迹的**实际区间归一化**后再留一点中间调提权 | ✅ |

改完**按 `deviceScaleFactor` 放大截图**看实际 24px 的效果 —— 泛白那版就是靠放大图发现的。

### 内嵌 CHANGELOG 时，workflow 必须监听它

想不手抄更新日志，用 snippets 直接嵌：

```yaml
markdown_extensions:
  - pymdownx.snippets:
      base_path: ["."]        # 相对仓库根，所以构建必须在仓库根跑
```

```markdown
# 更新日志

--8<-- "CHANGELOG.md"
```

两个连带影响：

1. `deploy-docs.yml` 的触发路径里**要加 `CHANGELOG.md`** —— 否则上游更新了日志站点不会重建。
   别把这条当冗余删掉。
2. 嵌进来的多半是 semantic-release 的原始产物，版本号是 H1 且整行是链接，照原样渲染是
   **一串紫色大标题**。用 `extra.css` 压回正文层级（给外层 div 加个 class 再写作用域规则）。

### `site/` 不会自动进 `.gitignore`

mkdocs 不会替你加。忘了加的话构建产物会混进提交。同理 `docs/.vitepress/` 之类别的工具缓存也不要漏。

## 本地构建环境

**用独立的临时 venv，不要污染项目已有的 venv**（项目 venv 里通常没有 mkdocs，也不该往里装）：

```bash
python -m venv /c/Users/13963/AppData/Local/Temp/mkdocs-venv
/c/Users/13963/AppData/Local/Temp/mkdocs-venv/Scripts/python.exe -m pip install mkdocs-material mkdocs-static-i18n
```

之后在**仓库根**跑（snippets 的 `base_path` 依赖 cwd）：

```bash
.../python.exe -m mkdocs build --strict    # 验证
.../python.exe -m mkdocs serve             # 本地预览，改文件自动重建
```

CI 装的是同样的两个包，本地过了 CI 基本也过。

## 写正文的核对纪律

**不要照抄 README。** 实测过好几个仓库的 README 与代码不符 —— 广告了实际不支持的文件格式、
路由在但后端接口被注释掉、空壳页面。文档站要按**代码**重写，不是搬运。

写之前回代码里取事实：

| 要写什么 | 去哪看 |
|---|---|
| 参数名、默认值 | 前端表单组件的 `data()`；后端请求模型 |
| 界面上的措辞（中英） | i18n 文案文件 —— **文档用词要和界面一致** |
| 语法/标记的精确语义 | 后端实现里的正则（别凭印象写「三个或更多」） |
| 并发、限流、超时、TTL 等数字 | 后端常量，别凭记忆写 |

**写了具体数字就要能指出它在哪一行。** 拿不准的宁可写定性描述。

## 给 PR 配截图

GitHub **没有**给 token 用的图片上传接口（网页版拖拽走的是网页会话专属端点，token 调用 404）。
可行做法只有「推到某个分支 + 用 raw 链接引用」：

```bash
git worktree add <临时目录> <图片分支>
# 放图到 <slug>/ 下，commit、push
# 引用：https://raw.githubusercontent.com/<owner>/<repo>/<commit-SHA>/<slug>/<name>.png
git worktree remove <临时目录>
```

- **用 commit SHA 而不是分支名**钉住链接 —— 分支被 force-push 时链接不会跟着变。
- 但 SHA 只防改写、**不防删分支**：分支/标签/PR ref 都不指向该 commit 时会被 GC，链接 404。
  **图片分支要长期保留。**
- 仓库若已有约定（如固定的 `pr-assets` 分支、或 `<slug>/` 分目录），**跟着现有约定走**，别另起一个。
- 更稳的位置是 **PR 头分支本身**：只要该提交还是 PR 当前头，`refs/pull/<n>/head` 就引用它，
  删分支、合并都不会失效；代价是图会进 PR 的 Files changed。

### 截图要截**生产构建**，不是开发服务器

开发环境常有只对开发者显示的控件（比如「本地全量预览」这类按钮，靠
`process.env.NODE_ENV === 'development'` 渲染）。用户根本看不到，不该出现在截图里。

**先 grep 一遍确认**有没有这类开发专用 UI，再决定怎么截。

### 无头驱动比浏览器面板可靠

桌面 App 的浏览器面板在**窗口被其他窗口挡住时不绘制**：截图超时、`innerWidth` 为 0、
eval 超时。用无头 Playwright 最稳（项目里若已有 `e2e/`，`NODE_PATH=<repo>/e2e/node_modules` 就能复用）：

```js
const { chromium } = require('playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(URL, { waitUntil: 'networkidle' });
await page.screenshot({ path: 'out.png' });
```

三条容易忘的：

1. **开屏动画**：`addInitScript` 里设好跳过标记（如 `localStorage.bookSplashShown = 'true'`）。
2. **第三方挂件**：客服气泡、统计脚本是运行时注入的，不属于产品界面 —— 用 `page.route()` 挡掉，
   和旧图才可比。
3. **等真正的结果**，别等占位图：`waitForFunction` 里排除占位图 URL，再 `img.decode()` 等解码。

窄屏 / 手机视口逐个人工核对，别只跑完 e2e 就报完成。
