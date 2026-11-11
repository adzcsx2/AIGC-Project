"""Compatibility entry; implementation is centralized under tools."""
import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / 'tools/视频工具/补帧核心.py'
if __name__ == '__main__':
    runpy.run_path(str(SCRIPT), run_name='__main__')
else:
    globals().update(runpy.run_path(str(SCRIPT), run_name='interpolation_core'))
