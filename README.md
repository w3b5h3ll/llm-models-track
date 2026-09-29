# Model Watch · 自选模型观察站

定时更新你关注的模型参数，并通过 GitHub Pages 展示。**默认优先官方规格**，保留聚合平台参数作对照。纯 Python 标准库采集 + 原生 HTML/CSS/JavaScript，不需要前端构建、服务器或模型推理调用。

## 现在的数据来源

OpenRouter 负责发现关注名单中的型号与新版本；`official_sources.json` 将已核实的精确型号关联到官方文档或官方模型卡。每次运行会重新获取这些官方页面并解析，不是把今天的数值写死。

本次初始核对覆盖 **15 / 20** 个型号：

| 官方来源 | 覆盖型号 | 说明 |
| --- | --- | --- |
| OpenAI 模型页 | GPT-6 Astra、Sol、Luna | 官方 API 规格，部分功能受端点/推理模式限制 |
| Anthropic 模型参数表 | Claude Opus 5.5、Sonnet 5.5 | 按官方 API 模型 ID 匹配表格列 |
| DeepSeek 参数页 | V4.1 Flash | 官方调用 ID 当前为 `deepseek-flash`，每次验证版本映射 |
| Z.ai 模型页 | GLM 5.3、Flash、FlashX | 官方 Model API |
| Kimi 快速入门 | Kimi K3 | 没有明确列出的数值不推算 |
| 阿里云 Model Studio | Qwen3.8 Max 0902、Flash、Omni Flash | 官方托管 API 规格，区域以原文为准 |
| Qwen 官方 Hugging Face 模型卡 | Qwen3.8 27B、2.4T A95B | 开源权重，原生上下文与可扩展上下文分开保存 |

以下 **5** 项暂未核实独立官方规格，页面明确标为“平台规格”：GPT-6 Astra / Sol / Luna Pro、Qwen3.8 Max Prime、Grok 4.7。前三者对应的独立 OpenAI 页面本次返回 404，不能套用基础型号；xAI 文档访问超时；Prime 尚未找到明确对应来源。后续可在配置里为它们添加经过核对的官方规则。未配置官方规则的条目不会被自动猜测或自动认定为官方。

### 不混用不同渠道的字段

- 官方规格与平台规格是独立记录。有官方资料的模型，默认整条采用官方规格；官方缺失的字段不会用平台值补齐。
- 每个官方字段保存 `url`、原文 `quote`，数值另保留 `reported`。详情可展开证据，并对照两个渠道的上下文、最大输入、最大输出。
- “未列出”表示当前核对的官方页面没有提供该字段，不代表厂商所有文档都没有公布，也不表示不支持。
- Qwen3.8 Omni Flash 的最大输入按模式分别记录：思考 / 非思考。不会取较大值作为通用上限。
- 模型卡的原生上下文与可扩展上下文分开记录。扩展能力可能需要 RoPE/YaRN 等部署配置，不能视为默认服务能力。
- 官方页面使用 `1M` / `128K` 等简写时保留原文，按十进制展开的数字仅用于排序，不宣称是官方公布的精确 token 数。
- Claude 官方 Models API 有 `max_input_tokens` 字段，但本版本未接入需要认证的官方 API，只读取公开文档；没有把 API 文档中的示例数值当成真实规格。
- 能力标记表示来源声明支持，不是质量评分；通过工具调用图片生成工具，不等于模型原生输出图片。

### 抓取失败如何处理

网络失败、精确型号身份不符、页面结构变化、同字段出现冲突值时，该官方条目解析失败：有同型号、同来源的旧证据时保留并标为“官方旧快照”；否则明确回退到平台规格。不会把缺失数据当作“不支持”，也不会把旧型号的官方参数套到新型号。

每次运行生成 `data/checks.json`，记录本次检查时间、各型号的成功/失败/未配置状态。它通过 Actions artifact 传递给 Pages，不写入 Git，避免只有检查时间变化也产生提交。`models.json` 中的 `changed_at` 是数据变更观察时间，`official.evidence_updated_at` 是官方证据最后变化时间；都不是每次检查时间。官网措辞变化也可能引起证据更新和提交。

## 字体

中文使用思源黑体（Source Han Sans SC），英文使用 Inter，模型 ID 和代码使用 JetBrains Mono。字体以 WOFF2 随站点发布，无需访问字体 CDN，也不依赖访问者本机安装。常用界面字符优先加载小字集，其他字符按需加载完整字库。字体来源、版本与许可证见 `assets/fonts/README.md`。

## 设计

参考 IBM Carbon 的数据表格信息组织规范，保留原生 HTML/CSS/JavaScript 实现：紧凑概览、统一筛选工具栏、固定表头、数字右对齐、来源状态标签，以及可连续切换模型的非模态详情侧栏。未引入 Carbon 组件依赖。

## 网页功能

- 搜索模型名称 / ID，按厂商和输入能力、工具调用、推理筛选。
- 按上下文或最大输出排序。
- 选择“优先官方”或“聚合平台”规格视图；统计与筛选随视图改变。
- 单独展示最大输入、最大输出、上下文；有模式限制或扩展条件时分别标注。
- 点击模型名称查看来源、检查状态、官方原文证据及平台参数对照。
- 手机布局支持参数表横向滚动；无结果、读取失败和重试都有对应提示。

## GitHub 与 Pages

目标仓库：[w3b5h3ll/llm-models-track](https://github.com/w3b5h3ll/llm-models-track)。

1. 将本目录的**内容**上传到仓库根目录，包含隐藏目录 `.github`。不要再套一层 `model-watch` 文件夹。
2. 在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
3. 打开 **Actions → Update watched models → Run workflow**。
4. 成功后从 `deploy` 任务或 **Settings → Pages** 打开实际站点 URL，通常为 `https://用户名.github.io/仓库名/`。

私有仓库使用 Pages 受账户套餐与站点可见性设置影响。模板已本地验证，尚未在你的 GitHub 仓库部署。

### Actions 做了什么

`.github/workflows/update-models.yml` 每天北京时间 **09:17** 运行，也支持手动触发；修改关注名单、采集代码、官方规则、网页或数据会触发运行。

1. `checkout` 下载仓库，准备 Python，运行测试。
2. 获取聚合目录并筛选关注型号，重新采集已配置的官方页面。
3. 生成 JSON、Markdown、检查报告；参数或证据变化时用内置 `GITHUB_TOKEN` 提交数据。
4. 把包含最新检查报告的数据作为 artifact 传给部署任务。
5. 部署任务获取网页资源与最新数据，发布到 GitHub Pages。

同一工作流包含采集和部署，不依赖机器人提交再次触发 `push`。公开目录查询不调用模型推理；GitHub Actions 用量按账户规则计费。

只有默认分支运行定时任务，实际启动可能延迟。公开仓库连续 60 天没有活动可能被 GitHub 自动停用定时任务，请留意 Actions 状态；每次没有数据变化的检查不会自动产生仓库提交。分支保护或组织策略若禁止机器人写默认分支，提交会失败，需要管理者调整策略或采用 PR 工作流；不会强制推送。

Pages 尚未启用时，采集可以成功而部署失败，启用后重新运行。目录采集失败或关注规则完全匹配不到模型时，整次采集失败，不发布；单个官方来源失败则保留旧证据/回退平台并发布明确的检查状态。

## 管理关注名单

`watchlist.json` 示例：

```json
{
  "source": "openrouter",
  "official_sources": "official_sources.json",
  "models": [
    {"provider": "deepseek", "id": "deepseek/deepseek-v4.1-flash"},
    {"provider": "openai", "match": "openai/gpt-6-*", "exclude": ["*:*"]},
    {"provider": "anthropic", "match": "anthropic/claude-opus-*", "exclude": ["*:*", "*preview*", "*latest*"], "latest": 1}
  ]
}
```

- `id`：与目录 ID 精确匹配。
- `match`：通配符匹配系列，`exclude` 排除批处理/免费等渠道变体。
- `latest: 1`：选择最新收录的一项，以目录 `created` 日期为准，不猜测模型版本号大小。
- `latest_family`：通过一个正则捕获组提取系列。当前 Grok 规则按系列首次收录时间仅保留最新数字系列及其变体，排除 Build 和旧系列。旧系列新增变体不会仅因时间较新而挤掉新系列。
- 系列发现仍以 OpenRouter 收录为边界，不保证与厂商发布同步。新型号没有官方规则时先明确展示平台规格，需核实官方页面后添加映射。

也保留 Models.dev 目录适配器（`source: "models.dev"`），但模型 ID 和 provider 格式不同，切换时需要同步调整关注名单与官方映射。它的线上访问本次未验证，不会自动混用两个目录源。

## 官方规则的维护

`official_sources.json` 按精确模型 ID 配置 URL、官方 ID、渠道口径、页面身份断言及逐字段提取规则。字段应有可定位的官方原文证据；不要仅因名称相近就共享参数。页面结构或语义发生变化时，应查看失败报告，核对原文再修改规则。

数字提取保存原始单位与证据。对于只看到了请求示例的 `max_tokens`、评测脚本的 token 限制或建议输出预算，不要当成模型最大输出上限。

## 本地运行与预览

Python 3.11+，无额外依赖。在项目根目录运行：

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/update_models.py
python3 -m http.server 8000 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8000`。不要双击 HTML，本地文件模式无法读取 JSON。更新脚本也支持 `--config /path/to/watchlist.json --output-dir /path/to/data`。

## 参考

- [GitHub Actions 定时任务](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [OpenRouter 模型目录](https://openrouter.ai/api/v1/models)
- [Claude Models API](https://platform.claude.com/docs/en/api/models/list)
- 各型号官方 URL 与原文证据保存在 `official_sources.json` 和 `data/models.json` 中。
