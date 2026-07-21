# Contributing

## Development setup

使用 Python 3.12 创建隔离环境，并从 `.env.example` 创建本地 `.env`。不要提交真实密钥、
`.venv/`、`.faiss/`、缓存或包含私有代码的实验结果。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
```

Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1` 和 `Copy-Item .env.example .env`。

## Change requirements

- 修改评价字段时，同时更新 `experiment/evaluation_protocol.md`、测试和 README 指标表。
- 修改知识文档时，更新 `docs/checksums.sha256`、来源快照信息和第三方许可说明。
- 修改 Prompt 或实验链路时，递增 `prompt_version`，不要覆盖历史原始结果。
- 新增实验结果前，检查是否包含私有代码、个人数据、凭据或不允许再分发的材料。
- 提交前运行 `python -m pytest -q` 和 `python agent.py evaluate`。

## Pull requests

Pull Request 应说明变更目的、验证方式、实验结果是否变化，以及是否影响许可、隐私或外部 API
成本。不要把模型输出当作事实；涉及指标变化时应附上可复算数据和评价规则。
