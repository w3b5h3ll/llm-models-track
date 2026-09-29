# 关注模型参数

数据最后变更采集时间（UTC）：2026-09-29T15:24:03+00:00

每次检查的时间见 Actions 日志；下表仅在数据变化时更新。未知表示来源未提供。

| 模型 ID | 上下文 tokens | 最大输入 | 最大输出 | 输入模态 | 输出模态 | 工具调用 | 推理 | 规格来源 |
| --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| anthropic/claude-opus-5.5 | 1000000 | 未知 | 128000 | text, image | text | 是 | 是 | [官方](https://docs.anthropic.com/en/docs/about-claude/models/overview) |
| anthropic/claude-sonnet-5.5 | 1000000 | 未知 | 128000 | text, image | text | 是 | 是 | [官方](https://docs.anthropic.com/en/docs/about-claude/models/overview) |
| deepseek/deepseek-v4.1-flash | 1000000 | 未知 | 384000 | text, image | 未知 | 是 | 是 | [官方](https://api-docs.deepseek.com/quick_start/pricing/) |
| moonshotai/kimi-k3 | 1000000 | 未知 | 未知 | text, image, video | 未知 | 未知 | 是 | [官方](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart) |
| openai/gpt-6-astra | 1050000 | 未知 | 128000 | text, image | text | 是 | 是 | [官方](https://developers.openai.com/api/docs/models/gpt-6-astra) |
| openai/gpt-6-astra-pro | 1050000 | 未知 | 128000 | file, image, text | text | 是 | 是 | [聚合平台](https://openrouter.ai/api/v1/models) |
| openai/gpt-6-luna | 1050000 | 未知 | 128000 | text, image | text | 是 | 是 | [官方](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| openai/gpt-6-luna-pro | 1050000 | 未知 | 128000 | file, image, text | text | 是 | 是 | [聚合平台](https://openrouter.ai/api/v1/models) |
| openai/gpt-6-sol | 1050000 | 未知 | 128000 | text, image | text | 是 | 是 | [官方](https://developers.openai.com/api/docs/models/gpt-6-sol) |
| openai/gpt-6-sol-pro | 1050000 | 未知 | 128000 | file, image, text | text | 是 | 是 | [聚合平台](https://openrouter.ai/api/v1/models) |
| qwen/qwen3.8-2.4t-a95b | 262144 | 未知 | 未知 | 未知 | 未知 | 未知 | 是 | [官方](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B/raw/main/README.md) |
| qwen/qwen3.8-27b | 262144 | 未知 | 未知 | text, image, video | 未知 | 未知 | 是 | [官方](https://huggingface.co/Qwen/Qwen3.8-27B/raw/main/README.md) |
| qwen/qwen3.8-flash | 1000000 | 未知 | 未知 | 未知 | 未知 | 是 | 是 | [官方](https://www.alibabacloud.com/help/en/model-studio/text-generation-model) |
| qwen/qwen3.8-max-0902 | 1000000 | 未知 | 未知 | 未知 | 未知 | 是 | 是 | [官方](https://www.alibabacloud.com/help/en/model-studio/text-generation-model) |
| qwen/qwen3.8-max-prime | 1000000 | 未知 | 131072 | text, image, video | text | 是 | 是 | [聚合平台](https://openrouter.ai/api/v1/models) |
| qwen/qwen3.8-omni-flash | 1000000 | 思考 983616；非思考 991808 | 131072 | text, image, audio, video | text | 是 | 是 | [官方](https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash) |
| x-ai/grok-4.7 | 500000 | 未知 | 450000 | text, image, file | text | 是 | 是 | [聚合平台](https://openrouter.ai/api/v1/models) |
| z-ai/glm-5.3 | 1000000 | 未知 | 128000 | text | 未知 | 是 | 是 | [官方](https://docs.z.ai/guides/llm/glm-5.3) |
| z-ai/glm-5.3-flash | 1000000 | 未知 | 128000 | text, image, video, file | text | 是 | 是 | [官方](https://docs.z.ai/guides/vlm/glm-5.3-flash.md) |
| z-ai/glm-5.3-flashx | 1000000 | 未知 | 128000 | text, image, video, file | text | 是 | 是 | [官方](https://docs.z.ai/guides/vlm/glm-5.3-flash.md) |

优先显示同型号的官方规格，官方未列字段不使用平台值补齐。未核实官方规格的条目标为聚合平台。

K/M 为官方简写时保留原文，数值按十进制展开用于排序。Qwen 权重模型显示原生上下文，扩展能力见 JSON / 网页详情。

原始平台规格及逐字段官方证据见 models.json；每次检查状态见 checks.json（随网页发布）。
