# widgets/__init__.py에 path 설정을 넣어서 widgets 패키지가 로드될 때 자동으로 프로젝트 루트가 path에 추가되도록 함
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.symbol_config import get_symbol_list