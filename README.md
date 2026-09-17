# ⚡ g-skill

> **脑内已经上市，现实还没新建文件。**<br>
> *Compiler for reality: Evidence > Vibes.*

计划写完了。模板搭好了。工具买齐了。<br>
然后呢，东西在哪？

G = Gravity。一个现实编译器，负责追问三件事：

**下一步做什么？怎样才算完成？证据在哪？**

### 假动作质检

- 花三小时搭 Notion，任务本身动了五分钟。
- 收藏了八百篇教程，第一版还没交。
- 第十二次优化标题，发布按钮一次没点。

这些动作都发生了。交付有没有发生，另算。

### 六个模块，专查“然后呢”

- **Ground**：先把下一步说成人能动手做的事。
- **Real**：别急着宣布需求成立，先让现实回一句。
- **Ship**：这次修改真有必要，还是又在拖？
- **Review**：把事前判断拿出来，跟结果对账。
- **Repeat**：同一个坑，别每次都原创新跳法。
- **Lab**：方法也得考试。改得更狠，不等于改得更好。

当前提供六个 Skill 和本地记录、核验底座。<br>
自动监控、自动发布、自主进化尚未实现。

**先交一版。让现实参与讨论。**

---

**0.1.0-alpha · 本地原型 · 六个 Skill + 可运行记录底座**

先读 [开始使用](START_HERE.md)。交给开发代理时读 [AGENTS.md](AGENTS.md)。公开版本采用 [Apache-2.0](LICENSE)；运行报告不随源码发布。

## 这版能做什么

| 模块 | 本轮交付 | 尚不能宣称 |
|---|---|---|
| Ground | 一步行动、完成标准、依赖、证据请求 | 自动让用户完成目标 |
| Real | 可区分假设的小测试、成本、观察窗口 | 已经有真实需求或成交 |
| Ship | 检查硬风险、核心价值、必要修改 | 已经替用户发布或付款 |
| Review | 事前记录与结果对照、候选规则 | 缺少历史时还原用户当时想法 |
| Repeat | 独立实例去重、模式与模板候选 | 自动看见所有电脑活动 |
| Lab | 修改方案、评估规则、发布检查 | 自主改写并部署正式版 |

六个 `SKILL.md` 可独立复制到支持 Agent Skills 的宿主。Python 底座负责真实本地记录和机械核验。两者通过 JSON 协议连接；这版没有部署一个全天运行的 Agent 服务。

## 快速运行

在解压后的 `gskill-v0.1.0` 根目录运行。需要 Python 3.10 或更高版本。依赖安装会访问所配置的 Python 包源；后面的测试和 demo 默认离线。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/check_project.py
python -m kernel demo --out .local/demo-01
python scripts/run_evals.py --mode offline --out .local/offline-check.json
```

`demo` 创建隔离目录中的示例文件和 SQLite 数据库。目录已经含有 demo 数据库时拒绝覆盖，请换一个目录。它不发布视频、不收款、不读取浏览器、不调用模型。

## 安装六个 Skill

当前 Codex 官方文档列出的本地位置包括用户级 `$HOME/.agents/skills` 和项目级 `.agents/skills`，见来源 [S02](docs/open-source-map.md)。安装脚本先显示将复制的位置。

```bash
python scripts/install_skills.py --target "$HOME/.agents/skills"
python scripts/install_skills.py --target "$HOME/.agents/skills" --apply
```

默认只安装前五个。维护者需要 Lab 时，在空目标目录安装全部六个：

```bash
python scripts/install_skills.py --target ./my-g-skills --include-lab --apply
```

已有同名目录会整体拒绝操作。先备份，再由你选择目标目录。宿主是否即时加载由其当前实现决定；看不到新 Skill 时重新打开会话检查。

安装后可明确调用，例如 `$g-ground 帮我把这个计划缩成今天能完成的一步`。仅安装 Skill 不会启动 SQLite 或自动持久记忆。需要记录时，由宿主在授权目录使用本项目的 CLI/API。

## 关键文件

| 文件或目录 | 用途 |
|---|---|
| `skills/` | 六个独立 Skill、共同约定、结构化示例 |
| `kernel/CONTRACT.md` | 统一行为、证据与授权规则 |
| `kernel/schemas/protocol.schema.json` | 统一 JSON Schema |
| `kernel/schema.sql` | SQLite 初始结构 |
| `kernel/storage.py` | 记录、状态、快照、证据、导出和删除 |
| `runtime/` | E1 核验、交接检查、Lab 发布检查 |
| `evals/inputs/` | 72 个合成测试输入 |
| `evals/grading/` | 与执行输入分开的评分要求 |
| `adapters/promptfoo/` | 离线样例及可选真实模型评估适配 |
| `docs/source-lineage.md` | 原 dbskill 保留、删改、新增对照 |
| `docs/open-source-map.md` | 开源补全案例、许可证来源、集成状态 |

## 验证状态

程序测试、Schema 检查、安装复制、离线演示已经运行，数量见验收报告。**没有执行真实模型效果评测，没有验证真实用户执行力提升。** 72 个合成案例是待跑的行为测试题。

Promptfoo Python provider/assertion 已做本地函数测试。完整 Promptfoo CLI 未在本环境运行。DSPy/GEPA、Langfuse、PM4Py、OpenAdapt 未作为运行依赖接入。

## 私密性与来源

默认单用户、本地明文 SQLite，支持逻辑删除和导出。请读 [PRIVACY.md](PRIVACY.md)。不要把真实用户失败记录放进公开测试集。

原 dbskill 是本地 beta 材料，原文件未随本包再分发。本版保留机制对照，重新编写实现。公开发布和商业授权处理见 [LICENSE-NOTICE.md](LICENSE-NOTICE.md)。
