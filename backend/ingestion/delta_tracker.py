"""
ingestion/delta_tracker.py
Manages sync cursors to enable delta (incremental) syncing.

Each sync cycle stores its cursor (a UTC timestamp) in the SyncLog table.
The next cycle reads the latest successful cursor and only requests
records modified after that timestamp — avoiding full reloads.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from storage.models import SyncLog, SyncStatus

logger = logging.getLogger(__name__)

# If no prior cursor exists, fetch from this date (first-ever run)
EPOCH_CURSOR = "2020-01-01T00:00:00+00:00"


class DeltaTracker:
    """
    Reads and writes sync cursors from/to the sync_log table.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_last_cursor(self, source_system: str) -> str:
        """
        Returns the cursor (ISO8601 timestamp) from the most recent
        successful sync for the given source system.

        If no successful sync exists, returns EPOCH_CURSOR.

        Args:
            source_system: 'greenhouse' or 'workday'

        Returns:
            ISO8601 string cursor value
        """
        last_log = (
            self.session.query(SyncLog)
            .filter(
                SyncLog.source_system == source_system,
                SyncLog.status == SyncStatus.SUCCESS,
                SyncLog.cursor_next.isnot(None),
            )
            .order_by(SyncLog.synced_at.desc())
            .first()
        )

        if last_log and last_log.cursor_next:
            logger.info(f"[DeltaTracker] {source_system} — using cursor: {last_log.cursor_next}")
            return last_log.cursor_next

        logger.info(f"[DeltaTracker] {source_system} — no prior cursor. Using epoch: {EPOCH_CURSOR}")
        return EPOCH_CURSOR

    def write_sync_log(
        self,
        source_system: str,
        cursor_used: str,
        cursor_next: str,
        records_pulled: int,
        records_inserted: int,
        records_updated: int,
        records_skipped: int,
        conflicts_detected: int,
        conflicts_resolved: int,
        duration_seconds: float,
        status: str = SyncStatus.SUCCESS,
        error_message: Optional[str] = None,
    ) -> SyncLog:
        """
        Writes a SyncLog row for this sync cycle.

        Args:
            source_system:      'greenhouse' or 'workday'
            cursor_used:        Cursor value used in this sync (input)
            cursor_next:        Cursor to use in next sync (current UTC time)
            records_*:          Counts from this sync cycle
            duration_seconds:   Wall-clock time for the full sync
            status:             SyncStatus enum value
            error_message:      Error detail if status != SUCCESS

        Returns:
            The persisted SyncLog ORM object
        """
        log = SyncLog(
            synced_at=datetime.now(timezone.utc),
            source_system=source_system,
            cursor_used=cursor_used,
            cursor_next=cursor_next,
            records_pulled=records_pulled,
            records_inserted=records_inserted,
            records_updated=records_updated,
            records_skipped=records_skipped,
            conflicts_detected=conflicts_detected,
            conflicts_resolved=conflicts_resolved,
            duration_seconds=round(duration_seconds, 3),
            status=status,
            error_message=error_message,
        )

        self.session.add(log)
        self.session.flush()   # Get the ID without committing

        logger.info(
            f"[DeltaTracker] Wrote sync log for {source_system}: "
            f"{records_inserted} inserted, {records_updated} updated, "
            f"{conflicts_detected} conflicts — status={status}"
        )

        return log
