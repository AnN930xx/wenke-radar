"""pytest 公共配置：把项目根目录加进导入路径"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
