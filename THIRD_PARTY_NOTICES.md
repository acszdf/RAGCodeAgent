# Third-party notices

本仓库的 `LICENSE` 只覆盖本项目原创代码与原创文档。以下外部材料保留其原始许可与归属。

## Python PEP 8

- 文件：`docs/knowledge/pep-0008.rst`
- 标题：*PEP 8 – Style Guide for Python Code*
- 上游：Python PEPs 官方仓库及 `https://peps.python.org/pep-0008/`
- 快照日期：2026-07-21
- 完整性：SHA-256 记录于 `docs/checksums.sha256`
- 许可：该文档末尾声明已置于公有领域

文件中保留了原作者与原始版权声明。本项目未修改该快照。

## OWASP SQL Injection Prevention Cheat Sheet

- 文件：`docs/knowledge/sql-injection-prevention.md`
- 标题：*SQL Injection Prevention Cheat Sheet*
- 上游：OWASP Cheat Sheet Series 官方仓库
- 上游文件：`cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.md`
- 快照日期：2026-07-21
- 完整性：SHA-256 记录于 `docs/checksums.sha256`
- 许可：Creative Commons Attribution-ShareAlike 4.0 International
- 许可全文：`docs/licenses/CC-BY-SA-4.0.md`

本项目按原文保存该文件，未声称获得 OWASP 背书。Open Worldwide Application Security
Project 和 OWASP 是 OWASP Foundation, Inc. 的注册商标。

## 实验结果中的外部摘录

`experiment/results/rag/*.json`、`experiment/results/retrieval/*.json` 及其中保存的 Prompt、
retrieved chunks、quotes 可能包含 PEP 8 或 OWASP 文档的原文摘录。相关摘录继续适用上述
来源的许可；其余由本项目生成的结构和原创说明适用 MIT License。

## Python dependencies

`requirements.txt` 中的包通过包管理器安装，并未将其源码复制进本仓库。每个依赖保留自己的
许可。发布二进制发行物、容器镜像或重新分发依赖时，应单独核对相应版本的许可与通知要求。
