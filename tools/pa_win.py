import os
import sys
import subprocess
import time
import argparse
from pathlib import Path


def run_cmd(cmd, check=True):
    """运行命令并实时显示输出"""
    print(f'执行: {" ".join(cmd)}')
    start_time = time.time()

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, bufsize=1, universal_newlines=True
    )

    for line in process.stdout:
        print(f'  {line.rstrip()}')

    process.wait()
    elapsed_time = time.time() - start_time
    print(f'  完成 (耗时: {elapsed_time:.1f}秒)')

    if process.returncode != 0 and check:
        raise subprocess.CalledProcessError(process.returncode, cmd)

    return process.returncode


def main():
    """主函数：打包为单个可执行exe文件"""
    parser = argparse.ArgumentParser(description='Python应用打包工具 (Windows版本)')
    parser.add_argument('--main', default='main.py', help='主程序文件路径')
    parser.add_argument('--output', default='dist', help='输出目录')
    parser.add_argument('--console', action='store_true', help='保留控制台窗口')
    args = parser.parse_args()

    # 获取项目根目录和Python解释器
    project_root = Path.cwd()
    python_exe = sys.executable
    main_file = project_root / args.main
    dist_dir = project_root / args.output

    # 检查主程序文件是否存在
    if not main_file.exists():
        print(f'错误: 主程序文件 {main_file} 不存在')
        return 1

    print(f'开始打包: {main_file} -> {dist_dir}')
    
    # 创建输出目录
    dist_dir.mkdir(exist_ok=True)

    # 构建Nuitka命令
    nuitka_cmd = [
        python_exe, '-m', 'nuitka',
        '--standalone',  # 创建独立可执行文件
        '--onefile',     # 打包为单个文件
        '--assume-yes-for-downloads',  # 自动下载依赖
        '--output-dir=' + str(dist_dir),  # 输出目录
        '--remove-output',  # 删除中间文件
        '--show-progress',  # 显示进度
    ]

    # 根据参数调整选项
    if not args.console:
        nuitka_cmd.append('--windows-disable-console')  # 禁用控制台窗口
    
    # 添加主程序文件
    nuitka_cmd.append(str(main_file))

    try:
        # 执行打包命令
        run_cmd(nuitka_cmd)
        print(f'\n打包完成! 可执行文件位于: {dist_dir}')
        return 0
    except subprocess.CalledProcessError as e:
        print(f'\n打包失败: {e}')
        return 1
    except Exception as e:
        print(f'\n发生错误: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())