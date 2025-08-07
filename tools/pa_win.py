import os
import sys
import shutil
import subprocess
import time
import argparse
import zipfile
from pathlib import Path
from datetime import datetime


def run_cmd(cmd, check=True):
    """运行命令"""
    print(f'执行: {" ".join(cmd)}')
    start_time = time.time()

    # 实时显示输出
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True
    )

    for line in process.stdout:
        print(f'  {line.rstrip()}')

    process.wait()
    result = subprocess.CompletedProcess(cmd, process.returncode, '', '')

    elapsed_time = time.time() - start_time
    print(f'  完成 (耗时: {elapsed_time:.1f}秒)')

    if result.returncode != 0 and check:
        print(f'错误: {result.stderr}')
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    return result


def count_python_files(directory):
    """统计目录中的 Python 文件数量"""
    count = 0
    for path in Path(directory).rglob('*.py'):
        if path.name != '__init__.py':
            count += 1
    return count


def create_zip_archive(source_dir, output_name):
    """创建压缩包"""
    print(f'步骤 9/9: 创建压缩包 {output_name}...')

    with zipfile.ZipFile(output_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
                print(f'  ✓ 添加: {arcname}')

    # 获取压缩包大小
    zip_size = os.path.getsize(output_name) / (1024 * 1024)  # MB
    print(f'  ✓ 压缩包创建完成: {output_name} ({zip_size:.1f} MB)')


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Cedar Ex 轻量化打包工具 (Windows版本)')
    parser.add_argument('--no-venv', action='store_true', help='不复制虚拟环境，只打包源码')
    parser.add_argument('--no-compress', action='store_true', help='不创建压缩包')
    args = parser.parse_args()

    # 配置
    # 从 tools 目录运行时，项目根目录是上级目录
    script_dir = Path(__file__).parent
    if script_dir.name == 'tools':
        project_root = script_dir.parent
    else:
        project_root = script_dir

    dist_dir = project_root / 'dist' / 'main.dist'
    conda_env = project_root / 'env'  # 基于项目根目录拼接env目录
    python_exe = str(conda_env / 'python.exe')

    print('=' * 60)
    print('Cedar Ex 轻量化打包工具 (Windows版本)')
    print('=' * 60)
    print(f'虚拟环境复制: {"否" if args.no_venv else "是"}')
    print(f'创建压缩包: {"否" if args.no_compress else "是"}')
    print('-' * 60)

    # 统计文件数量
    app_ui_files = count_python_files(project_root / 'app_ui')
    scripts_files = count_python_files(project_root / 'scripts')
    total_files = app_ui_files + scripts_files + 1  # +1 for main.py

    print(f'项目根目录: {project_root}')
    print(f'输出目录: {dist_dir}')
    print(f'Conda 环境: {conda_env}')
    print(f'需要编译的文件: {total_files} 个')
    print(f'  - app_ui: {app_ui_files} 个')
    print(f'  - scripts: {scripts_files} 个')
    print(f'  - main.py: 1 个')
    print('-' * 60)

    start_time = time.time()

    try:
        # 清理目录
        print('步骤 1/7: 清理打包目录...')
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True)
        print('  ✓ 清理完成')

        # 构建 app_ui 模块
        print(f'步骤 2/8: 构建 app_ui 模块 ({app_ui_files} 个文件)...')
        app_ui_dir = dist_dir / 'app_ui'
        app_ui_dir.mkdir()

        current_file = 0
        for py_file in (project_root / 'app_ui').glob('*.py'):
            if py_file.name == '__init__.py':
                continue
            current_file += 1
            print(f'  [{current_file}/{app_ui_files}] 构建: {py_file.name}')
            run_cmd([python_exe, '-m', 'nuitka', '--module', f'--output-dir={app_ui_dir}', str(py_file)])

        # 构建 scripts 模块
        print(f'步骤 3/8: 构建 scripts 模块 ({scripts_files} 个文件)...')
        scripts_dir = dist_dir / 'scripts'

        def build_scripts_recursive(src_path, dst_path, current_count):
            dst_path.mkdir(parents=True, exist_ok=True)

            for item in src_path.iterdir():
                if item.is_file() and item.suffix == '.py':
                    if item.name == '__init__.py':
                        continue
                    current_count[0] += 1
                    print(
                        f'  [{current_count[0]}/{scripts_files}] 构建脚本: {item.relative_to(project_root / "scripts")}'
                    )
                    run_cmd([python_exe, '-m', 'nuitka', '--module', f'--output-dir={dst_path}', str(item)])
                elif item.is_dir():
                    build_scripts_recursive(item, dst_path / item.name, current_count)
                elif item.is_file():
                    shutil.copy2(item, dst_path / item.name)

        current_count = [0]
        build_scripts_recursive(project_root / 'scripts', scripts_dir, current_count)

        # 构建主程序
        print('步骤 4/8: 构建主程序...')
        run_cmd([python_exe, '-m', 'nuitka', '--module', f'--output-dir={dist_dir}', str(project_root / 'main.py')])

        # 复制虚拟环境（可选）
        if not args.no_venv:
            print('步骤 5/8: 复制虚拟环境...')
            venv_dir = dist_dir / 'my_venv'
            shutil.copytree(conda_env, venv_dir)
            print('  ✓ 虚拟环境复制完成')

            # 清理虚拟环境
            print('步骤 6/8: 清理虚拟环境...')
            cleaned_files = 0
            for pattern in ['__pycache__', '*.pyc', '*.pyo']:
                for path in venv_dir.rglob(pattern):
                    if path.is_dir():
                        shutil.rmtree(path)
                        cleaned_files += 1
                    else:
                        path.unlink()
                        cleaned_files += 1
            print(f'  ✓ 清理了 {cleaned_files} 个缓存文件')
        else:
            print('步骤 5/8: 跳过虚拟环境复制...')
            print('  ✓ 已跳过虚拟环境复制')
            print('步骤 6/8: 跳过虚拟环境清理...')
            print('  ✓ 已跳过虚拟环境清理')

        # 复制额外文件
        print('步骤 7/8: 复制额外文件...')
        for extra_dir in ['configs', 'log']:
            src = project_root / extra_dir
            if src.exists():
                shutil.copytree(src, dist_dir / extra_dir)
                print(f'  ✓ 复制 {extra_dir} 目录')

        # 复制图标文件
        icon_src = project_root / 'app_ui' / 'icon.ico'
        if icon_src.exists():
            icon_dst = dist_dir / 'app_ui' / 'icon.ico'
            shutil.copy2(icon_src, icon_dst)
            print(f'  ✓ 复制图标文件: icon.ico')
        else:
            print(f'  ⚠ 图标文件不存在: {icon_src}')

        # 创建启动脚本 (Windows批处理文件)
        print('步骤 8/8: 创建启动脚本...')
        run_script = dist_dir / 'run.bat'

        # 使用虚拟环境中的Python
        script_content = """@echo off
REM 设置 Python 环境
set PYTHONPATH=%CD%/app_ui;%CD%/scripts;%PYTHONPATH%
REM 使用虚拟环境中的 Python 运行主程序
"%CD%/my_venv/python.exe" -c "import sys; import os; sys.path.insert(0, r'%CD%'); import main; from PyQt6.QtWidgets import QApplication; app = QApplication(sys.argv); from main import ScriptExecutorUI; win = ScriptExecutorUI(); win.show(); sys.exit(app.exec())"
pause
"""

        with open(run_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        print('  ✓ 创建启动脚本: run.bat')

        # 创建 VBS 启动脚本 (无窗口运行)
        run_vbs_script = dist_dir / 'run.vbs'
        vbs_content = """Set ws = CreateObject("WScript.Shell")
ws.Run "run.bat", 0"""

        with open(run_vbs_script, 'w', encoding='utf-8') as f:
            f.write(vbs_content)
        print('  ✓ 创建启动脚本: run.vbs')

        # 创建压缩包（可选）
        if not args.no_compress:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_name = f'cedar_ex_{timestamp}.zip'
            zip_path = project_root / 'dist' / zip_name
            create_zip_archive(dist_dir, zip_path)

        total_time = time.time() - start_time

        print('=' * 60)
        print('🎉 打包完成！')
        print('=' * 60)
        print(f'输出目录: {dist_dir}')
        if not args.no_compress:
            print(f'压缩包: {zip_path}')
        print(f'总耗时: {total_time:.1f} 秒')
        print(f'平均每个文件: {total_time / total_files:.1f} 秒')
        print('\n运行方式:')
        print(f'  cd {dist_dir}')
        print('  run.bat 或 run.vbs 运行')
        print('=' * 60)

    except Exception as e:
        total_time = time.time() - start_time
        print(f'\n❌ 打包失败 (耗时: {total_time:.1f} 秒)')
        print(f'错误信息: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()