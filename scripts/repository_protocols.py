"""财报仓储窄协议定义（从 Dayu storage/repository_protocols.py 提取）。

按真实职责簇拆分仓储，6 个窄协议替代单体 God Repository：

- **BatchingRepositoryProtocol** — 批处理事务
- **CompanyMetaRepositoryProtocol** — 公司级元数据
- **SourceDocumentRepositoryProtocol** — 源文档 CRUD
- **ProcessedDocumentRepositoryProtocol** — 解析产物
- **DocumentBlobRepositoryProtocol** — 文件对象读写
- **FilingMaintenanceRepositoryProtocol** — 维护治理

设计原则：
- 使用 ``typing.Protocol``（结构化鸭子类型），非 ABC 抽象类。
- Consumer 只 import 自己需要的协议，不依赖实现。
- 文件系统实现用 Mixin 组合对应各协议。
- 作为 `stock_analysis.db` 重构的设计模板 —— 当前所有 SQL 散落在各脚本中。

Turtle 应用：当前 ``stock_analysis.db`` 是 7GB 单体 SQLite，
可通过窄仓储协议分层重构为::

    class CompanyRepository(CompanyMetaRepositoryProtocol):
        def get_company(self, ticker) -> CompanyMeta: ...

    class FinancialRepository(SourceDocumentRepositoryProtocol):
        def get_income_statement(self, ticker, year) -> IncomeStatement: ...

    class ReportRepository(DocumentBlobRepositoryProtocol):
        def store_pdf(self, ticker, path) -> FileMeta: ...

Usage (设计参考，不强制实现)::

    from scripts.repository_protocols import (
        CompanyMetaRepositoryProtocol,
        SourceDocumentRepositoryProtocol,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import BinaryIO, Protocol


# ---------------------------------------------------------------------------
# 共享领域模型（简化版，替代 Dayu 的 domain models）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompanyMeta:
    """公司级元数据。

    Args:
        ticker: 规范化股票代码。
        company_name: 公司全称。
        market: 市场（US/CN/HK）。
        exchange: 交易所（可选）。
        aliases: 别名列表（如跨市场代码）。
    """

    ticker: str = ""
    company_name: str = ""
    market: str = ""
    exchange: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanyMetaInventoryEntry:
    """公司元数据盘点条目。

    Args:
        ticker: 股票代码。
        has_meta: 是否存在 meta.json。
        company_name: 公司名称（从 meta 读取）。
    """

    ticker: str = ""
    has_meta: bool = False
    company_name: str = ""


@dataclass(frozen=True)
class DocumentMeta:
    """文档元数据。

    Args:
        document_id: 唯一文档标识。
        form_type: 表单类型（10-K/年报等）。
        fiscal_year: 财年。
        fiscal_period: 财期（FY/Q1等）。
        filing_date: 申报日期。
        primary_document: 主文档文件名。
        file_entries: 关联文件列表。
    """

    document_id: str = ""
    form_type: str = ""
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    filing_date: str = ""
    primary_document: str = ""
    file_entries: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentSummary:
    """文档摘要（列表查询返回）。"""

    document_id: str = ""
    form_type: str = ""
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    filing_date: str = ""


@dataclass(frozen=True)
class DocumentHandle:
    """文档操作句柄。"""

    ticker: str = ""
    document_id: str = ""
    directory: str = ""


@dataclass(frozen=True)
class FileObjectMeta:
    """文件对象元数据。"""

    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    sha256: str = ""


@dataclass(frozen=True)
class BatchToken:
    """批处理事务令牌。"""

    ticker: str = ""
    token_id: str = ""


# ---------------------------------------------------------------------------
# 6 个窄仓储协议
# ---------------------------------------------------------------------------


class BatchingRepositoryProtocol(Protocol):
    """批处理事务仓储协议。

    用于需要原子性的多步写操作（如下载 filing → 写 meta → 写 blob）。
    """

    def begin_batch(self, ticker: str) -> BatchToken:
        """开启批处理事务。

        Args:
            ticker: 股票代码。

        Returns:
            批处理令牌。
        """
        ...

    def commit_batch(self, token: BatchToken) -> None:
        """提交批处理事务。

        Args:
            token: ``begin_batch`` 返回的令牌。
        """
        ...

    def rollback_batch(self, token: BatchToken) -> None:
        """回滚批处理事务。

        Args:
            token: ``begin_batch`` 返回的令牌。
        """
        ...

    def recover_orphan_batches(self, *, dry_run: bool = False) -> tuple[str, ...]:
        """恢复异常退出后遗留的孤儿 batch。

        Args:
            dry_run: True 时仅扫描不恢复。

        Returns:
            已恢复的 ticker 列表。
        """
        ...


class CompanyMetaRepositoryProtocol(Protocol):
    """公司级元数据仓储协议。

    负责公司信息的增删改查，是 ticker 解析的权威来源。
    """

    def scan_company_meta_inventory(self) -> list[CompanyMetaInventoryEntry]:
        """扫描所有公司目录的元数据状态。

        Returns:
            盘点条目列表。
        """
        ...

    def get_company_meta(self, ticker: str) -> CompanyMeta:
        """读取公司级元数据。

        Args:
            ticker: 股票代码。

        Returns:
            公司元数据对象。

        Raises:
            FileNotFoundError: 元数据不存在时抛出。
            ValueError: 元数据格式非法时抛出。
        """
        ...

    def upsert_company_meta(self, meta: CompanyMeta) -> None:
        """写入或更新公司级元数据。

        Args:
            meta: 公司元数据对象。
        """
        ...

    def resolve_existing_ticker(
        self, ticker_candidates: list[str]
    ) -> str | None:
        """在候选 ticker 中解析已存在的规范 ticker。

        Args:
            ticker_candidates: 候选代码列表（跨市场变体）。

        Returns:
            第一个匹配的已有 ticker，无匹配则返回 None。
        """
        ...


class SourceDocumentRepositoryProtocol(Protocol):
    """源文档仓储协议。

    管理从外部下载的原始财报文档（PDF/HTML/XBRL）的完整生命周期。
    """

    def has_source(self, ticker: str, document_id: str) -> bool:
        """判断源文档是否存在。

        Args:
            ticker: 股票代码。
            document_id: 文档 ID。

        Returns:
            存在返回 True。
        """
        ...

    def create_source_document(
        self, ticker: str, meta: DocumentMeta
    ) -> DocumentHandle:
        """创建源文档记录。

        Args:
            ticker: 股票代码。
            meta: 文档元数据。

        Returns:
            新创建的文档句柄。
        """
        ...

    def update_source_document(
        self, ticker: str, meta: DocumentMeta
    ) -> DocumentHandle:
        """更新源文档记录。

        Args:
            ticker: 股票代码。
            meta: 文档元数据。

        Returns:
            更新后的文档句柄。
        """
        ...

    def delete_source_document(
        self, ticker: str, document_id: str
    ) -> None:
        """逻辑删除源文档。

        Args:
            ticker: 股票代码。
            document_id: 文档 ID。
        """
        ...

    def get_source_meta(
        self, ticker: str, document_id: str
    ) -> DocumentMeta:
        """读取源文档元数据。

        Args:
            ticker: 股票代码。
            document_id: 文档 ID。

        Returns:
            文档元数据。
        """
        ...

    def list_source_documents(
        self, ticker: str,
    ) -> list[DocumentSummary]:
        """列出某 ticker 的全部源文档摘要。

        Args:
            ticker: 股票代码。

        Returns:
            文档摘要列表。
        """
        ...

    def get_primary_file(
        self, ticker: str, document_id: str,
    ) -> FileObjectMeta:
        """获取源文档主文件元数据。

        Args:
            ticker: 股票代码。
            document_id: 文档 ID。

        Returns:
            主文件对象元数据。
        """
        ...


class ProcessedDocumentRepositoryProtocol(Protocol):
    """解析产物仓储协议。

    管理经过 Processor 处理后的结构化数据（sections/tables/snapshots）。
    """

    def create_processed(
        self, ticker: str, document_id: str, meta: DocumentMeta,
    ) -> DocumentHandle:
        """创建解析产物记录。

        Args:
            ticker: 股票代码。
            document_id: 关联的源文档 ID。
            meta: 产物元数据。

        Returns:
            产物句柄。
        """
        ...

    def update_processed(
        self, ticker: str, document_id: str, meta: DocumentMeta,
    ) -> DocumentHandle:
        """更新解析产物记录。"""
        ...

    def delete_processed(
        self, ticker: str, document_id: str,
    ) -> None:
        """删除解析产物。

        Args:
            ticker: 股票代码。
            document_id: 文档 ID。
        """
        ...

    def get_processed_meta(
        self, ticker: str, document_id: str,
    ) -> DocumentMeta:
        """读取解析产物元数据。"""
        ...

    def list_processed_documents(
        self, ticker: str,
    ) -> list[DocumentSummary]:
        """列出某 ticker 的全部解析产物摘要。"""
        ...

    def clear_processed_documents(self, ticker: str) -> None:
        """清空某 ticker 的全部解析产物。

        Args:
            ticker: 股票代码。
        """
        ...


class DocumentBlobRepositoryProtocol(Protocol):
    """文档文件对象仓储协议。

    负责底层文件（PDF/HTML/JSON/txt）的读写，不关心业务语义。
    """

    def read_file_bytes(
        self, handle: DocumentHandle, filename: str,
    ) -> bytes:
        """读取文件字节内容。

        Args:
            handle: 文档句柄。
            filename: 文件名。

        Returns:
            文件字节内容。
        """
        ...

    def store_file(
        self,
        handle: DocumentHandle,
        filename: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> FileObjectMeta:
        """写入文件对象。

        Args:
            handle: 文档句柄。
            filename: 目标文件名。
            data: 可读二进制流。
            content_type: 可选 MIME 类型。

        Returns:
            写入后的文件对象元数据。
        """
        ...

    def delete_file(
        self, handle: DocumentHandle, filename: str,
    ) -> None:
        """删除文件。

        Args:
            handle: 文档句柄。
            filename: 文件名。
        """
        ...

    def list_files(
        self, handle: DocumentHandle,
    ) -> list[FileObjectMeta]:
        """列出文档目录下所有文件。

        Args:
            handle: 文档句柄。

        Returns:
            文件对象元数据列表。
        """
        ...


class FilingMaintenanceRepositoryProtocol(Protocol):
    """Filing 维护治理仓储协议。

    负责 filing 清理、拒绝注册表和过期文档管理。
    """

    def clear_filing_documents(self, ticker: str) -> None:
        """清空某 ticker 下的全部 filing 文档。

        Args:
            ticker: 股票代码。
        """
        ...

    def load_rejection_registry(
        self, ticker: str,
    ) -> dict[str, dict[str, str]]:
        """读取下载拒绝注册表。

        Args:
            ticker: 股票代码。

        Returns:
            ``{document_id: {reason, timestamp, ...}}``。
        """
        ...

    def save_rejection_registry(
        self,
        ticker: str,
        registry: dict[str, dict[str, str]],
    ) -> None:
        """保存下载拒绝注册表。

        Args:
            ticker: 股票代码。
            registry: 注册表字典。
        """
        ...

    def cleanup_stale_documents(
        self,
        ticker: str,
        *,
        valid_document_ids: set[str],
    ) -> int:
        """清理不在有效集合中的过期文档。

        Args:
            ticker: 股票代码。
            valid_document_ids: 当前有效的文档 ID 集合。

        Returns:
            清理的文档数量。
        """
        ...


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

__all__ = [
    # 数据模型
    "BatchToken",
    "CompanyMeta",
    "CompanyMetaInventoryEntry",
    "DocumentHandle",
    "DocumentMeta",
    "DocumentSummary",
    "FileObjectMeta",
    # 仓储协议
    "BatchingRepositoryProtocol",
    "CompanyMetaRepositoryProtocol",
    "SourceDocumentRepositoryProtocol",
    "ProcessedDocumentRepositoryProtocol",
    "DocumentBlobRepositoryProtocol",
    "FilingMaintenanceRepositoryProtocol",
]
