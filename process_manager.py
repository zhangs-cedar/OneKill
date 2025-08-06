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


class ProcessManager(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.current_processes = []
        self.saved_processes = set()
        self.init_ui()
        self.refresh_processes()
        
    def init_ui(self):
        self.setWindowTitle("进程管理工具")
        self.setGeometry(100, 100, 500, 300)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        # 状态显示
        self.status_label = QLabel("正在扫描进程...")
        layout.addWidget(self.status_label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 保存当前进程列表")
        self.save_btn.clicked.connect(self.save_current_processes)
        self.save_btn.setStyleSheet("background-color: #28a745; color: white; padding: 10px;")
        button_layout.addWidget(self.save_btn)
        
        self.kill_btn = QPushButton("🗑️ 关闭其他进程")
        self.kill_btn.clicked.connect(self.kill_other_processes)
        self.kill_btn.setStyleSheet("background-color: #dc3545; color: white; padding: 10px;")
        button_layout.addWidget(self.kill_btn)
        
        layout.addLayout(button_layout)
        
        # 日志区域
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        layout.addWidget(QLabel("操作日志:"))
        layout.addWidget(self.log_text)
        
    def refresh_processes(self):
        try:
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], 
                                  capture_output=True, text=True, encoding='gbk')
            
            if result.returncode == 0:
                processes = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip('"').split('","')
                        if len(parts) >= 4:
                            process_info = {
                                'name': parts[0].strip('"'),
                                'memory': parts[3].strip('"')
                            }
                            processes.append(process_info)
                
                # 合并相同名称的进程
                self.current_processes = self.merge_processes(processes)
                self.update_status()
                
        except Exception as e:
            self.log_text.append(f"刷新进程列表失败: {e}")
    
    def merge_processes(self, processes):
        process_groups = {}
        
        for process in processes:
            name = process['name']
            if name not in process_groups:
                process_groups[name] = {'count': 1, 'name': name}
            else:
                process_groups[name]['count'] += 1
        
        merged = []
        for name, info in process_groups.items():
            if info['count'] > 1:
                display_name = f"{name} ({info['count']})"
            else:
                display_name = name
            merged.append({'name': display_name, 'original_name': name})
        
        return merged
    
    def update_status(self):
        self.status_label.setText(f"当前进程数: {len(self.current_processes)}")
    
    def save_current_processes(self):
        if not self.current_processes:
            QMessageBox.warning(self, "警告", "没有可保存的进程！")
            return
        
        process_names = [p['original_name'] for p in self.current_processes]
        
        if self.config_manager.save_processes(process_names):
            self.saved_processes = set(process_names)
            self.log_text.append("✅ 进程列表已保存到 config.yaml")
            QMessageBox.information(self, "成功", "进程列表已保存！")
        else:
            self.log_text.append("❌ 保存进程列表失败")
    
    def kill_other_processes(self):
        # 重新读取config.yaml文件
        saved_processes_list = self.config_manager.load_processes()
        if not saved_processes_list:
            QMessageBox.warning(self, "警告", "config.yaml文件不存在或为空，请先保存进程列表！")
            return
        
        self.saved_processes = set(saved_processes_list)
        self.log_text.append(f"📖 从config.yaml加载了 {len(self.saved_processes)} 个保存的进程")
        
        current_names = {p['original_name'] for p in self.current_processes}
        to_kill = current_names - self.saved_processes
        
        if not to_kill:
            QMessageBox.information(self, "提示", "没有需要关闭的进程！")
            return
        
        reply = QMessageBox.question(
            self, "确认操作",
            f"确定要关闭以下 {len(to_kill)} 个进程吗？\n" + 
            "\n".join(list(to_kill)[:10]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for process_name in to_kill:
                try:
                    result = subprocess.run(['taskkill', '/IM', process_name, '/F'],
                                          capture_output=True, text=True, encoding='gbk')
                    
                    success = result.returncode == 0
                    self.log_text.append(f"[{'✓' if success else '✗'}] {process_name}")
                    
                except Exception as e:
                    self.log_text.append(f"[✗] {process_name}: 错误 - {str(e)}")
            
            self.log_text.append("批量关闭操作完成！")
            self.refresh_processes()


class SystemTrayApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.tray_icon = None
        self.process_manager = None
        self.init_tray()
        
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        menu = QMenu()
        
        save_action = menu.addAction("💾 保存当前进程列表")
        save_action.triggered.connect(self.show_process_manager)
        
        menu.addSeparator()
        
        kill_action = menu.addAction("🗑️ 关闭其他进程")
        kill_action.triggered.connect(self.kill_other_processes)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("进程管理工具")
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.show()
        
    def show_process_manager(self):
        if not self.process_manager:
            self.process_manager = ProcessManager()
        
        self.process_manager.show()
        self.process_manager.raise_()
        self.process_manager.activateWindow()
    
    def kill_other_processes(self):
        if not self.process_manager:
            self.process_manager = ProcessManager()
        
        self.process_manager.kill_other_processes()


def main():
    app = SystemTrayApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 