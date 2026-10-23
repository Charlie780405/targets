# WT-006：WeKnora 采集退役与历史只读

## 结果

Targets 已没有 WeKnora 网络客户端、同步命令或 scheduler 作业。部署后即使遗留环境仍含旧 `WEKNORA_*` 变量，也不会注册或执行拉取。

历史 `weknora_evidence_projections` 继续由现有模型和迁移读取。工作台只提供 GET 页面与 GET 分页接口，所有行的 `reviewable` 均为 `false`；旧 PATCH 地址不再注册并返回 404。

`apps/weknora_history.py` 是保留的只读发布门禁。绑定非 active 投影的事件不能进入周报、已审摘要、审核队列、Vault 导出或 Vault frontmatter 回写；没有历史投影的普通事件保持原行为。

## 上线门禁

1. 部署 Targets 退役版本，确认 scheduler 作业列表没有 `sync_weknora_literature`。
2. 保留 WeKnora v1 路由访问日志至少 7 天，并覆盖原调度的一个完整周期。
3. 确认零调用后，另行删除 WeKnora v1 路由和相关 retrieve 授权。
4. 若专用 Key 还服务其他接口，只移除 `targets-evidence` 授权；不要删除整把 Key。

本次未执行生产部署、真实 Key 撤销或历史数据清理。
