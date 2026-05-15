# ShortHaul Excel Workbook Template

`shorthaul_dispatch_template.xlsx` is the recommended input file for external users. Fill one workbook, upload it in the Web UI, and run the scheduler.

Required sheets:

| Sheet | Required columns |
| --- | --- |
| `fleets` | `fleet_id`, `owned_vehicles` |
| `routes` | `route_id`, `origin`, `destination`, `wave`, `latest_dispatch_time`, `travel_min`, `fleet_id` |
| `demand` | `route_id`, `volume` |

Optional sheets:

- `compatibility`: destination pairs that can be milk-run together.
- `settings`: capacity, objective weights, and solver strategy overrides.

`ready_time` in the `demand` sheet is optional. Time fields accept either minute offsets, such as `1800`, or readable day offsets, such as `D+1 06:00`.

API uploads use `POST /schedule/upload` with multipart field name `workbook`.
