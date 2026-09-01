"""财报下载器包。

提供三大市场财报 PDF 搜索与下载能力：
- CninfoDownloader — A股（巨潮资讯网）
- HkexnewsDownloader — 港股（披露易）
- SecDownloader — 美股（SEC EDGAR）
"""

from downloaders.cninfo import CninfoDownloader
from downloaders.hkexnews import HkexnewsDownloader
from downloaders.sec import SecDownloader

__all__ = [
    "CninfoDownloader",
    "HkexnewsDownloader",
    "SecDownloader",
]
