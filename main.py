import sys
import subprocess
import yaml
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class ConfigManager:
    def __init__(self, config_file="config.yaml"):
        self.config_file = config_file
        
    def save_processes(self, processes):
        config = {'saved_processes': processes}
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def load_processes(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('saved_processes', [])
        except Exception as e:
            print(f"加载配置失败: {e}")
        return []


class SystemTrayApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.tray_icon = None
        self.config_manager = ConfigManager()
        self.init_tray()
        
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        menu = QMenu()
        
        save_action = menu.addAction("💾 保存当前进程列表")
        save_action.triggered.connect(self.save_current_processes)
        
        menu.addSeparator()
        
        edit_action = menu.addAction("📝 编辑进程列表")
        edit_action.triggered.connect(self.edit_process_list)
        
        menu.addSeparator()
        
        kill_action = menu.addAction("🗑️ 关闭其他进程")
        kill_action.triggered.connect(self.kill_other_processes)
        
        force_kill_action = menu.addAction("💀 强制关闭其他进程")
        force_kill_action.triggered.connect(self.force_kill_other_processes)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("进程管理工具")
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.show()
    
    def edit_process_list(self):
        """用记事本打开config.yaml文件进行编辑"""
        try:
            if os.path.exists(self.config_manager.config_file):
                subprocess.Popen(['notepad.exe', self.config_manager.config_file])
                self.tray_icon.showMessage("编辑进程列表", "已用记事本打开 config.yaml 文件", QSystemTrayIcon.MessageIcon.Information, 2000)
            else:
                self.tray_icon.showMessage("文件不存在", "config.yaml 文件不存在，请先保存进程列表", QSystemTrayIcon.MessageIcon.Warning, 3000)
        except Exception as e:
            self.tray_icon.showMessage("打开失败", f"无法打开文件: {str(e)}", QSystemTrayIcon.MessageIcon.Critical, 3000)
    
    def get_current_processes(self):
        """获取当前进程列表"""
        try:
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], 
                                  capture_output=True, text=True, encoding='gbk')
            
            if result.returncode == 0:
                processes = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip('"').split('","')
                        if len(parts) >= 1:
                            name = parts[0].strip('"')
                            processes.append({'name': name})
                
                return self.merge_processes(processes)
                
        except Exception as e:
            print(f"获取进程列表失败: {e}")
            return []
        
        return []
    
    def merge_processes(self, processes):
        """合并相同名称的进程"""
        process_groups = {}
        
        for process in processes:
            name = process['name']
            if name not in process_groups:
                process_groups[name] = {
                    'count': 1, 
                    'name': name
                }
            else:
                process_groups[name]['count'] += 1
        
        merged = []
        for name, info in process_groups.items():
            if info['count'] > 1:
                display_name = f"{name} ({info['count']})"
            else:
                display_name = name
            merged.append({
                'name': display_name, 
                'original_name': name
            })
        
        return merged
    
    def save_current_processes(self):
        """保存当前进程列表"""
        current_processes = self.get_current_processes()
        
        if not current_processes:
            self.tray_icon.showMessage("保存失败", "没有可保存的进程！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        process_names = [p['original_name'] for p in current_processes]
        
        if self.config_manager.save_processes(process_names):
            self.tray_icon.showMessage(
                "保存成功", 
                f"已保存 {len(process_names)} 个进程到 config.yaml", 
                QSystemTrayIcon.MessageIcon.Information, 
                3000
            )
        else:
            self.tray_icon.showMessage("保存失败", "保存进程列表失败", QSystemTrayIcon.MessageIcon.Critical, 3000)
    
    def kill_other_processes(self):
        """关闭其他进程"""
        saved_processes_list = self.config_manager.load_processes()
        if not saved_processes_list:
            self.tray_icon.showMessage("警告", "config.yaml文件不存在或为空，请先保存进程列表！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        saved_processes = set(saved_processes_list)
        
        # 第一次关闭
        first_kill_result = self._kill_processes_once(saved_processes, show_confirm=True)
        
        if first_kill_result['total_killed'] == 0:
            self.tray_icon.showMessage("提示", "没有需要关闭的进程！", QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        
        # 等待2秒让进程完全关闭
        import time
        time.sleep(2)
        
        # 第二次检查并关闭新产生的进程（不显示确认对话框）
        second_kill_result = self._kill_processes_once(saved_processes, show_confirm=False)
        
        # 显示结果
        total_killed = first_kill_result['total_killed'] + second_kill_result['total_killed']
        total_attempted = first_kill_result['total_attempted']
        
        message = f"操作完成：共关闭 {total_killed} 个进程"
        if second_kill_result['total_killed'] > 0:
            message += f"\n其中 {second_kill_result['total_killed']} 个是重新启动的进程"
        
        self.tray_icon.showMessage("操作完成", message, QSystemTrayIcon.MessageIcon.Information, 5000)
    
    def _kill_processes_once(self, saved_processes, show_confirm=True):
        """执行一次进程关闭操作"""
        current_processes = self.get_current_processes()
        current_names = {p['original_name'] for p in current_processes}
        to_kill = current_names - saved_processes
        
        if not to_kill:
            return {'total_killed': 0, 'total_attempted': 0}
        
        # 只在第一次显示确认对话框
        if show_confirm:
            reply = QMessageBox.question(
                None, "确认操作",
                f"确定要关闭以下 {len(to_kill)} 个进程吗？\n" + 
                "\n".join(list(to_kill)[:10]),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return {'total_killed': 0, 'total_attempted': len(to_kill)}
        
        success_count = 0
        for process_name in to_kill:
            try:
                result = subprocess.run(['taskkill', '/IM', process_name, '/F'],
                                      capture_output=True, text=True, encoding='gbk')
                
                if result.returncode == 0:
                    success_count += 1
                
            except Exception as e:
                pass
        
        return {'total_killed': success_count, 'total_attempted': len(to_kill)}
    
    def force_kill_other_processes(self):
        """强制关闭其他进程（多次重试）"""
        saved_processes_list = self.config_manager.load_processes()
        if not saved_processes_list:
            self.tray_icon.showMessage("警告", "config.yaml文件不存在或为空，请先保存进程列表！", QSystemTrayIcon.MessageIcon.Warning, 3000)
            return
        
        saved_processes = set(saved_processes_list)
        
        # 执行多次关闭，每次间隔2秒
        total_killed = 0
        rounds = 3  # 最多执行3轮
        
        for round_num in range(rounds):
            result = self._force_kill_processes_once(saved_processes, round_num + 1)
            total_killed += result['total_killed']
            
            if result['total_killed'] == 0:
                break
            
            # 等待2秒后继续下一轮
            if round_num < rounds - 1:
                import time
                time.sleep(2)
        
        # 显示结果
        message = f"强制关闭完成：共关闭 {total_killed} 个进程"
        if rounds > 1:
            message += f"\n执行了 {rounds} 轮检查"
        
        self.tray_icon.showMessage("强制关闭完成", message, QSystemTrayIcon.MessageIcon.Information, 5000)
    
    def _force_kill_processes_once(self, saved_processes, round_num):
        """执行一次强制进程关闭操作"""
        current_processes = self.get_current_processes()
        current_names = {p['original_name'] for p in current_processes}
        to_kill = current_names - saved_processes
        
        if not to_kill:
            return {'total_killed': 0, 'total_attempted': 0}
        
        # 显示确认对话框
        reply = QMessageBox.question(
            None, f"确认第{round_num}轮操作",
            f"第{round_num}轮：发现 {len(to_kill)} 个需要关闭的进程\n" + 
            "\n".join(list(to_kill)[:10]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return {'total_killed': 0, 'total_attempted': len(to_kill)}
        
        success_count = 0
        for process_name in to_kill:
            try:
                # 使用更强力的关闭方式
                result = subprocess.run(['taskkill', '/IM', process_name, '/F', '/T'],
                                      capture_output=True, text=True, encoding='gbk')
                
                if result.returncode == 0:
                    success_count += 1
                else:
                    # 如果taskkill失败，尝试用wmic强制终止
                    wmic_result = subprocess.run(['wmic', 'process', 'where', f'name="{process_name}"', 'call', 'terminate'],
                                               capture_output=True, text=True, encoding='gbk')
                    if wmic_result.returncode == 0:
                        success_count += 1
                
            except Exception as e:
                pass
        
        return {'total_killed': success_count, 'total_attempted': len(to_kill)}


def main():
    app = SystemTrayApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 