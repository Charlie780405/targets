# PLAN-006：退役 WeKnora 新证据采集

状态：已实现，未部署。

## 目标

Targets 停止从 WeKnora 接收新文献证据，同时完整保留历史投影、事件与来源失效门禁。历史工作台只读，不再产生新的审核写入。

## 变更

- 删除 WeKnora 拉取客户端、同步 CLI、调度注册、环境配置与专用 retrieve Key 文件依赖。
- 保留 `weknora_evidence_projections` 表、迁移和历史数据，不删除或重置任何状态。
- 将周报、已审摘要、审核队列、Vault 与 frontmatter 回写使用的来源门禁迁到 `apps/weknora_history.py`；非 active 历史投影继续阻断发布。
- 历史工作台保留白名单字段的分页读取，删除审核令牌、PATCH 路由和批准/拒绝按钮。

## 边界

- 本计划不部署生产、不修改或撤销真实凭据。
- WeKnora 的 `targets-evidence` v1 接口在服务端继续观察至少 7 天并覆盖一个完整调度周期；日志确认零调用后由后续变更删除接口与相关授权。
- 历史投影、事件和迁移不会在本期清理。

## 验证

运行 `bash scripts/verify-plan-006-weknora-retirement.sh`，覆盖无调度注册、无采集入口、历史只读、PATCH 不存在，以及 revoked/expired 历史证据无法进入周报、摘要、审核队列或 Vault。
