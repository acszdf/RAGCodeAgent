# 人工评价协议（Rubric 2.0）

本协议用于解释 `human_evaluation.csv` 的逐行判分规则。评价对象是保存于
`experiment/results/{baseline,rag}/` 的最终结构化审查结果，而不是模型草稿或检索候选。
当前数据由一名评审者（`reviewer-1`）在 2026-07-21 完成，因此不包含评审者间一致性指标。

## 1. 匹配单位

`ground_truth.json` 中的一个 `issue_key` 代表一个根因。模型对同一根因给出多个表现、后果或
修复意见时，只计为一个 `detected_true_issues`，额外意见计入 `duplicate_findings`。一条模型
意见不能同时匹配多个 ground-truth 根因。

匹配依据依次为：缺陷机制、受影响文件、受影响新增代码和修复方向。仅关键词相同不足以判定
为命中。

## 2. 客观计数字段

- `detected_true_issues`：命中的唯一 ground-truth 根因数。
- `total_ground_truth_issues`：该样本在 `ground_truth.json` 中的根因数。
- `false_positives`：无法由 diff 或提供文档支持，或依赖未知外部上下文的意见数。
- `duplicate_findings`：已经由另一条意见覆盖的同根因重复意见数。
- `total_review_claims`：最终输出意见总数，必须满足：
  `detected_true_issues + false_positives + duplicate_findings`。
- `unsupported_claims`：false positive 中缺少代码或文档依据的断言数。

## 3. 建议与整体质量

### recommendation_quality_1_5

只评价已匹配真实问题的修复建议，不评价漏报和误报；没有命中真实问题时留空。

- 5：修复方向正确、具体、可直接实施，并与当前框架或调用方式匹配。
- 4：方向正确且可实施，但存在轻微泛化、上下文不够精确或遗漏次要细节。
- 3：方向基本正确，但需要较多补充才能安全实施。
- 2：建议含明显技术缺陷，可能引入新问题。
- 1：建议错误、不可执行或与问题无关。

### overall_review_quality_1_5

综合评价整条样本输出，考虑召回、误报、重复、严重度、定位、建议和引用：

- 5：所有根因均检出，无误报或重复；严重度和定位准确；建议及引用可靠。
- 4：总体可靠，仅有一个轻微缺陷，不影响主要结论。
- 3：存在一个实质性缺陷，例如严重度明显错误、重要定位偏差或部分漏报。
- 2：存在多个实质性缺陷，或同时出现漏报与误报。
- 1：没有产生可用审查结果，或主要结论错误。

## 4. 严重度与定位

- `severity_assessed`：命中的唯一 ground-truth 根因数，应等于 `detected_true_issues`。
- `severity_correct`：模型严重度与 ground truth 完全一致的根因数。
- `location_assessed`：命中的唯一 ground-truth 根因数，应等于 `detected_true_issues`。
- `location_exact`：模型的 `line_start` 与 ground truth 的规范根因行一致，且范围没有无必要地
  扩展到其他行。只“覆盖到”风险行不算精确定位。

该定义刻意比程序内置的 `location_checks` 更严格。程序检查只证明位置属于新增代码；人工字段
评价是否锚定到最能解释根因的行。

## 5. 引用评价

- `valid_citations / total_citations`：引用原文一致性。程序检查 source、section、chunk_id 和 quote
  是否与本轮实际检索 chunk 一致。
- `supported_citations / citation_support_assessed`：人工判断引用内容是否真正支持对应审查结论。

因此“引用原文一致”不自动等于“引用支持结论”。两项指标必须分开报告。

## 6. 聚合与复现

`python agent.py evaluate` 会同时读取 CSV、`ground_truth.json` 和最终结果 JSON，并检查：

- 5 个样本是否同时具有 baseline 与 RAG 行；
- 是否存在重复样本/模式；
- 所有计数是否为非负整数，避免小数被静默截断；
- ground-truth 数量、最终意见数、引用数和程序校验通过数是否与原始文件一致；
- 各计数字段之间是否满足约束。

聚合结果写入 `experiment/results/metrics.json`。该文件中的“问题召回率”不是分类准确率，也不
代表真实仓库中的总体代码审查准确率。
