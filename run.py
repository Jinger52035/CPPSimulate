"""
run.py — 启动入口
运行方式：python run.py
"""
import sys
import traceback
import datetime
import os

def _crash_handler(exc_type, exc_value, exc_tb):
    """未捕获异常时写入日志文件并打印到控制台"""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(log_dir, "crash.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    text = f"\n{'='*60}\n[{timestamp}]\n{''.join(lines)}"
    # 写文件
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text)
    # 同时打印到控制台
    print(text, file=sys.stderr)

sys.excepthook = _crash_handler

from src.main_window import main

if __name__ == "__main__":
    main()
