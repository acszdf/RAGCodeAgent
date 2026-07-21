# Knowledge base provenance and licensing

RAG 索引只读取 `docs/knowledge/`。外部文档按原文快照保存，以便实验可复现；项目不会暗示
Python Software Foundation 或 OWASP 对本项目提供背书。

| File | Role | Upstream source | Snapshot | License |
|---|---|---|---|---|
| `pep-0008.rst` | Python naming and style rules | `https://github.com/python/peps/blob/main/peps/pep-0008.rst` | 2026-07-21；SHA-256 见 `checksums.sha256` | 文档自身声明置于公有领域 |
| `sql-injection-prevention.md` | SQL injection prevention guidance | `https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.md` | 2026-07-21；SHA-256 见 `checksums.sha256` | CC BY-SA 4.0 |
| `project-design.md` | Local architecture and error-handling contract | 本项目原创 | 2026-07-21 | MIT |

`pep-0008.rst` 和 `sql-injection-prevention.md` 与上述日期下载的官方上游原文逐字节一致。
OWASP 文档的许可全文保存在 `docs/licenses/CC-BY-SA-4.0.md`。完整归属说明见仓库根目录
`THIRD_PARTY_NOTICES.md`。

结果 JSON 中的 `retrieved_chunks`、Prompt 和 citations 可能包含上述文档摘录。外部材料的许可
不会因被写入实验结果而变成本项目的 MIT 许可。
