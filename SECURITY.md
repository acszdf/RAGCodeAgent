# Security policy

## Supported code

安全修复只针对默认分支的最新版本。该项目是研究原型，不承诺生产级安全保证。

## Reporting a vulnerability

请使用 GitHub 仓库的私有安全报告或 Security Advisory 功能提交漏洞。不要在公开 Issue、
Pull Request、日志或截图中粘贴 API Key、访问令牌、个人数据、私有源码或可利用细节。

报告应尽量包含：受影响版本或提交、复现步骤、影响范围、最小化示例和建议修复方向。

## Credential exposure

如果密钥曾出现在公开仓库、公开压缩包、构建日志或聊天记录中：

1. 立即在供应商控制台撤销或轮换该密钥；
2. 检查使用记录与账单；
3. 从当前文件和 Git 历史中清理敏感值；
4. 检查 forks、缓存、制品和其他克隆副本；
5. 使用 `.env`、环境变量和 GitHub Secrets 管理后续凭据。

仅删除最新提交中的文件不能使已泄露密钥重新安全。

## Data handling

模型调用会向配置的第三方 API 发送待审查 diff、Prompt 和检索证据。用户负责确认其有权上传
这些内容，并确认供应商的数据保留、训练使用、地域和合规条款满足项目要求。
