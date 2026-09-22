# WindJev

简体中文 | [English](README_EN.md)

WindJev 是一个面向开发者工作流、具备置信度感知能力的决策基座。它的 MVP 使用 TypeSafe Jev 对 GitHub Issue 进行分流，并通过 Python 接口、CLI 和 GitHub Action 提供一致的行为。

MVP 刻意保持精简：先通过 Issue 分流验证基础能力，不提前引入工作流 DSL、插件系统、托管服务或通用连接器框架。

## 判断内容

每个 Issue 会产生四项类型化判断：

- `type`：`bug`、`feature`、`question` 或 `maintenance`
- `area`：由仓库定义的产品或代码领域
- `priority`：`low`、`medium`、`high` 或 `critical`
- `route`：由仓库定义的负责团队

每项判断都包含置信度和各选项的概率。WindJev 根据各字段的置信度门槛和响应有效性推导 `needs_review`，而不是让模型自行判断它的答案是否可信。

## 安装

WindJev 需要 Python 3.11 或更高版本。

```bash
pip install windjev
export TYPESAFE_API_KEY="..."
```

本地开发：

```bash
uv sync --dev
uv run pytest
```

## 初始化仓库

```bash
windjev init
```

该命令会创建 `.windjev.yml` 和 `.github/workflows/windjev.yml`，且不会覆盖已有文件。根据仓库情况编辑生成配置中的 `areas`、`routes` 和标签映射，然后进行校验：

```bash
windjev config validate
windjev config validate --json
```

新配置默认使用 `observe` 模式和 `jev-latest`。观察模式会生成完整结果，但不会修改标签。

## 本地运行

```bash
windjev triage \
  --repository acme/shop \
  --title "POST /orders returns 500" \
  --body "The request fails after upgrading" \
  --json
```

对已有 GitHub Issue 进行分流时，还需要设置 `GITHUB_TOKEN`：

```bash
export GITHUB_TOKEN="..."
windjev triage --repository acme/shop --issue-number 42 --json
```

机器可读输出是在标准输出中生成的一份带版本号的 JSON 文档，诊断信息写入标准错误。稳定退出码分别为：`0` 表示判断完成（包括需要人工复核），`2` 表示输入或配置无效，`3` 表示 Provider 失败，`4` 表示 GitHub 操作失败。

## GitHub Action

生成的工作流会在 Issue 创建时运行，并支持手动重新分流。请将 `TYPESAFE_API_KEY` 添加为仓库 Secret。工作流只会检出默认分支，然后读取 `.windjev.yml`；Issue 内容永远不会被执行。

观察模式需要以下权限：

```yaml
permissions:
  contents: read
  issues: read
```

切换到应用模式前，请固定一个不可变模型版本，例如 `jev-1.13.0`，使用历史 Issue 完成评估，并将 `issues: read` 改为 `issues: write`。应用模式会一次性更新全部四个受管理的标签维度。如果任一判断未通过门槛，现有判断标签保持不变，只添加 `needs-human-review`。

WindJev 不会修改未受管理的标签、分配人员、关闭 Issue、编辑 Issue 内容或发布生成的评论。

## 应用前评估

创建 `.windjev/eval.yml`：

```yaml
version: 1
repository: acme/shop
cases:
  - issue: 42
    expected:
      type: bug
      area: api
      priority: high
      route: backend
```

然后运行：

```bash
windjev eval --evaluation .windjev/eval.yml --json
```

报告包含各字段准确率、自动处理覆盖率、自动处理错误率、人工复核率、Provider 用量和耗时。少于 30 个用例时会产生警告。WindJev 不会自动调整门槛或启用应用模式。

## Python

```python
from windjev import IssueSubject, TriageProfile, TypeSafeJevProvider, triage

profile = TriageProfile.model_validate({
    "version": 1,
    "mode": "observe",
    "model": "jev-latest",
    "areas": {"api": "Public API and request handling"},
    "routes": {"backend": "Backend maintainers"},
    "labels": {
        "type": {
            "bug": "type: bug",
            "feature": "type: feature",
            "question": "type: question",
            "maintenance": "type: maintenance",
        },
        "area": {"api": "area: api"},
        "priority": {
            "low": "priority: low",
            "medium": "priority: medium",
            "high": "priority: high",
            "critical": "priority: critical",
        },
        "route": {"backend": "route: backend"},
        "review": "needs-human-review",
    },
})

result = triage(
    IssueSubject(
        title="POST /orders returns 500",
        body="The request fails after upgrading",
        repository="acme/shop",
    ),
    profile,
    TypeSafeJevProvider(),
)
```

异步应用使用 `async_triage`。批量评估使用 `async_triage_many`，它会限制并发、保持输入顺序，并隔离单项失败。

## 数据边界

WindJev 只向 TypeSafe 发送 Issue 标题和正文、仓库名称和描述，以及配置的判断标准。它不会发送评论、附件、作者信息、已有标签、仓库源码或其他 Issue。私有 Issue 的内容仍会离开 GitHub 并发送给 TypeSafe。

WindJev 没有托管服务、数据库或产品遥测。API Key 从环境变量或 GitHub Secrets 读取，不会写入配置或结果。

## 项目文档

- [MVP 设计](docs/mvp-design.md)
- [领域语言](CONTEXT.md)
- [架构决策](docs/adr/)
