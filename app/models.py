from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    __table_args__ = (
        UniqueConstraint(
            "os_family",
            "os_version",
            "repository_name",
            "original_filename",
            name="uq_catalog_source_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    os_family: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    os_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repository_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    saved_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    packages: Mapped[list["CatalogPackage"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class CatalogPackage(Base):
    __tablename__ = "catalog_packages"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "package_name",
            "version_original",
            "architecture",
            "filename",
            name="uq_catalog_package_per_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("catalog_sources.id"), nullable=False, index=True)

    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    package_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    version_original: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    architecture: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    section: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    filename: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    source_package: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    depends: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    source: Mapped[CatalogSource] = relationship(back_populates="packages")