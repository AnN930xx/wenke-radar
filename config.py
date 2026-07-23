"""
Campus Radar 配置文件
修改这里的配置来定制你的秋招监控。
"""

# ==================== 监控公司开关 ====================
# 把不想监控的公司设为 False 即可
ENABLED_COMPANIES = {
    # --- 电商大厂（原有） ---
    "京东": True,
    "快手": True,
    "小红书": True,
    "拼多多": True,
    "淘宝": True,
    "offerstar": True,   # 聚合平台，补充行业动态
    # --- IP/内容/综合大厂（新增） ---
    "腾讯": True,
    "字节跳动": True,
    "阿里巴巴": True,    # 集团主站（淘天已单列在"淘宝"）；遍历应届/实习/研究型等批次
    "百度": True,
    "小米": True,        # 飞书 ATS，与字节同一套引擎
    "网易": True,        # 自动发现互联网/互娱等在招校招项目
    "B站": True,
    "米哈游": True,
    "美团": True,        # 全量翻页较慢（约130页），介意可关闭
    "泡泡玛特": True,    # 校招未开时为 0 岗位，开启后自动出现
    "欧莱雅": True,      # 百库平台；2027秋招官网未开时为 0，开启后自动抓取
    "农夫山泉": True,    # 养生堂·农夫山泉，Moka平台（快消行销/生产管培大户）
    "滴滴": True,        # Moka平台（响应加密已破解）
    "名创优品": True,    # 北森平台（快消/潮流零售）
    # --- 快消（新增第二批）---
    "蒙牛": True,        # 北森平台；两季之间校招暂关(0岗)，官网重开自动出现
    "伊利": True,        # 百库旧版(/wt/)接口，动态令牌；管培/销售/职能大户
    "元气森林": True,    # 飞书ATS多租户(jobs.feishu.cn/352020)
    # --- 文化艺术机构（新增） ---
    "UCCA": True,        # UCCA当代艺术中心（含策展/展览类岗位与实习）
    # --- 聚合平台（新增） ---
    "牛客日程": True,    # 牛客网校招日程，覆盖2万+公司的校招项目（公司级信息）
    # --- 社招源（已毕业求职者社招机会更多；豁免届别/实习过滤）---
    "美团(社招)": True,       # 美团社招 jobType=3
    "泡泡玛特(社招)": True,   # 消费品牌社招
    "名创优品(社招)": True,   # 消费品牌社招
    "蒙牛(社招)": True,       # 快消社招（北森 category=1）
    "字节跳动(社招)": True,   # 大体量源，daily_only 只报每日新增
    "腾讯(社招)": True,       # 大体量源，daily_only 只报每日新增
    "滴滴(社招)": True,       # talent.didiglobal.com 自研接口（明文JSON）
    "伊利(社招)": True,       # 百库旧版 recruitType=2（快消社招大户，91页）
    "小红书(社招)": True,     # recruitType=social（互联网大厂社招，889岗）
    "小米(社招)": True,       # 飞书ATS portal_type=2（同字节社招套路）
    "B站(社招)": True,        # X-Channel=society（互联网大厂社招）
    "京东(社招)": True,       # zhaopin.jd.com 老JSP站，form编码接口
    # 示例：无官方API、只在猎聘招人的公司（按需替换或停用）
    "宽创国际": True,         # 博物馆展陈/文物IP/策展（策展方向靶心）
    "凯谛思": True,           # Arcadis，文化遗产/考古外企
}

# ==================== 岗位关键词 ====================
# 简报会优先按"职位类别"过滤，再用关键词对岗位标题做兜底匹配。
# 默认覆盖非技术/泛商业岗全谱系（面向文科/商科/艺术背景求职者）——
# 组名就是日报里显示的方向名。方向太多嫌吵？删掉不要的组即可，一处配置全局生效。
KEYWORDS = {
    "电商": [
        "采销", "采销管培", "商家运营", "行业运营", "品类运营",
        "电商运营", "商品运营", "店铺运营", "平台运营", "招商",
        "供应链", "采购", "贸易", "跨境", "电商", "商家拓展",
        "行业BD", "商业化", "渠道运营", "分销",
    ],
    "产品": [
        "产品经理", "产品策划", "产品助理", "产品实习生",
        "数据产品", "商业化产品", "策略产品", "产品运营",
        "用户产品", "平台产品", "B端产品", "C端产品",
    ],
    "运营": [
        "用户运营", "内容运营", "活动运营", "社群运营",
        "新媒体运营", "社区运营", "增长运营",
        "海外运营", "国际化运营", "直播运营",
        "APP运营", "游戏运营", "IP运营", "社媒",
    ],
    "策展": [
        "策展", "展览", "展陈", "布展", "会展",
        "文创", "艺术", "美术馆", "博物馆", "画廊",
        "IP授权", "IP合作", "衍生品", "内容策划", "活动策划",
        "空间设计", "陈列", "公共教育", "公共实践",
        "编辑", "出版",
    ],
    "增长营销": [
        "SEO", "GEO", "增长", "营销", "市场营销", "品牌",
        "投放", "广告优化", "用户增长", "流量", "获客",
        "AIGC", "内容营销", "社媒营销", "数字营销",
        "行销", "市场", "商务拓展", "BD", "管培生", "管理培训生",
    ],
    "市场公关": [
        "公关", "品牌公关", "传播", "媒介", "政府事务", "公共事务",
        "市场策划", "广告策划", "活动执行", "会务",
    ],
    "媒体内容": [
        "编辑", "记者", "文案", "撰稿", "采编", "编导",
        "内容审核", "翻译", "本地化",
    ],
    "商业分析": [
        "商业分析", "经营分析", "数据分析", "战略", "咨询",
        "行业研究", "市场研究", "用户研究", "投资分析",
    ],
    "人力行政": [
        "人力资源", "HRBP", "招聘", "培训", "组织发展", "薪酬",
        "雇主品牌", "校园招聘", "行政", "文秘", "总助",
    ],
    "项目客户": [
        "项目管理", "项目经理", "项目专员", "PMO",
        "客户成功", "客户经理", "客户运营", "大客户", "商务合作",
    ],
}

# 命中关键词的类别名（各公司 API 返回的类别字段里，含这些字就算命中）
CATEGORY_KEYWORDS = ["产品", "运营", "电商", "采销", "商家", "行业", "策展", "展览", "文创",
                     "营销", "增长", "市场", "公关", "人力", "行政", "分析", "战略",
                     "项目", "客户", "编辑", "内容", "品牌"]


# ==================== 用户自定义方向（隔离区，改这里不碰引擎）====================
# 想加自己的求职方向？别动上面的 KEYWORDS——去编辑同目录的 user_profile.py。
# 隔离保证：
#   ① 改错不影响抓取——引擎每天抓的是"全量岗位"，方向只决定"从里面挑哪些给你看"；
#   ② 写错语法也不会让每日任务崩——引擎忽略你的自定义、回退内置方向，并在日志里提示。
def _load_user_directions() -> dict:
    """读取 user_profile.MY_DIRECTIONS；文件不存在=未定制（静默），出错=提示并回退。"""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_profile.py")
    if not os.path.exists(path):
        return {}
    try:
        import user_profile
        extra = getattr(user_profile, "MY_DIRECTIONS", {})
        return extra if isinstance(extra, dict) else {}
    except Exception as e:
        print(f"⚠️ user_profile.py 有误，已忽略你的自定义方向（引擎照常运行）：{e}")
        return {}


def apply_user_directions(extra: dict = None) -> list:
    """把用户方向合并进 KEYWORDS / CATEGORY_KEYWORDS，返回成功加载的方向名列表。
    对任何非法输入（非dict/值非list/空名/非字符串关键词）都安全跳过、绝不抛异常，
    这是"坏配置不影响引擎"的保证。同名方向合并关键词、不覆盖内置。幂等可重复调用。"""
    if extra is None:
        extra = _load_user_directions()
    added = []
    if not isinstance(extra, dict):
        return added
    for name, kws in extra.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(kws, (list, tuple)):
            continue
        clean = [k.strip() for k in kws if isinstance(k, str) and k.strip()]
        if not clean:
            continue
        KEYWORDS[name] = list(dict.fromkeys(KEYWORDS.get(name, []) + clean))
        if name not in CATEGORY_KEYWORDS:
            CATEGORY_KEYWORDS.append(name)
        added.append(name)
    return added


apply_user_directions()

# ==================== 来源分级（二轮外部审查采纳）====================
# 每个源标注可信等级：官方源（公司官网/公开 ATS）可为"岗位关闭/更新时间/真实性"背书；
# 聚合发现源（猎聘/offerstar/牛客）只作线索发现，不 authoritative。
# 用途：完整性告警分级（聚合源不完整不误报警）、未来跨源去重与"岗位关闭"判定。
_ATS_SOURCES = {
    "字节跳动", "小米", "元气森林", "字节跳动(社招)", "小米(社招)",              # 飞书 ATS
    "泡泡玛特", "名创优品", "蒙牛", "泡泡玛特(社招)", "名创优品(社招)", "蒙牛(社招)",  # 北森
    "欧莱雅", "伊利", "伊利(社招)",                                          # 百库
    "农夫山泉", "滴滴",                                                     # Moka
}
_AGGREGATOR_SOURCES = {"牛客日程", "宽创国际", "凯谛思"}   # 猎聘/牛客系；offerstar 走前缀匹配


def source_kind(source_id: str) -> str:
    """源的可信等级：OFFICIAL_ATS / OFFICIAL_CAREERS / AGGREGATOR_DISCOVERY"""
    name = source_id or ""
    if name.startswith("offerstar") or name in _AGGREGATOR_SOURCES:
        return "AGGREGATOR_DISCOVERY"
    if name in _ATS_SOURCES:
        return "OFFICIAL_ATS"
    return "OFFICIAL_CAREERS"


def is_authoritative(source_id: str) -> bool:
    """官方源可为岗位关闭/时效背书；聚合发现源不可。"""
    return source_kind(source_id) != "AGGREGATOR_DISCOVERY"

# ==================== 排除关键词 ====================
# 岗位标题含以下词的直接排除（技术/研发类岗位常带"电商/运营/产品"字样造成误报）
EXCLUDE_TITLE_KEYWORDS = [
    "工程师", "算法", "开发", "研发", "测试", "运维", "架构",
    "大模型", "前端", "后端", "客户端", "嵌入式", "芯片", "SRE",
]

# ==================== 届别过滤（画像驱动，任意年份随便改）====================
# 只影响校招（社招天然不分届别、不受此过滤）。想看哪几届就填哪几届——
# [2024]、[2027, 2028]、任何 2000~2099 的组合都行，"2026届/26届/26秋"等匹配 token
# 与排除窗口（目标届别前后各约6年的其他年份）全部由 filters 层按当前配置自动推导。
# 规则：命中目标届别 → 保留；命中排除届别 → 排除；没提年份=滚动招聘 → 保留。
ONLY_TARGET_YEAR = True
TARGET_GRAD_YEARS = [2025, 2026, 2027]      # 可投届别窗口（改这里，全局生效）
CAMPUS_FOCUS_YEARS = None                   # 日报分块顺序（第一个=🎯重点届）；None=每个目标届别一块
TARGET_YEAR_LABEL = "/".join(str(y) for y in TARGET_GRAD_YEARS) + " 届"

# ==================== 排除实习岗 ====================
# 目标用户为已毕业/应届求职者，只要能直接入职的正式岗（校招应届正式 / 社招），实习岗全部筛掉。
# 命中以下任一词（不区分大小写）的岗位直接排除。
# 注意："管培生/管理培训生/校招生/应届"不含"实习"，会保留。
EXCLUDE_INTERN = True
INTERN_KEYWORDS = [
    "实习", "见习", "intern", "internship", "实习生", "日常实习",
    "暑期实习", "转正实习", "研究型实习",
]

# ==================== 社招经验年限阈值 ====================
# 大厂社招标题不写"资深/高级"，经验要求在 JD 正文（字节）或结构化字段（腾讯）里。
# JD 要求超过这个年数经验的社招岗直接丢弃（区间取下限："1-3年"=1 保留，"3-5年"=3 丢弃）。
SOCIAL_MAX_EXPERIENCE_YEARS = 2

# ==================== 社招资深岗排除 ====================
# 目标用户刚毕业，社招只投入门级。标题含以下"资深标识"的社招岗排除
# （只作用于社招；校招岗不受影响）。保留 专员/助理/经理/主管/运营/产品 等。
SOCIAL_EXCLUDE_SENIORITY = [
    "资深", "高级", "专家", "负责人", "总监", "总经理", "副总", "总裁",
    "首席", "主任", "senior", "sr.", "expert", "director", "principal",
    "staff", "head of", "chief", "lead ", "8年", "10年", "5年以上", "多年经验",
]

# ==================== 目标城市 ====================
# 留空 [] 表示全国都看；填了就只看这些城市
# 注意：部分公司（如小红书）按城市过滤，填这里会精确过滤
TARGET_CITIES = ["上海", "北京", "杭州", "深圳", "广州"]

# ==================== 各公司专属参数 ====================
COMPANY_CONFIG = {
    "京东": {
        # 应届生招聘类型，type=present 表示应届生
        "type": "present",
    },
    "快手": {
        # 27届校招项目代码（从官网 URL 里提取）
        "recruit_sub_project_codes": ["20271779425607"],
    },
    "小红书": {
        # term_regular = 应届生校招
        "campus_recruit_types": ["term_regular"],
        # workplace 城市编码（4401=上海）。留空则不限城市
        "workplaces": [],  # [] = 全国
    },
    "拼多多": {
        # t=null 表示全部类别，也可填具体类别 job code
        "t": None,
    },
    "淘宝": {
        # batchId 会自动获取，这里留默认即可
        "batch_channel": "campus_group_official_site",
    },
    "offerstar": {
        # 聚合平台查询参数
        "title": "2027",
        "positions": "运营",   # 聚合平台按"运营"方向筛
        "channel": "校招",
    },
    "腾讯": {
        # 1=校招（应届），职位详情统一跳转岗位列表页搜索
        "recruit_type": 1,
    },
    "字节跳动": {
        # portal_type=3 为校园招聘入口
        "portal_type": 3,
    },
    "网易": {
        # 从导航接口自动发现在招校招项目；这里可以排除不关注的项目关键词
        "exclude_projects": [],   # 例如 ["雷火"] 表示跳过含"雷火"的项目
    },
    "B站": {
        # recruitType=1 校招；workTypeList 留空=应届+实习都抓
        "recruit_type": 1,
    },
    "米哈游": {
        # channelDetailIds=[1] 校招渠道
        "channel_detail_ids": [1],
    },
    "美团": {
        # 官网接口无法按校招过滤，全量翻页后本地筛 jobType=2（校招）
        # 最多翻这么多页（每页20条），防止意外死循环
        "max_pages": 200,
    },
    "泡泡玛特": {
        # 北森(zhiye.com)平台，category=2 校招
        "host": "https://popmart.zhiye.com",
        "category": 2,
    },
    "欧莱雅": {
        # 百库(hotjob.cn)平台。SU 是欧莱雅校招站点ID；recruit_type=1 校招
        # 注：2027秋招官网未开时该站点返回"已关闭"，抓取器会优雅返回空
        "host": "https://bkhr.hotjob.cn",
        "su": "SU64ecb74d1c240e725e589d9a",
        "recruit_type": 1,
    },
    "农夫山泉": {
        # Moka平台。org_id/site_id 来自 window.TurboApply.data.org.{id,siteId}
        "host": "https://app.mokahr.com",
        "org_id": "yst",
        "site_id": 68367,
    },
    "滴滴": {
        # Moka平台（自有域名）
        "host": "https://campus.didiglobal.com",
        "org_id": "didiglobal",
        "site_id": 96064,
    },
    "名创优品": {
        # 北森(zhiye.com)平台，category=2 校招
        # 该租户 pageSize 越大返回越少(接口bug)，用 page_size=3 才能正常翻页
        "host": "https://miniso.zhiye.com",
        "category": 2,
        "page_size": 3,
        # 北森总数虚高（Count 含未上架岗），实抓稳定在报告数的 ~80%，校准对账阈值
        "complete_ratio": 0.75,
    },
    "蒙牛": {
        # 北森(zhiye.com)平台，category=2 校招
        # 两季之间校招官网暂关(返回0岗)，重开后自动出现
        "host": "https://mengniu.zhiye.com",
        "category": 2,
    },
    "伊利": {
        # 百库(hotjob.cn)旧版接口(/wt/路径)，动态 operational 令牌
        # brandCode=1 伊利集团；recruitType=1 校招
        "host": "https://yili.hotjob.cn",
        "brand_code": 1,
        "recruit_type": 1,
    },
    "元气森林": {
        # 飞书ATS多租户站(jobs.feishu.cn)，站点路径352020（详见 GenkiForestScraper）
        # portal_type=3 校招（含实习岗，靠全局实习过滤剔除）
        "portal_type": 3,
    },
    "UCCA": {
        # 抓取招聘+实习两个板块的所有表格
        "url": "https://ucca.org.cn/careers/",
    },
    "牛客日程": {
        # tab=2/3 为近期更新与即将截止的活跃子集（全量档案tab=1有2万+条，不抓）
        "tabs": [2, 3],
    },
    # ---------- 社招源 ----------
    "美团(社招)": {
        "job_type_filter": "3",   # 3=社招
        "job_nature": "社招",
        "max_pages": 200,
    },
    "泡泡玛特(社招)": {
        "host": "https://popmart.zhiye.com",
        "category": 1,            # 1=社招
        "job_nature": "社招",
    },
    "名创优品(社招)": {
        "host": "https://miniso.zhiye.com",
        "category": 1,            # 1=社招
        "page_size": 3,
        "job_nature": "社招",
        "complete_ratio": 0.75,   # 北森总数虚高，同校招
    },
    "蒙牛(社招)": {
        "host": "https://mengniu.zhiye.com",
        "category": 1,            # 1=社招
        "job_nature": "社招",
        "complete_ratio": 0.75,   # 北森总数虚高（实抓 ~90% 且稳定）
    },
    "字节跳动(社招)": {
        # portal_type=2 社招；按职类过滤（否则全量1万+抓不动）
        # 类目ID来自 /api/v1/config/job/filters/2：产品/运营/市场
        "portal_type": 2,
        "job_category_ids": [
            "6704215864629004552",   # 产品
            "6704215882479962371",   # 运营
            "6704215901438216462",   # 市场
        ],
        "job_nature": "社招",
        "daily_only": True,          # 大体量源：日报只列每日新增，不全量展示
    },
    "腾讯(社招)": {
        # careers.tencent.com 公开API，父类目过滤：40003产品/40004营销与公关/40006内容
        "parent_category_ids": [40003, 40004, 40006],
        "job_nature": "社招",
        "daily_only": True,          # 大体量源：日报只列每日新增，不全量展示
    },
    "滴滴(社招)": {
        # talent.didiglobal.com 自研接口，明文JSON；pageSize服务端硬限16
        "job_nature": "社招",
    },
    "伊利(社招)": {
        # 百库旧版(/wt/)接口，recruitType=2 社招
        "host": "https://yili.hotjob.cn",
        "brand_code": 1,
        "recruit_type": 2,
        "job_nature": "社招",
    },
    "小米(社招)": {
        # 飞书ATS portal_type=2（同字节社招）；job_nature 触发经验/资深过滤
        "portal_type": 2,
        "job_nature": "社招",
    },
    # 小红书(社招)/B站(社招) 无需专属参数（job_nature 在各自抓取器类里设）
    "宽创国际": {
        # 猎聘手机版公司页；反爬不稳定→no_archive 防抖动
        "company_id": "9584536",
        "no_archive": True,
    },
    "凯谛思": {
        "company_id": "10054189",
        "no_archive": True,
    },
}

# ==================== 通用抓取源（零代码添加新公司）====================
# 后续添加新公司，只需在这里加一段配置即可，无需写代码！
# 配置格式见 scrapers/generic.py 文件顶部说明。
#
# 示例（取消注释并修改即可启用）：
#
# GENERIC_SOURCES = [
#     {
#         "name": "某公司",
#         "type": "api",                          # api 或 html
#         "url": "https://example.com/api/jobs",
#         "method": "POST",
#         "headers": {"Content-Type": "application/json"},
#         "body_template": {"page": "{page}", "size": 100},
#         "pagination": {"page_start": 1, "page_key": "page", "stop_when": "less_than_size"},
#         "response": {"list_path": "data.list", "total_path": "data.total"},
#         "fields": {
#             "job_id": "id", "title": "positionName", "category": "jobType",
#             "location": "workCity", "publish_time": "createTime",
#         },
#         "detail_url_template": "https://example.com/jobs/{job_id}",
#         "timestamp_field": "createTime",
#     },
# ]
GENERIC_SOURCES = []

# ==================== 数据可信度守卫 ====================
# 来源级 bootstrap：库里（含归档）从未见过的公司 = 新接入的源。其首抓岗位数 >= 此值时
# 静默入库、不计"今日新增"，防止接新源当天日报被几百条存量刷屏。
# 聚合源里的新公司（如 offerstar·某司）通常只有 1-2 条公告、属真实新增，不受此豁免。
BOOTSTRAP_MIN_JOBS = 5
# 归档骤降守卫：某公司本次"要归档的岗位数"占其原库存比例超过 RATIO（且原库存 >= MIN_EXISTING）
# 时，视为疑似"部分抓取成功"（分页失效/接口改版只抓到一部分），本次跳过归档并告警。
# 防住"昨天100岗今天只抓到20 → 80个被误判下线"这条路径；真实的大幅缩招会在告警里人工确认。
ARCHIVE_GUARD_MIN_EXISTING = 10
ARCHIVE_GUARD_RATIO = 0.5
# 抓取完整性对账：分页拿到的原始条数 >= 服务端报告总数 × 此比例，视为"抓全"。
# 低于此比例 → FetchResult.complete=False → 该源本次跳过归档 + 日报告警。
# 留 10% 余量吸收翻页过程中岗位实时上下线造成的正常抖动。
FETCH_COMPLETE_RATIO = 0.9

# ==================== 运行参数 ====================
# 请求超时（秒）
REQUEST_TIMEOUT = 20
# 失败重试次数
MAX_RETRIES = 2
# 每页抓取条数（尽量大，减少翻页）
PAGE_SIZE = 100
# User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
