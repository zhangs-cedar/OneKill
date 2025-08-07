import sys
import subprocess
import yaml
import os
import time
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QMessageBox


class ProcMgr:
    """进程管理器"""
    
    # 系统进程白名单
    SYSTEM_PROCS = {
        'System', 'svchost.exe', 'explorer.exe', 'winlogon.exe', 'csrss.exe',
        'wininit.exe', 'services.exe', 'lsass.exe', 'spoolsv.exe', 'taskmgr.exe',
        'conhost.exe', 'dwm.exe', 'rundll32.exe', 'ctfmon.exe', 'smss.exe'
    }
    
    def __init__(self, config="config.yaml"):
        self.config = config
        
    def save(self, procs):
        """保存进程列表"""
        try:
            with open(self.config, 'w', encoding='utf-8') as f:
                yaml.dump({'saved_processes': procs}, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False
    
    def load(self):
        """加载进程列表"""
        try:
            if os.path.exists(self.config):
                with open(self.config, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f).get('saved_processes', [])
        except Exception as e:
            print(f"加载失败: {e}")
        return []
    
    def get_procs(self):
        """获取当前进程"""
        try:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'], 
                capture_output=True, text=True, encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return {line.strip('"').split('","')[0].strip('"') 
                       for line in result.stdout.strip().split('\n') if line.strip()}
                
        except Exception as e:
            print(f"获取进程失败: {e}")
        return set()
    
    def kill(self, procs, rounds=3):
        """关闭进程，支持多轮重试"""
        total = 0
        
        for round_num in range(rounds):
            killed = 0
            
            for proc in procs:
                if self._kill_one(proc):
                    killed += 1
            
            total += killed
            
            if killed == 0 or round_num == rounds - 1:
                break
            
            time.sleep(2)
        
        return total
    
    def _kill_one(self, proc):
        """关闭单个进程"""
        try:
            # 先用taskkill
            result = subprocess.run(
                ['taskkill', '/IM', proc, '/F', '/T'],
                capture_output=True, text=True, encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return True
            
            # 失败则用wmic
            wmic_result = subprocess.run(
                ['wmic', 'process', 'where', f'name="{proc}"', 'call', 'terminate'],
                capture_output=True, text=True, encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return wmic_result.returncode == 0
            
        except Exception as e:
            print(f"关闭 {proc} 失败: {e}")
            return False


class TrayApp(QApplication):
    """系统托盘应用"""
    
    def __init__(self, argv):
        super().__init__(argv)
        self.mgr = ProcMgr()
        self._init_tray()
        
    def _init_tray(self):
        """初始化托盘"""
        self.tray = QSystemTrayIcon(self)
        
        menu = QMenu()
        
        save_action = menu.addAction("💾 保存当前进程")
        save_action.triggered.connect(self.save_procs)
        
        menu.addSeparator()
        
        kill_action = menu.addAction("🗑️ 关闭其他进程")
        kill_action.triggered.connect(self.kill_others)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit)
        
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("进程管理工具")
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.show()
    
    def save_procs(self):
        """保存当前进程"""
        procs = self.mgr.get_procs()
        
        if not procs:
            self.tray.showMessage("保存失败", "没有可保存的进程！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        # 过滤系统进程
        safe_procs = procs - ProcMgr.SYSTEM_PROCS
        
        if self.mgr.save(list(safe_procs)):
            self.tray.showMessage(
                "保存成功", 
                f"已保存 {len(safe_procs)} 个进程", 
                QSystemTrayIcon.MessageIcon.Information, 
                3000
            )
        else:
            self.tray.showMessage("保存失败", "保存进程列表失败", QSystemTrayIcon.MessageIcon.Critical, 3000)
    
    def kill_others(self):
        """关闭其他进程"""
        saved_procs = set(self.mgr.load())
        if not saved_procs:
            self.tray.showMessage("警告", "请先保存进程列表！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        current_procs = self.mgr.get_procs()
        
        # 计算需关闭的进程
        to_kill = current_procs - saved_procs - ProcMgr.SYSTEM_PROCS
        
        if not to_kill:
            self.tray.showMessage("提示", "没有需要关闭的进程！", QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            None, "确认关闭",
            f"确定要关闭 {len(to_kill)} 个进程吗？\n" + 
            "\n".join(list(to_kill)[:10]) + "\n\n将执行最多3轮检查",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 执行关闭
        killed = self.mgr.kill(to_kill)
        
        # 显示结果
        msg = f"关闭完成：{killed}/{len(to_kill)} 个进程"
        if killed < len(to_kill):
            msg += f"\n{len(to_kill) - killed} 个进程可能仍在运行"
        
        self.tray.showMessage("操作完成", msg, QSystemTrayIcon.MessageIcon.Information, 5000)


def main():
    """主函数"""
    app = TrayApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 