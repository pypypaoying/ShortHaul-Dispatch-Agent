# 外部数据接入指南

ShortHaul Dispatch Agent 的默认接入方式是一张 Excel 工作簿。外部使用者不需要手写 JSON，也不需要一次上传多份 CSV。

![Web UI upload workflow](assets/dispatch_ui_demo.png)

## 推荐流程

1. 启动服务并打开 Web UI：`http://127.0.0.1:8000/`。
2. 点击“下载 Excel 模板”，或使用仓库中的 `examples/workbook_template/shorthaul_dispatch_template.xlsx`。
3. 将业务数据填入三张必需表：`fleets`、`routes`、`demand`。
4. 如需串点关系或求解参数，再填写可选表：`compatibility`、`settings`。
5. 在 UI 中上传工作簿并点击“上传并运行”。
6. 查看 KPI、外部承运任务数、调度甘特图和原始响应。

## 最小数据格式

| 工作表 | 业务含义 | 必需字段 |
| --- | --- | --- |
| `fleets` | 自有车队资源 | `fleet_id`, `owned_vehicles` |
| `routes` | 线路、波次、时间窗和成本 | `route_id`, `origin`, `destination`, `wave`, `latest_dispatch_time`, `travel_min`, `fleet_id` |
| `demand` | 线路货量 | `route_id`, `volume` |

`demand.ready_time` 可选。不填写时，系统会按对应线路的最晚发运时间自动给出默认可发运时间。

## 常见业务数据如何转换

| 业务系统字段 | 填入工作表 | 模板字段 |
| --- | --- | --- |
| 车队编码、车队名称 | `fleets` | `fleet_id` |
| 自有车数量 | `fleets` | `owned_vehicles` |
| 线路编码或“始发地-目的地-波次” | `routes`、`demand` | `route_id` |
| 始发场地 | `routes` | `origin` |
| 目的站点 | `routes` | `destination` |
| 发运波次 | `routes` | `wave` |
| 最晚发运时间 | `routes` | `latest_dispatch_time` |
| 在途时长 | `routes` | `travel_min` |
| 预测包裹量、货量 | `demand` | `volume` |
| 货量可发运时间 | `demand` | `ready_time` |

时间字段支持分钟偏移，也支持 `D+n HH:MM`：

| 写法 | 含义 |
| --- | --- |
| `1800` | 计划起点后的第 1800 分钟，即 D+1 06:00 |
| `D+0 23:00` | 第一天 23:00 |
| `D+1 14:00` | 第二天 14:00 |

## API 上传

系统集成时可以直接上传同一个工作簿：

```http
POST /schedule/upload
Content-Type: multipart/form-data
```

| 表单字段 | 说明 |
| --- | --- |
| `workbook` | 填好的 Excel 工作簿 |
| `request` | 自然语言调度需求 |
| `instance_id` | 场景编号 |
| `date` | 计划日期 |
| `prefer_cpsat` | 是否优先使用 CP-SAT |

## 调试接口

- `GET /templates/view`：在浏览器中预览模板格式。
- `GET /templates/workbook.xlsx`：下载 Excel 模板。
- `GET /contract`：查看字段说明和填表步骤。
- `GET /schema`：查看机器可读 schema。

CSV 和内部 JSON 仍然可用，但建议只在自动化导出、系统集成或调试时使用。
