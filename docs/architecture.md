# 设计落地与范围

依据用户提供的《G_Skill_开发设计文档_v0.1.md》最后一节实现。原文哈希见 source-manifest.json。本版目标是 Phase 0 与部分 Phase 1，不宣称完成完整系统。

## 分层

**Skill 层**。六个独立的判断流程，由支持 SKILL.md 的宿主模型执行。默认输出行动卡；API/评测输出 Envelope。

**Kernel 层**。统一字段、声明式路由、持久记录和状态约束。模型只提议写入。CLI/API 保存后返回真实回执。

**核验层**。当前实际可用的是本地文件 E1 核验。完成条件必须明确限定为文件存在、哈希一致。人工内容评审和 E2/E3 外部结果只有接口定义。

**评估层**。Python 可直接跑离线机械检查。Promptfoo 配置和 Python 适配已提供。真实模型 API 为显式开启的可选路径；本次未调用。

## 原文到交付物

| 原设计章节 | 对应文件 | 实现状态 |
|---|---|---|
| 2 宪法 | kernel/CONTRACT.md | 已写入六个 Skill 的共同约定 |
| 4 Kernel | protocol.schema.json、validation.py | 已实现格式与部分跨字段检查 |
| 5–10 六模块 | skills/g-*/SKILL.md | 已编写，宿主行为待实测 |
| 11 原始映射 | docs/source-lineage.md | 逐项核对源文件并记录指纹 |
| 12 开源补全 | docs/open-source-map.md | 来源核对与集成边界 |
| 14 SQLite | schema.sql、storage.py | 运行、快照、E1、候选规则/簇、导出/删除可用 |
| 15 交接 | runtime/handoff.py | 检查提议，不调度其他 Agent |
| 16/19 评测 | evals/、tests/ | 72 合成题与程序测试，效果未测 |
| 17 G Index | 尚未实现 | 与私人记录分离，后续单独设计 |
| 18 阶段路线 | docs/roadmap.md | 未将未来能力冒充当前能力 |

## 保留与修订

保留动作、完成标准、证据、现实反馈这四个核心。保留原设计的六个模块名字和职责。

细化了几个容易误用的部分。行动卡生成与行动完成分别记录。实验做完与假设成立分别记录。预算到期后继续检查硬风险。没有事前快照时只做回顾，不假装还原预测。重复聚类依赖独立 episode；多次编辑同一个东西只能算一个实例。

本地授权布尔值和确认参数用于原型流程检查，不能当成多人产品的身份认证。Lab 发布门槛只检查提交的报告，不验证报告由谁签发。正式服务还需身份、权限、审计、隔离和防篡改设计。

## 目前的数据表

主实体包括 action_runs、intents、completion_contracts、action_steps、evidence、outcomes、judgment_snapshots、learned_rules、repeat_clusters。关联表包括 rule_sources、repeat_members 和 trace_events。

skill_versions、eval_cases、eval_runs 目前有表结构和导出支持。完整的版本注册、迁移、服务端评估任务、Canary 和回退调度仍待开发。不要把空表称为已运行的发布平台。

## 与模型的连接方式

第一种，把独立 Skill 装到宿主，按自然语言对话使用。没有调用本地记录工具就没有持久保存。

第二种，在项目内使用 Codex 一类宿主，让它在你授权后调用 CLI/API。真实回执才进入记录。

第三种，使用可选 provider 进行文本模型评估。它不提供工具执行、私有数据库访问或正式发布能力。
