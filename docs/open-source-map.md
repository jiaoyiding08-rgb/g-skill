# 开源补全案例与核对记录

核对日期 2026-09-18。来源是官方规范、官方文档、作者仓库及论文。以下 GitHub main/release 链接会变化；尚未固定上游 commit。真实集成前应锁定具体版本、保存许可证及依赖清单。

## 各自补什么

| G 模块 | 来源 | 借鉴方式 | 当前交付 | 尚未接入 |
|---|---|---|---|---|
| Repeat | PM4Py | 用独立事件实例观察稳定路径和返工 | episode/run 模型、去重检查、成熟度限制 | 流程挖掘算法、自动语义聚类 |
| Repeat | OpenAdapt/openadapt-flow | 示范是样本，效果需独立核验 | 产物与真实效果分开；E1 核验参考 | 录屏、操作回放、工作流编译器 |
| Review/Lab | Langfuse | 将运行、事件、结果和评估关联 | 本地 trace、快照、结果表 | Langfuse 服务或 SDK |
| Review | Reflexion | 失败生成可复查的候选规则 | 规则来源、范围、反例和复查条件 | 自动策略学习或已证实的人类收益 |
| Lab | Promptfoo | 同样输入比较不同版本并断言 | Python provider/assertion、两类配置 | 完整 CLI 与真实模型试验 |
| Lab | DSPy/GEPA | 基于开发反馈提出候选版本 | 接口、隔离和审批要求 | SDK、优化轮次、自动发布 |

没有用新项目名覆盖原 dbskill 的贡献。六个原始来源与具体删改另见 source-lineage.md。

## 许可与实际边界

PM4Py 许可入口为 AGPL-3.0。OpenAdapt 系列需查看具体仓库和第三方组件边界。Langfuse 核心与商业目录有不同条款。Promptfoo、DSPy 和 Reflexion 的 MIT 信息应在将来锁定版本时再次核对。这里是工程来源记录，不是商业发布的法律意见。

本包没有把这些项目装成一个大工具集合。已做的补全主要是协议和测试的实现；无人观察、持续聚类、自动优化等仍标成未来能力。

## 可追溯来源

### S01 · Agent Skills 规范

https://agentskills.io/specification

核对内容：Skill 文件结构、name/description 与相对引用。本版处理：规范采用；安装副本自包含。

### S02 · Codex Skills 文档

https://learn.chatgpt.com/docs/build-skills

核对内容：项目和用户级 .agents/skills 安装位置。本版处理：安装器采用显式路径；未操控用户客户端。

### S03 · Promptfoo Python provider

https://www.promptfoo.dev/docs/providers/python/

核对内容：call_api(prompt, options, context) 接口。本版处理：本包自行编写 Python 适配，直接函数已测。

### S04 · Promptfoo Python assertions

https://www.promptfoo.dev/docs/configuration/expected-outputs/python/

核对内容：get_assert 与 pass/score/reason。本版处理：机械评分适配已写；语义评分仍人工。

### S05 · PM4Py

https://github.com/process-intelligence-solutions/pm4py

核对内容：按 case/activity/timestamp 观察流程、分支和返工。本版处理：只借方法，未导入库。

### S06 · PM4Py LICENSE

https://raw.githubusercontent.com/process-intelligence-solutions/pm4py/release/LICENSE

核对内容：AGPL-3.0。本版处理：记录许可约束；没有直接集成。

### S07 · OpenAdapt

https://github.com/OpenAdaptAI/OpenAdapt

核对内容：从示范中提取可重用操作。本版处理：只借方法，未录屏/控制电脑。

### S08 · openadapt-flow

https://github.com/OpenAdaptAI/openadapt-flow

核对内容：工作流、效果核验与示范边界。本版处理：只借架构；不声称示范一次就可靠自动化。

### S09 · openadapt-flow LICENSE

https://raw.githubusercontent.com/OpenAdaptAI/openadapt-flow/main/LICENSE

核对内容：作者编写包代码的 MIT 条款，部分第三方边界另列。本版处理：复用前必须按具体目录审查，不能概括整个仓库。

### S10 · Langfuse LICENSE

https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE

核对内容：核心 MIT，ee 等目录许可例外。本版处理：只借运行/事件/评分关联，不安装服务。

### S11 · Reflexion

https://github.com/noahshinn/reflexion

核对内容：用反馈形成下一次可用的文字记忆。本版处理：借候选规则设计，未把研究结果外推为人类成效。

### S12 · Reflexion 论文

https://arxiv.org/abs/2303.11366

核对内容：Language Agents with Verbal Reinforcement Learning。本版处理：方法来源。

### S13 · Promptfoo LICENSE

https://github.com/promptfoo/promptfoo/blob/main/LICENSE

核对内容：MIT。本版处理：可选工具，未复制源码。

### S14 · Promptfoo package.json

https://raw.githubusercontent.com/promptfoo/promptfoo/main/package.json

核对内容：核对时源码版本 0.123.0、Node >=22.22.0。本版处理：npm 查询超时；CLI 未执行。

### S15 · DSPy

https://github.com/stanfordnlp/dspy

核对内容：LM 程序与优化器，MIT。本版处理：仅下一阶段接口设计。

### S16 · GEPA 文档

https://dspy.ai/api/optimizers/GEPA/overview/

核对内容：基于评价与文字反馈生成候选。本版处理：未调用优化器。

### S17 · Chat Completions 请求参考

https://platform.openai.com/docs/api-reference/chat/create

核对内容：messages 与 max_completion_tokens 请求格式。本版处理：兼容 adapter；未调用任何收费模型。
