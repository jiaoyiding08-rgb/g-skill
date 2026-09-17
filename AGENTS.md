# G Skill 开发协作约定

## 当前任务与主文件

这是六个 Agent Skills 的本地原型，加上 Python/SQLite 参考底座。先读 README、kernel/CONTRACT.md、docs/architecture.md 和 docs/acceptance.md。遵守用户当前请求，不自行扩成网页、社交平台或多租户产品。

## 修改规则

1. 开始前确认当前代码、失败情况、授权目录和本轮验收条件。
2. 不读取或修改用户未授权目录。不得把 .local、数据库、密钥、客户资料和私人行为上传。
3. dbskill 原文件不在本包中。不得从用户私有源目录直接复制原文并改名发布。保留 docs/source-lineage.md。
4. 共同行为规则只编辑 kernel/CONTRACT.md。共同 Schema 只编辑 kernel/schemas/protocol.schema.json。完成后运行 `python scripts/sync_skill_refs.py` 同步自包含副本。
5. 决策枚举修改要同步 kernel/decisions.json、Schema、Skill、示例和评分要求。更改已持久化的语义需要新协议版本和迁移说明。
6. 不让模型 JSON 自行签发写入、付款、发布或 VERIFIED。证据必须绑定运行和标准版本。
7. 外部副作用、删改、收费 API、正式 Skill 改写需要明确授权。自动发布不在本版范围。
8. 不替换正式 Skill 后再评估。先在候选目录修改，保存基线与 diff，完成测试和人工审阅再决定发布。
9. 所有合成材料保持 simulated/provenance 标记。不得报告尚未执行的模型成功率。
10. 日常输出使用中文和短句，不对用户进行人格判断或羞辱。

## 必跑命令

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m kernel demo --out .local/demo-new
python scripts/run_evals.py --mode offline --out .local/offline-new.json
```

目标已存在时选择新的 demo/输出路径，不删除旧资料凑通过。

## 评测角色隔离

执行模型只能得到选定 Skill、共同约定、响应 Schema 和案例输入。不要给它 evals/grading、旧答案、候选优劣标记和评分结果。

本仓库所有案例均公开给作者，可用于开发和回归。`holdout_candidate` 不是真盲测。真正留出集应由另一名维护者准备并保存到执行者与优化器不可读的位置。评分和执行最好由独立过程处理，语义评审保留人工检查。

## 不得夸大

程序单元测试通过，说明检查到的代码行为通过。离线样例通过，说明固定 JSON 符合协议。只有真实模型跑过并经独立评分，才能报告模型表现；只有实际用户任务试用，才能讨论对执行结果的作用。

## 后续优先级

先补十个匿名真实案例，跑基线和 G 版本的相同输入，对失败做最小改动。之后再考虑人工语义核验器、只读外部状态适配、真实运行注册表、候选发布与回退。不优先接屏幕监控、现金排名或自动优化器。
