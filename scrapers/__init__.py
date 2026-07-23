"""scrapers 包"""
from .jd import JdScraper
from .kuaishou import KuaishouScraper
from .xiaohongshu import XiaohongshuScraper, XiaohongshuSocialScraper
from .pdd import PddScraper
from .taotian import TaotianScraper
from .offerstar import OfferstarScraper
from .generic import GenericScraper
from .tencent import TencentScraper, TencentSocialScraper
from .bytedance import (BytedanceScraper, XiaomiScraper,
                        GenkiForestScraper, BytedanceSocialScraper,
                        XiaomiSocialScraper)
from .alibaba import AlibabaScraper
from .baidu import BaiduScraper
from .netease import NeteaseScraper
from .bilibili import BilibiliScraper, BilibiliSocialScraper
from .mihoyo import MihoyoScraper
from .meituan import MeituanScraper, MeituanSocialScraper
from .beisen import (PopmartScraper, MinisoScraper,
                     PopmartSocialScraper, MinisoSocialScraper,
                     MengniuScraper, MengniuSocialScraper)
from .yili import YiliScraper, YiliSocialScraper
from .ucca import UccaScraper
from .nowcoder import NowcoderScraper
from .baiku import LorealScraper
from .moka import NongfuScraper, DidiScraper
from .didi_social import DidiSocialScraper
from .jd_social import JdSocialScraper
from .liepin import KuanChuangScraper, ArcadisScraper

# 内置抓取器（每个公司一个专用类）
SCRAPERS = {
    "京东": JdScraper,
    "快手": KuaishouScraper,
    "小红书": XiaohongshuScraper,
    "拼多多": PddScraper,
    "淘宝": TaotianScraper,
    "offerstar": OfferstarScraper,
    "腾讯": TencentScraper,
    "字节跳动": BytedanceScraper,
    "阿里巴巴": AlibabaScraper,
    "百度": BaiduScraper,
    "小米": XiaomiScraper,
    "网易": NeteaseScraper,
    "B站": BilibiliScraper,
    "米哈游": MihoyoScraper,
    "美团": MeituanScraper,
    "泡泡玛特": PopmartScraper,
    "欧莱雅": LorealScraper,
    "农夫山泉": NongfuScraper,
    "滴滴": DidiScraper,
    "名创优品": MinisoScraper,
    "蒙牛": MengniuScraper,
    "伊利": YiliScraper,
    "元气森林": GenkiForestScraper,
    "UCCA": UccaScraper,
    "牛客日程": NowcoderScraper,
    # --- 社招源（豁免届别/实习过滤，只按方向+城市筛）---
    "美团(社招)": MeituanSocialScraper,
    "泡泡玛特(社招)": PopmartSocialScraper,
    "名创优品(社招)": MinisoSocialScraper,
    "蒙牛(社招)": MengniuSocialScraper,
    "字节跳动(社招)": BytedanceSocialScraper,
    "腾讯(社招)": TencentSocialScraper,
    "滴滴(社招)": DidiSocialScraper,
    "伊利(社招)": YiliSocialScraper,
    "小红书(社招)": XiaohongshuSocialScraper,
    "小米(社招)": XiaomiSocialScraper,
    "B站(社招)": BilibiliSocialScraper,
    "京东(社招)": JdSocialScraper,
    # 猎聘公司页示例源（策展/文化遗产方向，按需替换）
    "宽创国际": KuanChuangScraper,
    "凯谛思": ArcadisScraper,
}
