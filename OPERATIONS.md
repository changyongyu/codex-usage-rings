# 维护与故障排查

## 独立启动

安装脚本注册当前用户的 `CodexUsageRings` 任务，使用交互登录会话、普通权限启动 `launch_supervised.py`，并创建桌面入口。`start_widget.py` 只请求运行已有任务，不能独立完成安装。

```powershell
Get-ScheduledTask -TaskName 'CodexUsageRings'
Get-ScheduledTaskInfo -TaskName 'CodexUsageRings'
Start-ScheduledTask -TaskName 'CodexUsageRings'
```

任务允许电池供电运行，没有执行时长上限，重复启动请求不创建新的任务实例。任务失败时按 1 分钟间隔重试，最多 999 次。组件自身意外退出后，守护通常等待 5～60 秒重试；连续短时退出会延长等待。这些机制并非对所有故障的保证。

## 正常退出与重启

日常退出请选择卡片或托盘右键菜单的“退出”。组件会写入停止标记，守护不再自动重开。等待任务回到 `Ready` 后，双击桌面入口可重新启动。

源码更新、依赖升级或安装配置更新前也请先退出组件。`Stop-ScheduledTask` 不保证组件子进程已退出，残留组件可能继续持有单实例锁，因此不建议用它代替日常退出。

## 数据文件

默认使用下列路径；若配置 `CODEX_HOME`，前三项随其变化。

| 路径 | 内容 |
| --- | --- |
| `%USERPROFILE%\.codex\widget_pos.json` | 位置、锁定、置顶、显示模式和展示风格 |
| `%USERPROFILE%\.codex\codex_widget.log` | 查询和界面日志，含额度数据 |
| `%USERPROFILE%\.codex\codex_widget_instance.json` | 当前组件进程信息 |
| `%LOCALAPPDATA%\CodexUsageRings\launcher.log` | 带轮转的守护日志 |
| `%LOCALAPPDATA%\CodexUsageRings\child.pid` | 守护记录的子进程 ID |
| `%LOCALAPPDATA%\CodexUsageRings\stop.requested` | 主动退出标记，重新启动守护时清除 |

如果环境没有 `LOCALAPPDATA`，守护目录回退到用户主目录下的 `CodexUsageRings`。PID 文件在异常退出后可能残留，不能单独证明进程仍运行。

不要删除整个 `.codex` 目录：它属于 Codex，也包含认证和历史信息。日志可能包含敏感的额度和路径，分享前请检查。

## 展示风格与升级

卡片或托盘右键 → **展示风格** → **蒙德里安 / 孟菲斯波点**。切换即时生效，自动写入设置中的 `style` 字段（`mondrian` / `memphis`），重启继续使用。

没有保存风格的新安装默认使用蒙德里安；升级旧版本时，缺失或无效的风格值也回退到蒙德里安。安装和升级不覆盖已经保存的有效选择。请将 `widget_styles.py` 与 `codex_usage_widget.py` 一同更新，避免缺失绘制模块。

新双环卡片默认约 365 × 495 像素。恢复位置时会检查屏幕边界；若原位置容纳不下新卡片，会移动到可见区域。字体、圆环和卡片可通过 `UI_SCALE` 一起缩放。

## 卡片消失

1. 检查系统托盘，双击图标恢复窗口。
2. 若此前主动退出，双击桌面入口重新打开。
3. 若意外退出，等待守护重试，并查看 `launcher.log`。
4. 检查任务状态。`Running` 仅表示任务入口运行，不等于数据读取成功，需结合窗口及查询日志判断。
5. 如果多显示器布局改变，退出后将 `widget_pos.json` 重命名备份，再启动以恢复默认位置。

## 显示“读取失败” / 月度不可用

检查 Codex 是否已登录、网络是否可用，再右键“立即刷新”或等待下一轮查询。

无 `individualLimit` 可能表示账号没有个人月度额度，或者 Codex / 服务端版本未返回数据；不是额度耗尽。接口和客户端版本变化也可能导致查询失败，应结合日志排查。

`codex_usage.py` 会搜索 PATH 与 Codex 版本目录；可用环境变量 `CODEX_USAGE_WIDGET_CODEX` 指定可执行文件。任务计划程序的环境不一定与当前终端相同。

## 移动目录或更换 Python

先退出并运行旧目录下的 `uninstall.ps1`，再在新目录重新执行安装脚本。虚拟环境本身不宜直接搬移，应重新创建。不要同时保留启动文件夹入口与另一份直接运行的守护进程。

## 禁用与恢复自启动

```powershell
Disable-ScheduledTask -TaskName 'CodexUsageRings'
Enable-ScheduledTask -TaskName 'CodexUsageRings'
```

任务禁用期间，桌面快捷方式也无法通过它启动。卸载脚本只处理当前目录对应的任务、组件进程和快捷方式；如果任务属于另一目录，脚本会拒绝操作。卸载不清理源码、状态或 Codex 认证。
