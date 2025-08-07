import os
import sys
import shutil
import subprocess
import time
import argparse
from pathlib import Path


def run(cmd, check=True):
    """运行命令"""
    print(f'执行: {" ".join(cmd)}')
    start = time.time()

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, bufsize=1, universal_newlines=True
    )

    for line in process.stdout:
        print(f'  {line.rstrip()}')

    process.wait()
    result = subprocess.CompletedProcess(cmd, process.returncode, '', '')

    elapsed = time.time() - start
    print(f'  完成 (耗时: {elapsed:.1f}秒)')

    if result.returncode != 0 and check:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    return result


def main():
    parser = argparse.ArgumentParser(description='OneKill 打包工具')
    args = parser.parse_args()

    # 配置路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent if script_dir.name == 'tools' else script_dir
    dist_dir = project_root / 'dist'
    main_py = project_root / 'main.py'
    config_yaml = project_root / 'config.yaml'

    print('=' * 50)
    print('OneKill 打包工具')
    print('=' * 50)
    print(f'项目根目录: {project_root}')
    print(f'输出目录: {dist_dir}')
    print('-' * 50)

    start = time.time()

    try:
        # 清理目录
        print('步骤 1/3: 清理打包目录...')
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True, exist_ok=True)
        print('  ✓ 清理完成')

        # 构建命令
        print('步骤 2/3: 使用 Nuitka 编译...')
        
        cmd = [
            'python', '-m', 'nuitka',
            '--follow-imports',
            '--enable-plugin=pyqt6',
            '--include-data-files=config.yaml=config.yaml',
            '--include-package=PyQt6',
            '--include-package=yaml',
            '--windows-disable-console',
            '--assume-yes-for-downloads',
            '--standalone',
            '--onefile',
            '--output-dir=' + str(dist_dir),
            '--output-filename=OneKill.exe',
            str(main_py)
        ]
        
        # 添加图标（如果存在）
        icon_path = project_root / 'icon.ico'
        if icon_path.exists():
            cmd.insert(-1, f'--windows-icon-from-ico={icon_path}')

        run(cmd)

        # 复制文件
        print('步骤 3/3: 复制配置文件...')
        exe_dir = dist_dir / 'OneKill'
        exe_dir.mkdir(exist_ok=True)
        
        # 移动exe文件
        exe_src = dist_dir / 'OneKill.exe'
        exe_dst = exe_dir / 'OneKill.exe'
        if exe_src.exists():
            shutil.move(str(exe_src), str(exe_dst))
            print('  ✓ 移动可执行文件')
        else:
            print('  ⚠ 未找到生成的 exe 文件')

        # 复制配置文件
        if config_yaml.exists():
            shutil.copy2(config_yaml, exe_dir / 'config.yaml')
            print('  ✓ 复制配置文件')
        else:
            print('  ⚠ 配置文件不存在')

        total = time.time() - start

        print('=' * 50)
        print('🎉 打包完成！')
        print('=' * 50)
        print(f'输出目录: {dist_dir}/OneKill/')
        print(f'可执行文件: {dist_dir}/OneKill/OneKill.exe')
        print(f'配置文件: {dist_dir}/OneKill/config.yaml')
        print(f'总耗时: {total:.1f} 秒')
        print('\n运行方式:')
        print(f'  cd {dist_dir}/OneKill')
        print('  OneKill.exe')
        print('=' * 50)

    except Exception as e:
        total = time.time() - start
        print(f'\n❌ 打包失败 (耗时: {total:.1f} 秒)')
        print(f'错误信息: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()