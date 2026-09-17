# Promptfoo 适配与真实模型评估

本目录包含本项目编写的 Python provider、Python assertion、配置生成器和两份 JSON 配置。接口依据官方 Python provider/assertion 文档，来源 S03/S04 见 ../../docs/open-source-map.md。

## 本次实际验证范围

Python 函数、输入隔离、默认断网、配置结构和固定样例已经本地测试。**完整 Promptfoo CLI 没有运行。** 核对的仓库 package.json 为 0.123.0，要求 Node >=22.22.0；当前容器 Node 为 22.16.0。npm 查询还出现超时。因此该版本在 npm 的可安装性和端到端 CLI 执行均未验证。

package.json 将该源码版本记录为可选依赖候选。没有生成虚假的 package-lock。正式接入时先在满足 Node 要求的环境核对 npm 版本、固定 lockfile，再跑 CLI 冒烟测试。

## 无需 Node 的离线入口

在项目根目录：

```bash
python scripts/run_evals.py --mode offline --out .local/offline.json
```

只读六份预写 Envelope。输出是机械检查，无实际模型调用。

## 可选真实模型入口

使用你已经确认的 Chat Completions 兼容端点和模型。没有默认服务商，没有自动创建账号。先确认传输材料、调用价格和样本授权。

```bash
export G_ALLOW_NETWORK=1
export G_CHAT_COMPLETIONS_URL='https://YOUR_APPROVED_HOST/v1/chat/completions'
export G_MODEL='YOUR_APPROVED_MODEL'
export G_API_KEY='YOUR_LOCAL_SECRET'
export G_MAX_COMPLETION_TOKENS=3500
python scripts/run_evals.py --mode live --skill g-ground --limit 3 --out .local/live-ground.json
```

这些为占位配置，不可原样调用。密钥建议在本机安全设置，不放 Git、不写进文档、不发群。默认不重试，超时 120 秒，输出限额与任务数有上限。上限只控制请求数量和输出 token，无法保证供应商总收费，仍需账户侧预算控制。

该 provider 按 `messages` 和 `max_completion_tokens` 请求。兼容服务不一定支持相同参数，需要依据实际端点测试。请求没有 tools，没有读取数据库，没有执行电脑操作。HTTPS 或显式 localhost HTTP 可用，拒绝重定向。

## Promptfoo CLI 路径

在你自己的兼容 Node 环境核对并安装依赖后，于本目录运行：

```bash
npm install
npx promptfoo eval -c promptfooconfig.offline.json
```

以上命令未在本次容器实测。先让离线配置通过，再生成少量真实模型配置。

```bash
python generate_config.py --split dev --skill g-ground --limit 3
npx promptfoo eval -c promptfooconfig.live.json
```

生成配置本身不联网。执行 live 时仍需 G_ALLOW_NETWORK、端点和模型。只有 input_json 进入模型；case_id 在评分侧使用，不把整份 Promptfoo context 或评分要求发给模型。

## 分数边界

自动断言通过仅代表 JSON 合法且决策属于该题允许集合。必须另行审查评分要求中的语义条件。真实模型测试是否已经执行，应从运行报告、原始响应和服务方用量共同确认。
