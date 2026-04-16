"""Tests for the scheduler module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestSchedulerJobs:
    @patch("bgscraper.scheduler.main.send_daily_digest")
    @patch("bgscraper.scheduler.main.mark_daily_notified")
    @patch("bgscraper.scheduler.main.daily_new_listings", return_value=[])
    @patch("bgscraper.scheduler.main.expire_stale", return_value=0)
    @patch("bgscraper.scheduler.main.run_all", return_value=[])
    @patch("bgscraper.scheduler.main.session_scope")
    def test_daily_job_runs(
        self, mock_scope, mock_run_all, mock_expire,
        mock_daily_new, mock_mark, mock_send,
    ):
        from bgscraper.scheduler.main import _daily_job

        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)

        _daily_job()

        mock_run_all.assert_called_once()
        mock_expire.assert_called_once()
        mock_daily_new.assert_called_once()
        # No new listings → send_daily_digest not called.
        mock_send.assert_not_called()

    @patch("bgscraper.scheduler.main.send_weekly_digest")
    @patch("bgscraper.scheduler.main.all_active_listings", return_value=[])
    @patch("bgscraper.scheduler.main.session_scope")
    def test_weekly_job_runs(self, mock_scope, mock_active, mock_send):
        from bgscraper.scheduler.main import _weekly_job

        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)

        _weekly_job()

        mock_active.assert_called_once()
        # No active listings → send not called.
        mock_send.assert_not_called()


class TestSchedulerStart:
    @patch("bgscraper.scheduler.main.BlockingScheduler")
    @patch("bgscraper.scheduler.main.Base")
    def test_registers_two_jobs(self, mock_base, mock_scheduler_cls, settings):
        from bgscraper.scheduler.main import start

        mock_sched = MagicMock()
        mock_scheduler_cls.return_value = mock_sched
        mock_sched.start = MagicMock()

        start()

        assert mock_sched.add_job.call_count == 2
        job_ids = [call.kwargs["id"] for call in mock_sched.add_job.call_args_list]
        assert "daily_scrape" in job_ids
        assert "weekly_digest" in job_ids
        mock_sched.start.assert_called_once()
