# tvbox-conf — 自建 TVBox 聚合点播接口

由全栈哥（OpenClaw 全栈工程师）自动生成与维护的家庭影音 TVBox 聚合配置。

## 使用

OK影视 / TVBox → 设置 → 配置地址，填：

- 主地址：`https://raw.githubusercontent.com/zhourenjing/tvbox-conf/main/boss_tvbox.json`
- 备用 CDN：`https://cdn.jsdelivr.net/gh/zhourenjing/tvbox-conf@main/boss_tvbox.json`

## 内容构成（2026-09-14 v1）

| 来源 | 站点数 | 说明 |
|---|---|---|
| 小雅官方（my_ext_jar） | 49 | jar 走内网 192.168.100.150，需在家 LAN |
| 小盒子 xhztv.top | 54 | |
| 小盒子4K | 4 | 该接口多数站点的公共 jar 已失效，仅存活 4 站 |
| 高天 gao | 298 | drpy JS 站点，需较新版 OK影视 |
| 采集之王 drpy_dz | 272 | drpy JS 站点，需较新版 OK影视 |

合计 677 站 + 42 条解析；直播 tab = 家庭直播 2750 台（iptv 容器 1905）。

- 死 jar 的 49 个站点已自动剔除（fan.txt / rihou.vip / tv.nxog.top 等 9 个 jar 家宽实测不可达）
- 原始接口清单收录于配置 `storeHouse` 字段，App 内可一键切回任一原始接口
- 小雅 jar 引用已去 md5（上游每天发版 jar 内容变、URL 不变，去 md5 才不会失效）

## 重建 / 更新

`scripts/build_boss_tvbox.py` 在 NAS `/tmp/tvbox` 下运行（各源配置就位后）：
自动拉取各源最新配置 → 合并 → jar 测活 → 剔除死站 → 输出 `boss_tvbox.json`。
用新文件覆盖本仓库根目录同名文件并推送即可，**配置地址永不变**。

## 更新记录

- 2026-09-14 v1：首次生成（726 站 → 剔除 49 死站 → 677 站）
