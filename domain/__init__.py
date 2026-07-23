"""领域层：与"数据从哪来"无关的核心模型与分类逻辑。

models.py    JobItem —— 全系统的数据契约（通用货币）
classify.py  标题→职位类别 的兜底推断

本层只依赖 config，不依赖抓取/存储/渲染任何一层；
所有层（scrapers/filters/store/report）都可以依赖本层。
"""
