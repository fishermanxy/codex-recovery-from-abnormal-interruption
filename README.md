# Codex Recovery

Codex Recovery 是一个 Windows 托盘常驻程序。它通过 UI Automation 监听当前 Codex 窗口，在检测到模型容量错误时，对最新错误卡片中的“重试”按钮执行一次点击。在检测到明确的重试限制错误及其同一对话框中的“继续”按钮时，也会执行一次继续操作。对于输入框旁的“继续”，要求当前对话的末尾是包含图标和错误文字的重试失败卡片，且输入框为空。错误后的新消息或停止提示会阻止恢复，点击前会再次检查错误上下文。单独出现的“继续”按钮会被保留给用户处理，以免恢复用户手动暂停的对话。

程序启动后立即检查一次，之后默认每 15 秒检查一次。检查周期可以通过配置文件中的 `interval_seconds` 调整，范围为 10 到 20 秒。

通过 `CodexRecovery.exe` 统一启动。它会打开 Codex，或连接到已运行的 Codex，并在 Codex 进程退出后自动退出。隐藏窗口、最小化或暂停监听时仍会跟踪 Codex 进程。可以将此程序的快捷方式放到桌面或固定到任务栏，作为日常启动入口。从 Codex 原有快捷方式单独启动时，需要另行启动本程序。

首次使用此模式会移除本程序旧的 Windows 登录自启动注册，并清除旧配置中的 `autostart` 标志。

同一张错误卡片只处理一次。错误卡片消失后，下一张新出现的错误卡片可以再次触发处理。

## 开发运行

使用已安装依赖的 Python 环境运行托盘程序。

```powershell
python -m codex_recovery.tray_app
```

托盘菜单提供监听启停、设置和退出。设置窗口可以控制监听和自动重试通知。托盘“退出”会结束恢复程序，Codex 可继续运行。

配置文件默认写入 `%APPDATA%\CodexRecovery\config.json`，日志写入同目录下的 `codex-recovery.log`。

## 打包

项目提供 PyInstaller spec 和 PowerShell 构建脚本。安装 PyInstaller 后运行：

```powershell
.\packaging\build.ps1 -Python "C:\path\to\python.exe"
```

生成文件为 `dist\CodexRecovery\CodexRecovery.exe`。运行时请保留这个目录中的依赖文件。

## 许可证与图标

项目原创代码和文档采用 [MIT 许可证](LICENSE)。第三方内容及其原始许可、署名见 [第三方声明](THIRD_PARTY_NOTICES.md)。

项目图标（`assets/codex-recovery.png` 和 `assets/codex-recovery.ico`）由作者使用 Codex 辅助生成。在作者有权授权的范围内，图标按 MIT 许可证提供。
