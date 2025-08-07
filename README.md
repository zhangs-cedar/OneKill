# OneKill - 进程管理工具
一个简洁高效的Windows进程管理工具，运行在系统托盘中。

## 使用方法
1. **保存进程列表**
    - 右键托盘图标 → "💾 保存当前进程"
    - 将当前运行的进程保存为白名单
2. **关闭其他进程**
    - 右键托盘图标 → "🗑️ 关闭其他进程"
    - 确认后自动关闭不在白名单中的进程

### 关闭机制
1. 使用 `taskkill /F /T` 强制关闭进程树
2. 如果失败，使用 `wmic` 命令强制终止
3. 最多执行3轮检查，每轮间隔2秒

## 配置文件
软件使用 `config.yaml` 文件保存进程白名单：

```yaml
saved_processes:
  - notepad.exe
  - chrome.exe
  - code.exe
```

## 安装运行
```bash
pip install -r requirements.txt
python main.py
```

