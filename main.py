import sys
import subprocess
import yaml
import os
import time
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class ProcessManager:
    """进程管理器 - 精简版"""
    
    # 系统关键进程白名单，防止误杀
    SYSTEM_PROCESSES = {
        'System', 'svchost.exe', 'explorer.exe', 'winlogon.exe', 'csrss.exe',
        'wininit.exe', 'services.exe', 'lsass.exe', 'spoolsv.exe', 'taskmgr.exe',
        'conhost.exe', 'dwm.exe', 'rundll32.exe', 'ctfmon.exe', 'winlogon.exe',
        'smss.exe', 'wininit.exe', 'lsass.exe', 'csrss.exe', 'winlogon.exe',
        'services.exe', 'spoolsv.exe', 'svchost.exe', 'explorer.exe', 'taskmgr.exe',
        'conhost.exe', 'dwm.exe', 'rundll32.exe', 'ctfmon.exe', 'winlogon.exe'
    }
    
    def __init__(self, config_file="config.yaml"):
        self.config_file = config_file
        
    def save_processes(self, processes):
        """保存进程列表到配置文件"""
        config = {'saved_processes': processes}
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def load_processes(self):
        """从配置文件加载进程列表"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('saved_processes', [])
        except Exception as e:
            print(f"加载配置失败: {e}")
        return []
    
    def get_current_processes(self):
        """获取当前进程列表"""
        try:
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], 
                                  capture_output=True, text=True, encoding='gbk')
            
            if result.returncode == 0:
                processes = set()
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip('"').split('","')
                        if len(parts) >= 1:
                            name = parts[0].strip('"')
                            processes.add(name)
                
                return processes
                
        except Exception as e:
            print(f"获取进程列表失败: {e}")
            return set()
        
        return set()
    
    def kill_processes(self, processes_to_kill, max_rounds=3):
        """关闭指定进程，支持多轮重试"""
        total_killed = 0
        
        for round_num in range(max_rounds):
            killed_this_round = 0
            
            for process_name in processes_to_kill:
                if self._kill_single_process(process_name):
                    killed_this_round += 1
            
            total_killed += killed_this_round
            
            # 如果没有进程被关闭，或者已经是最后一轮，则停止
            if killed_this_round == 0 or round_num == max_rounds - 1:
                break
            
            # 等待2秒后继续下一轮
            time.sleep(2)
        
        return total_killed
    
    def _kill_single_process(self, process_name):
        """关闭单个进程"""
        try:
            # 使用taskkill强制关闭进程树
            result = subprocess.run(['taskkill', '/IM', process_name, '/F', '/T'],
                                  capture_output=True, text=True, encoding='gbk')
            
            if result.returncode == 0:
                return True
            
            # 如果taskkill失败，尝试用wmic强制终止
            wmic_result = subprocess.run(['wmic', 'process', 'where', f'name="{process_name}"', 'call', 'terminate'],
                                       capture_output=True, text=True, encoding='gbk')
            
            return wmic_result.returncode == 0
            
        except Exception as e:
            print(f"关闭进程 {process_name} 时出错: {e}")
            return False


class SystemTrayApp(QApplication):
    """系统托盘应用"""
    
    def __init__(self, argv):
        super().__init__(argv)
        self.process_manager = ProcessManager()
        self.init_tray()
        
    def init_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        
        menu = QMenu()
        
        # 保存当前进程列表
        save_action = menu.addAction("💾 保存当前进程")
        save_action.triggered.connect(self.save_current_processes)
        
        menu.addSeparator()
        
        # 关闭其他进程
        kill_action = menu.addAction("🗑️ 关闭其他进程")
        kill_action.triggered.connect(self.kill_other_processes)
        
        menu.addSeparator()
        
        # 退出
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("进程管理工具")
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.show()
    
    def save_current_processes(self):
        """保存当前进程列表"""
        current_processes = self.process_manager.get_current_processes()
        
        if not current_processes:
            self.tray_icon.showMessage("保存失败", "没有可保存的进程！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        # 过滤掉系统关键进程
        safe_processes = current_processes - ProcessManager.SYSTEM_PROCESSES
        
        if self.process_manager.save_processes(list(safe_processes)):
            self.tray_icon.showMessage(
                "保存成功", 
                f"已保存 {len(safe_processes)} 个进程到 config.yaml", 
                QSystemTrayIcon.MessageIcon.Information, 
                3000
            )
        else:
            self.tray_icon.showMessage("保存失败", "保存进程列表失败", QSystemTrayIcon.MessageIcon.Critical, 3000)
    
    def kill_other_processes(self):
        """关闭其他进程"""
        saved_processes_list = self.process_manager.load_processes()
        if not saved_processes_list:
            self.tray_icon.showMessage("警告", "config.yaml文件不存在或为空，请先保存进程列表！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        saved_processes = set(saved_processes_list)
        current_processes = self.process_manager.get_current_processes()
        
        # 计算需要关闭的进程（排除保存的进程和系统进程）
        to_kill = current_processes - saved_processes - ProcessManager.SYSTEM_PROCESSES
        
        if not to_kill:
            self.tray_icon.showMessage("提示", "没有需要关闭的进程！", QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        
        # 显示确认对话框
        reply = QMessageBox.question(
            None, "确认关闭操作",
            f"确定要关闭以下 {len(to_kill)} 个进程吗？\n" + 
            "\n".join(list(to_kill)[:10]) + "\n\n将执行最多3轮检查",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 执行关闭操作
        total_killed = self.process_manager.kill_processes(to_kill)
        
        # 显示结果
        message = f"关闭完成：共关闭 {total_killed}/{len(to_kill)} 个进程"
        if total_killed < len(to_kill):
            message += f"\n{len(to_kill) - total_killed} 个进程可能仍在运行"
        
        self.tray_icon.showMessage("操作完成", message, QSystemTrayIcon.MessageIcon.Information, 5000)


def main():
    """主函数"""
    app = SystemTrayApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 