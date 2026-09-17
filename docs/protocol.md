# 协议与运行参考

## 版本

协议 0.1.0，Skill 状态 alpha，SQLite user_version=1。模型输出以 `Envelope` 统一。完整字段定义在 kernel/schemas/protocol.schema.json 的 `$defs`。Schema 标识地址仅用于命名，不触发网络读取。

| 对象 | 关键约束 |
|---|---|
| TaskIntent | 用户实际目标、范围、来源、创建时间 |
| CompletionContract | 稳定 ID、版本、至少一个可检查条件；同版本不可改 |
| Criterion | 类型、最低等级、核验方式、有效期必须与主张匹配 |
| ActionStep | 一个主要动作、承担者、依赖、时间预算、副作用与确认 |
| Evidence | run、标准版本、条件 ID、来源、捕获时间、模拟标记 |
| Outcome | 检查结果与所用证据绑定；成功条件逐项通过 |
| JudgmentSnapshot | 开始前保存，不能覆盖或事后补成预测 |
| LearnedRule | 来源、状态、适用范围、反例、复查条件 |
| RepeatCluster | 独立 episode、原始 run、成熟度、近邻反例 |
| ActionTrace | 可见事件摘要，不保存模型隐含思考 |
| Handoff | 父运行、目标、事实、待补项、证据和相同授权范围 |
| Envelope | 决策和写入提议；writes_applied 固定 false |

Repeat 的本地存储要求 R1 来源任务已经登记开始；仅有计划不能确认重复。R2 模板候选进一步要求来源任务已核验。这个原型规则比较保守；语义可复用性仍要由独立新实例验证。

Schema 提供类型校验；Python `validate` 再检查跨字段约束。格式校验不能证明文字描述真实。

## 运行状态

| 当前 | 可请求的下一状态 |
|---|---|
| DRAFT | READY、PARKED、ABORTED |
| READY | ACTIVE、PARKED、ABORTED |
| ACTIVE | WAITING_EVIDENCE、FAILED、PARKED、ABORTED |
| WAITING_EVIDENCE | ACTIVE、FAILED、PARKED、ABORTED |
| PARKED | READY、ABORTED |
| VERIFIED、FAILED、ABORTED | 不直接切换；更改目标建立新运行 |

`VERIFIED` 只能经 `verify()` 产生。证据撤销会使已核验运行退回等待。已通过的文件之后变化，下一次主动复查会使状态退回等待。**没有持续文件监视，所以文件刚变化时不会即时推送或自动更新。**

设置 ACTIVE 只登记行动开始，不等于代码已经替用户执行动作。受依赖阻塞的计划不能开始。开始后不能通过 PARKED 再回 READY 伪造事前快照。

## E0–E3 的实际能力

E0 是自述标记。E1 是产物标记。E2 是核验系统状态。E3 是有来源的第三方结果。它们要对应具体问题，不能简单按数值高低替代判断。

本地 `attach_file()` 只产生 E1，限定显式目录、最大 16 MiB 文件，登记 SHA-256、时间和范围。`verify()` 重新读取文件并比较哈希。

URL 可打开不证明交易完成。文件存在不证明其内容合格。E2/E3、人工作品质量判断和第三方回应在本版无法自动签发通过；要求这些条件的任务保留 WAITING_EVIDENCE。

## CLI

在项目根目录、激活 Python 环境后：

```bash
python -m kernel --help
python -m kernel --db .local/work.sqlite init
python -m kernel check examples/run-plan.json --kind RunPlan
python -m kernel check examples/g-ground.json --kind Envelope
python -m kernel --db .local/work.sqlite create examples/run-plan.json
```

`create` 返回运行 ID。后续状态、snapshot、attach 和 verify 命令用这个真实 ID。静态 examples 的 ID 不应反复用来创建真实任务；真实任务生成新 ID 和当前时间。用相同幂等键提交相同请求会返回原运行；同键改请求会拒绝。

```bash
python -m kernel --db .local/work.sqlite state RUN_ID READY
python -m kernel --db .local/work.sqlite snapshot RUN_ID --prediction '本轮会生成草稿文件' --window '本次任务结束'
python -m kernel --db .local/work.sqlite state RUN_ID ACTIVE --confirm
python -m kernel --db .local/work.sqlite attach RUN_ID file_created PATH_TO_FILE --root ALLOWED_DIRECTORY
python -m kernel --db .local/work.sqlite verify RUN_ID
python -m kernel --db .local/work.sqlite export --out .local/my-export.json
```

上述大写参数为需要替换的实际值。示例 RunPlan 中的 criterion_id 请以文件本身为准。想免配置检查时优先运行 `demo`。

## SQLite 行为

每个实例只面向一个可信本地用户。写操作使用事务和外键。同一标准版本不可改，快照不可覆盖。删除运行会一并清理其证据、结果和相关派生规则/簇，避免残留复制的私人事实。源文件和已导出的备份不会被删除。

数据库不是防篡改账本。能直接写数据库或改 Python 代码的人可以绕过约束。本版不适合用来裁定现金奖金或处理对抗性的多人提交。
