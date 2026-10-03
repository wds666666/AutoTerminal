# v1.1.0
2026-10-03

- 新增 DeepSeek、智谱（中国）、Kimi、Qwen（百炼）配置向导，支持模型自动获取及手动输入。
- 新增 Bash/Zsh 接入与上下文查看，传递上一条命令及退出码，优先纠正失败命令。
- 修复历史数量为零无效、上下文顺序、配置覆盖丢失、命令取消及退出码处理。
- 拒绝执行截断的模型响应，限制目录与历史上下文大小，增加请求超时和原子保存。
- 新增 17 项回归测试，覆盖 SDK 请求、配置向导及真实交互 Shell。

# v1.0.0 
2025-10-21
-  add the shell history feature
-  add the logging feature
-  refactor the codebase for better maintainability