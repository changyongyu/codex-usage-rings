# Codex Usage Rings

Windows 桌面悬浮用量卡片：双圆环显示 **5 小时 / 每周剩余额度**，底部进度条显示**个人月度工作空间额度**。中文界面，每 60 秒刷新，支持登录自启动及异常退出恢复。

![界面预览：演示数据](assets/preview.png)

> 截图使用合成演示数据，不包含真实账号信息。本项目为社区定制版本，与 OpenAI 无隶属或背书关系。来源与许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 功能

- 深色渐变圆角卡片，圆头细圆环、独立月度额度区域和较大的文字。
- 双圆环尺寸约 250 × 268 像素，可切换为仅 5 小时或仅每周模式。
- 外环显示剩余额度，细内环显示重置前的剩余时间比例；下方显示重置日期与时间。
- 月度进度条显示剩余比例、余额 / 总额和重置倒计时；无数据时显示“额度暂不可用”。
- 拖动、锁定位置、置顶、收起到托盘、手动刷新、单实例运行。
- 使用本机 Codex 登录，不需要另外填写 API key，也不需要复制认证文件。
- 由 Windows 任务计划程序独立启动，守护程序在组件意外退出后重试。

## 环境要求

- Windows 10 / 11。
- Python 3.11+，包含 Tkinter 与同目录下的 `pythonw.exe`。
- 已安装 Codex CLI 或 Codex 桌面客户端，且已通过 ChatGPT 账号登录。
- 网络可用。中文绘图使用 Windows 微软雅黑字体。

月度额度需要账号接口返回 `individualLimit`。没有设置个人月度上限的账号可能不显示该项。

## 安装

在 PowerShell 中克隆到准备长期保留的目录：

```powershell
git clone https://github.com/changyongyu/codex-usage-rings.git
cd codex-usage-rings
python -m venv .venv
.\install.ps1 -PythonPath '.\.venv\Scripts\python.exe'
```

脚本会安装运行依赖、注册当前用户的 `CodexUsageRings` 登录启动任务、创建桌面 **Codex Usage Rings** 快捷方式并启动组件。普通用户权限运行；如设备策略限制任务注册，请按组织策略处理。

如果系统阻止运行 `.ps1`，可检查脚本后，仅对本次执行使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -PythonPath '.\.venv\Scripts\python.exe'
```

`-SkipDependencies` 跳过依赖安装，`-NoStart` 只配置、不立即启动。安装脚本会拒绝覆盖另一目录的同名部署，也会拒绝更新仍在运行的组件。**不要在安装完成后移动源码或虚拟环境目录。**

## 使用

| 操作 | 效果 |
| --- | --- |
| 左键拖动 | 移动；锁定时先右键解锁 |
| 右键 | 刷新、锁定、置顶、显示模式或退出 |
| 双击卡片 | 收起到托盘 |
| 双击托盘图标 | 恢复窗口 |
| 单击托盘图标 | 双圆环模式下切换托盘显示的 5 小时 / 每周百分比 |
| 右键“退出” | 正常结束组件和本次守护，不会立即重新弹出 |

主动退出后，双击桌面快捷方式可再次打开，下次登录仍会自启动。

### 读懂额度

- **5 小时 / 每周**：显示账号相应窗口的剩余百分比，不是当前聊天的 token 使用量。
- **月度额度**：工作空间所有者给当前用户设置的个人月度额度，不等于整个工作空间共享余额。
- **颜色**：5 小时额度充足时为薄荷绿，每周额度充足时为淡紫蓝；剩余 10%～30% 为琥珀色，低于 10% 为柔红色。
- **重置时间**：圆环下方使用本机时区，格式“日/月 时:分”；月度使用倒计时。
- **状态点**：薄荷绿为就绪、琥珀色为运行中、空心为未检测到 Codex、柔红色为检测异常。状态由本地事件推断，可能有延迟。

用量每 60 秒查询，显示也可能受服务端更新延迟影响。缺失数据与真实的 0% 会分别处理。

## 个性化

编辑 `codex_usage_widget.py` 后重新启动组件：

| 设置 | 默认值 | 作用 |
| --- | --- | --- |
| `UI_SCALE` | `1.25` | 整体缩放，字体随面板一起放大 |
| `POLL_SECONDS` | `60` | 查询间隔（秒） |
| `WIDGET_W_BOTH` / `WIDGET_H` | `200` / `214` | 缩放前设计尺寸 |
| `RENDER_SCALE` | `4` | 绘图抗锯齿采样倍率，不是界面缩放 |

## 工作方式

```text
桌面快捷方式 → start_widget.py → Windows 任务 CodexUsageRings
Windows 登录 ───────────────────→ Windows 任务 CodexUsageRings
任务 → launch_supervised.py → codex_usage_widget.py → codex_usage.py → Codex App Server
```

正常数据路径使用 `account/rateLimits/read`，认证交给已安装的 Codex 管理。月度余额使用十进制上限减已用值计算，不写死额度或重置日期。已移除上游直接读取或更新认证文件的旧代码。

## 更新与卸载

更新前先右键退出组件，随后：

```powershell
git pull
.\install.ps1 -PythonPath '.\.venv\Scripts\python.exe'
```

卸载任务和桌面快捷方式：

```powershell
.\uninstall.ps1
```

卸载保留源码、设置和日志，不删除 Codex 登录或会话数据。详细故障排查见 [OPERATIONS.md](OPERATIONS.md)。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\render_preview.py
```

预览脚本使用演示数据，不查询账号。本地测试覆盖月度额度解析，安装脚本可通过 PowerShell 语法检查；这些检查不代替真实桌面、多显示器或任务注册的实机验证。当前发布不包含 GitHub Actions 工作流。

## 来源与许可

双圆环和托盘界面基于 [maximevaulch/codex-usage-widget](https://github.com/maximevaulch/codex-usage-widget)；App Server 读取模块基于 [Wannatep/codex-usage-mini-widget](https://github.com/Wannatep/codex-usage-mini-widget)。

上游双圆环项目未提供开源许可证，本项目保留 GitHub fork 来源关系，**不将全部代码重新声明为 MIT 或其他开源许可**。读取模块的原始 Unlicense 文本保存在 [licenses](licenses/codex-usage-mini-widget-UNLICENSE.txt)。各部分权利说明详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 隐私

不要上传 Codex 认证文件、日志、个人设置或真实额度截图。项目 `.gitignore` 已排除常见状态文件；公开前仍应检查提交内容。组件日志包含额度与本地诊断信息，分享前请检查。
