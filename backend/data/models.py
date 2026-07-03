"""SQLAlchemy ORM models for the PostgreSQL L2 cache.

These tables serve as a persistent store for NBA data fetched from the
external API. They outlive Redis TTLs and survive container restarts,
making cold-start performance acceptable even without a warm Redis cache.

Design principles:
- Every table has ``fetched_at`` (when we last pulled from nba_api) and
  ``expires_at`` (when the row should be considered stale). The application
  layer decides whether to refresh; the database just stores the timestamps.
- JSON columns (``data``) hold the raw serialised payload so schema changes
  in nba_api do not require a migration — only consumer code changes.
- ``ai_narratives`` is the only table that does NOT mirror nba_api output;
  it stores generated text and must be regenerated when its linked
  ``player_game_logs`` row has a newer ``last_game_date``.
"""

import datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class PlayerGameLogs(Base):
    """Game-by-game statistics for a player in one season.

    One row per (player_id, season). The ``data`` column holds the full list of
    per-game records as returned by ``nba_client.fetch_game_log``, serialised to
    JSON. Rolling averages are computed at read time from this payload — they are
    never stored here to avoid drift.
    """

    __tablename__ = "player_game_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    player_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    last_game_date: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True
    )
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PlayerBios(Base):
    """Biographical and roster data for a single player.

    Height and weight are stored in metric units (cm / kg) — the conversion from
    the imperial values returned by nba_api happens in the service layer before
    persistence.
    """

    __tablename__ = "player_bios"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    player_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    team_abbreviation: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    jersey_number: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DraftClasses(Base):
    """Full draft class for a given year.

    One row per draft year. ``data`` holds the list of all picks (both rounds) as
    returned by ``nba_client.fetch_draft_history``.
    """

    __tablename__ = "draft_classes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    season_year: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SeasonAverages(Base):
    """League-wide per-game averages snapshot for one season.

    One row per season. ``data`` holds the full LeagueDashPlayerStats payload.
    Rebuilt from the same nba_api call that powers the Draft Class Overview
    chart.
    """

    __tablename__ = "season_averages"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    season: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, index=True
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AiNarratives(Base):
    """AI-generated narrative text for a player's current-season performance.

    A narrative is stale when ``player_game_logs.last_game_date`` for the same
    ``(player_id, season)`` pair is newer than ``generated_at`` — meaning new
    games have been played since the last generation run. The application
    compares these two timestamps before deciding whether to regenerate or serve
    the cached text.
    """

    __tablename__ = "ai_narratives"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    player_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
