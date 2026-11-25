# Codex Recovery

Codex Recovery 是一个 Windows 托盘常驻程序。它通过 UI Automation 监听当前 Codex 窗口，在检测到模型容量错误时，对最新错误卡片中的“重试”按钮执行一次点击。在检测到明确的重试限制错误及其同一对话框中的“继续”按钮时，也会执行一次继续操作。单独出现的“继续”按钮会被保留给用户处理，以免恢复用户手动暂停的对话。

程序启动后立即检查一次，之后默认每 15 秒检查一次。检查周期可以通过配置文件中的 `interval_seconds` 调整，范围为 10 到 20 秒。

同一张错误卡片只处理一次。错误卡片消失后，下一张新出现的错误卡片可以再次触发处理。

## 开发运行

使用已安装依赖的 Python 环境运行托盘程序。

```powershell
python -m codex_recovery.tray_app
```

托盘菜单提供监听启停、设置和退出。设置窗口可以控制登录 Windows 后自动启动，以及自动重试通知。

配置文件默认写入 `%APPDATA%\CodexRecovery\config.json`，日志写入同目录下的 `codex-recovery.log`。

## 打包

项目提供 PyInstaller spec 和 PowerShell 构建脚本。安装 PyInstaller 后运行：

```powershell
.\packaging\build.ps1 -Python "C:\path\to\python.exe"
```

生成文件为 `dist\CodexRecovery\CodexRecovery.exe`。运行时请保留这个目录中的依赖文件。
