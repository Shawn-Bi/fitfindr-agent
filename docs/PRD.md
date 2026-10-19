# FitFindr MVP PRD v2.2

Oct 18, 2026 · @Shawn Bi

FitFindr 是一个面向美国用户的二手服饰搜索 Agent：用户用一句话或自己的衣橱找到合适的二手单品，并看到如何和已有衣服搭配。本版把注册、首页、我的衣橱三份 PRD 合并为一份，范围收窄到可在一个人几周内做完的 MVP。

## 1. MVP 范围

MVP 只做“买”这一条线：搜索二手单品、管理自己的衣橱、看搭配建议、收藏。卖和社交是另外两个产品，放到后续阶段。

| 功能 | MVP | 说明 |
| --- | --- | --- |
| 邮箱注册、登录、忘记密码 | 做 | 用成熟的登录服务，不自己存密码 |
| 尺码与风格档案 | 做 | 全部可跳过 |
| 文字搜索 + 结果页 | 做 | 6 个平台的真实商品（RapidAPI） |
| 风格卡片筛选 | 做 | Vintage、Y2K、Streetwear 等 |
| 我的衣橱：上传照片 + 填写衣物信息 | 做 | 增删改查，照片必须支持 |
| 单品详情 + AI 搭配建议 | 做 | 就是现有的 suggest\_outfit |
| 收藏 | 做 | 站内收藏 |
| 每个推荐都显示商品图片 | 做 | 用各平台接口返回的商品图 |
| 图片搜索（上传参考图找相似款） | 占位 | 显示“Coming soon” |
| 卖闲置、多平台发布、AI 估价 | 不做 | 大部分平台没有发布接口 |
| 同城 | 不做 | FB Marketplace 商品先进搜索结果，按城市筛选放第二阶段 |
| 好友衣橱、关注、消息 | 不做 | 社交功能，第三阶段 |
| 邮件/短信通知、定时推荐 | 不做 | 第二阶段 |

## 2. 页面清单与核心流程

网站界面统一用英文（目标用户在美国），主题色天蓝色。一套响应式代码同时支持手机和电脑：手机底部导航、单栏；电脑顶部导航、多栏。未登录看 Landing，登录后看 Home。登录后底部导航 4 个入口：Home · Closet · Saved · Profile；桌面端放在顶部。

| 编号 | 页面 | 谁能看 | 作用 |
| --- | --- | --- | --- |
| P1 | Landing | 未登录 | 介绍产品，引导注册或试搜 |
| P2 | Sign up / Log in | 未登录 | 邮箱 + 密码，条款同意 |
| P3 | Profile setup | 新用户 | 尺码、风格、预算，全部可跳过 |
| P4 | Home | 登录后 | 搜索框、风格卡片、为你推荐 |
| P5 | Search results | 所有人 | 商品卡片 + 搭配建议 + 文案 |
| P6 | My Closet | 登录后 | 按分类浏览自己的衣服 |
| P7 | Add item | 登录后 | 上传照片 + 填写衣物信息 |
| P8 | Closet item detail | 登录后 | 这件衣服 + 可以配它的二手商品 |
| P9 | Saved | 登录后 | 收藏的商品 |

新用户主流程：

1. Landing → Get Started
2. Sign up（邮箱 + 密码 + 同意条款）→ 邮箱验证
3. Profile setup（可跳过）
4. My Closet 空状态 → Add your first item → 上传照片 + 填信息 → 保存
5. Home → 输入 “vintage graphic tee under $30” → Search results
6. 结果卡片显示用自己衣橱的搭配建议 → 收藏或跳转原平台购买

游客可以在 Landing 试搜；结果页用通用搭配建议，并提示“注册后用你自己的衣橱搭配”。

## 3. 逐页需求

### P1 Landing

- 顶部：FitFindr logo · How it works · Log in · Get started
- 主标题：Find pieces that fit your wardrobe, not just your search.
- 副标题：Secondhand finds from supported stores, matched to your style, size and budget.
- 一个试搜框（示例 vintage graphic tee under $30）+ Get started 按钮
- 三步说明：Add your closet → Search in plain words → Get matches that go with what you own
- 数据来源条：Searching eBay · Etsy · Depop · Poshmark · Mercari · FB Marketplace

### P2 Sign up / Log in

- 必填：Email、Password（至少 12 位，可显示/隐藏，支持密码管理器）
- 必勾：I agree to the Terms of Service and the Privacy Policy（两个链接可点开）
- 可选，默认关闭：Email me new matches（MVP 只记录选择，暂不发送）
- 登录页：Email + Password + Forgot password；错误提示说清楚是哪里错

### P3 Profile setup（全部可跳过）

- 常穿尺码：上衣、裤装（腰围/长度）、鞋码（US/EU/UK）
- 偏好风格（多选卡片）、偏好颜色、单件预算上限
- 每项一句话说明用途；按钮 Skip for now / Save & continue
- 不收集身高、体重、三围（MVP 用不到）

### P4 Home

- 第一排：Logo · 搜索框 · 相机按钮（点开显示 Coming soon）
- 第二排：风格卡片横向滑动：Vintage · Y2K · Streetwear · Minimalist · Grunge · Cottagecore
- 第三排：Picked for your closet（按衣橱和偏好推荐）；新用户显示“添加衣服后解锁”，并展示各平台的热门单品
- 数据来源条：6 个平台名；某平台额度用完时标 Paused

### P5 Search results

- 顶部显示 Agent 理解到的条件标签：graphic tee · under $30 · size M，每个可点 × 删除
- 商品网格：图片、标题、价格、尺码、成色、平台、收藏心
- 第一件（最匹配）展开：How to wear it with your closet（显示用到的自己衣服缩略图）+ Fit card 文案（可复制）
- 搜不到时：说清楚按哪些条件搜了，给出一键放宽按钮（去掉尺码 / 提高预算）
- 每个商品显示更新时间和 “Price and stock may change on the original site”；可按平台筛选，暂停的平台显示恢复日期

### P6 My Closet

- 顶部：单品总数 · 搜索 · + Add item
- 分类标签：All · Tops · Bottoms · Outerwear · Dresses · Shoes · Accessories，带数量
- 照片网格；空状态：Your closet starts here + Add your first item

### P7 Add item

- 先上传照片（拍照或从相册选），可预览、重拍、删除
- 再填信息（字段见第 4 节）；第二阶段由 AI 根据照片预填，用户确认
- 按钮：Save to closet

### P8 Closet item detail

- 大图 + 衣物信息 + Edit / Delete
- Finds that go with this：横向商品卡片（图片、价格、平台、一句匹配理由）

### P9 Saved

- 收藏商品网格；商品已下架时变灰并标注 No longer available

## 4. 衣橱数据与图片上传

照片和衣物信息都是必做功能：信息越全，Agent 的搭配越准。分类和商品数据对齐，删掉了化妆品，补上了外套和连衣裙。

| 字段 | 必填 | 输入方式 | 例子 |
| --- | --- | --- | --- |
| 照片 photo | 是 | 拍照或上传，JPG/PNG/HEIC，≤ 10 MB | — |
| 名称 name | 是 | 文字 | Baggy straight-leg jeans |
| 分类 category | 是 | 单选 | tops / bottoms / outerwear / dresses / shoes / accessories |
| 颜色 colors | 是 | 多选色块 | dark blue, indigo |
| 风格标签 style\_tags | 否 | 多选卡片 | denim, streetwear, baggy |
| 尺码 size | 否 | 文字 | W30 L32 |
| 品牌 brand | 否 | 文字 | Levi's |
| 季节 season | 否 | 多选 | spring, fall |
| 备注 notes | 否 | 文字 | High-waisted, sits above the hip |

上传规则：服务器端检查格式和大小、去掉照片里的 GPS 等元数据、压缩到 1600 px、生成缩略图；上传失败要提示原因并可重试。照片和衣橱默认只有自己可见。

## 5. Agent 与数据源

商品全部来自通过 RapidAPI 接入的美国二手平台真实数据；产品界面里永远不出现模拟数据。

| 平台 | RapidAPI Host | 免费额度 | 本地熔断线 |
| --- | --- | --- | --- |
| Depop · Poshmark · Mercari | fashion-resale-api.p.rapidapi.com | 50 次/月 | 40 |
| Etsy | etsy-api2.p.rapidapi.com | 50 次/月 | 40 |
| Facebook Marketplace | facebook-marketplace-api.p.rapidapi.com | 50 次/月（硬上限） | 40 |
| eBay | real-time-ebay-data.p.rapidapi.com | 20 次/月（软上限） | 15 |

- **统一格式**：每个平台一个 adapter，把返回清洗成 FitFindr 标准字典 id、title、price、size、platform、url、image\_url（可选 condition、updated\_at）；search\_listings 负责合并、去重、排序。
- **调用优先级**：先调 Fashion Resale API（一次覆盖 3 个平台）；eBay、Etsy、FB Marketplace 放到最后统一联调。
- **开发期用录制数据**：每个接口只真实调用 1–2 次，把原始 JSON 存到 tests/fixtures/；单元测试、Prompt 调试、UI 联调都读这些文件。fixtures 只在开发和测试代码里使用，生产环境不加载。
- **计数与熔断**：每个 host 一个月度计数器（存数据库，每月 1 日清零）。到熔断线后该平台暂停请求：有 24 小时内的真实缓存就用缓存，没有就跳过该平台，并在结果页显示 “eBay results are paused until Nov 1”。不用假数据填补。
- **额度提醒**：4 个接口合计约 170 次/月，只够开发和小范围演示；有真实用户前要升级付费套餐。
- **第三方接口**：这些是 RapidAPI 上的第三方接口，不是平台官方 API；遵守 RapidAPI 和提供方的条款，接口可能变动，需要监控失败率。
- **不改接口形状**：search\_listings 的输入输出保持不变，继续通过 MCP 调用。
- **用衣橱匹配**：结果排序加入衣橱信息（缺什么品类、常见颜色和风格）；尺码（US）和预算（USD）从档案自动带入，用户可删。
- **搜索升级**（第二阶段）：把关键词匹配换成向量搜索，并检查结果品类是否和问题一致。
- **故障提示写给普通用户**：模型不可用时显示 “Styling suggestions are unavailable right now. Your search results still work.”，技术细节只写日志。
- **成本控制**：同一问题的真实结果缓存 24 小时；每个用户每分钟最多 10 次搜索。

## 6. 隐私、合规与诚实展示

- 衣橱、照片、档案默认只有自己可见；Profile 里可以删除单件衣物和整个账户。
- 密码交给登录服务托管，绝不明文保存；API key 只放在服务器环境变量里。
- 只展示真正接入的 6 个平台，不说“全网搜索”；每件商品标注来源平台并链接回原商品页。
- 购买在第三方网站完成；本站不收支付信息。价格和库存以原平台为准。
- 遵守 eBay 和 Etsy 的 API 使用条款（图片展示、缓存时长、来源标注）。
- 服务条款和隐私政策正式上线前需要法律审核；第二阶段做短信时，需单独同意并支持 STOP 退订。

## 7. 技术方案建议

建议用 Supabase 一次解决数据库、登录和图片存储三件事，后端保留 Python，直接复用现有 Agent 代码。

| 层 | 选择 | 理由 |
| --- | --- | --- |
| 前端 | Next.js + Tailwind CSS | 模板多，部署简单 |
| 后端 | FastAPI（Python） | 直接调用现有 run\_agent |
| 数据库 | Supabase Postgres | 衣橱、收藏、档案用 SQL 存 |
| 登录 | Supabase Auth | 邮箱验证、忘记密码都现成 |
| 图片存储 | Supabase Storage | 每个用户只能读写自己的照片 |
| 部署 | Vercel（前端）+ Render（后端） | 都有免费额度 |

数据表：users、profiles(user\_id, sizes, styles, colors, budget)、closet\_items(id, user\_id, photo\_url, name, category, colors, style\_tags, size, brand, season, notes)、saved\_items(user\_id, listing\_id, source, saved\_at)。

接口：POST /search、GET/POST/PATCH/DELETE /closet/items、POST /closet/items/{id}/photo、GET /closet/items/{id}/matches、GET/POST/DELETE /saved、GET/PATCH /profile。

网站开一个新的私有仓库 fitfindr-agent（本地 the project folder）：课程仓库是公开仓库的 fork，GitHub 不允许把它改成私有，产品代码不应公开。把 agent.py、tools.py、mcp\_server.py 等复制过去；每次大改后继续跑 run\_eval.py。环境变量：GEMINI\_API\_KEY、RAPIDAPI\_KEY、EBAY\_API\_HOST、ETSY\_API\_HOST、RESALE\_API\_HOST、FB\_MARKETPLACE\_HOST、SUPABASE\_URL、SUPABASE\_ANON\_KEY、SUPABASE\_SERVICE\_ROLE\_KEY。

## 8. 验收标准

- [ ] 新用户能用邮箱 + 密码注册、验证邮箱、登录；未勾选条款时无法注册
- [ ] Profile setup 每一项都能跳过
- [ ] 能上传一张衣服照片并填写信息；退出重新登录后照片和信息仍在
- [ ] 超过 10 MB 或不支持的格式会被拒绝，并提示原因
- [ ] 搜索 “vintage graphic tee under $30” 返回带图片的结果，每件 ≤ $30
- [ ] 有衣橱时，搭配建议点名衣橱里的至少 1 件衣服（5 次里至少 4 次）
- [ ] 搜不到时不调用模型，并给出可点的放宽建议
- [ ] 收藏后出现在 Saved，重新登录后仍在
- [ ] 所有商品来自 6 个真实平台，带图片和原链接，生产环境不加载 fixtures；未做的功能显示 Coming soon，不是空白页
- [ ] 手机宽度 375 px 下所有页面没有横向滚动；电脑宽度 1280 px 下为多栏布局
- [ ] run\_eval.py 的 5 条标准仍然达标（读 fixtures，不消耗额度）；每个平台计数到熔断线后不再发起真实请求

## 9. 相对 v1 的改动与待确认

| v1 的写法 | v2 的决定 | 原因 |
| --- | --- | --- |
| 注册 PRD 和首页 PRD 各有一个首页 | 未登录 Landing，登录后 Home | 两个首页会让开发不知道做哪个 |
| 页面 A/B 和 A–E 编号重复 | 统一为 P1–P9 | 避免指代混乱 |
| Feed Finder / FitFindr | 统一为 FitFindr | 品牌名一致 |
| 导航中文、文案英文 | 界面全部英文 | 用户在美国 |
| Dashboard 与“我的”两个叫法 | Closet + Profile | 一个概念一个名字 |
| 底部五入口：首页/同城/卖闲置/消息/我的 | Home/Closet/Saved/Profile | 同城、卖闲置、消息暂时没有接口支持 |
| 衣橱分类含化妆品、缺外套 | tops/bottoms/outerwear/dresses/shoes/accessories | 和商品数据对齐，化妆品和穿搭无关 |
| 商品数据无图片 | 标准格式包含 image\_url 和 url | 每个推荐必须有图 |
| 注册时收集身高、体重、三围 | MVP 不收集 | 用不到，增加隐私风险 |

待确认：

- 已确认：只面向美国用户，尺码用 US 体系，价格用 USD。
- RapidAPI 免费额度只够开发和演示：有真实用户前选哪个付费套餐？
- 某个第三方接口停服时，用哪个备用接口？

## 10. 开发前准备

大部分准备已完成；剩下的交给 Claude Code 按 CLAUDE.md 和启动指令完成，只有 3 件事需要你亲手做。

| 事项 | 状态 | 谁来做 |
| --- | --- | --- |
| GitHub、Vercel、Render 账号 | 已有 | — |
| Gemini API key | 已有（沿用作业的） | — |
| RapidAPI key 和 4 个 host | 已有 | 你填进 .env |
| 10 张衣服照片（wardrobe photos/） | 已有 | — |
| Logo 和 favicon | 已有（价签 + FF 图形，logo.svg、favicon.svg） | — |
| 新建私有仓库 fitfindr-agent 并复制 Agent 代码 | 待做 | Claude Code |
| 把 PRD、CLAUDE.md、原型 HTML、logo 放进项目文件夹 | 已完成 | Claude（已直接放进 FitFindr-Agent） |
| .env.example、.gitignore、目录结构、RapidAPI 计数器 | 待做 | Claude Code |
| 服务条款和隐私政策模板（标注 Draft） | 待做 | Claude Code |
| 调用 Fashion Resale API 1–2 次并录制 fixtures | 待做 | Claude Code，发请求前先问你 |
| 安装 Node.js LTS | 待做 | 你（Claude Code 会先检查） |
| 注册 Supabase 并新建项目 | 待做 | 你（约 5 分钟；建表 SQL 由 Claude Code 写） |
| 律师审核条款 | 有真实用户后 | 你 |
