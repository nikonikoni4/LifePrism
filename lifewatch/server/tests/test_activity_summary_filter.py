"""
Activity Summary API Unit Tests
Tests for the category filter functionality in the activity summary endpoint.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lifewatch.server.services.activity_summery_service import ActivitySummaryService


class TestActivitySummaryService:
    """Test cases for ActivitySummaryService with filter functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = ActivitySummaryService()
        self.test_date = "2025-12-14"
        self.history_days = 7
        self.future_days = 7
    
    def test_get_activity_summary_without_filter(self):
        """Test fetching activity summary without category filter"""
        with patch.object(
            self.service.statistical_data_provider, 
            'get_daily_active_time'
        ) as mock_daily, patch.object(
            self.service.statistical_data_provider,
            'get_active_time'
        ) as mock_active:
            # Mock return values
            mock_daily.return_value = [
                {"date": "2025-12-10", "active_time_percentage": 45},
                {"date": "2025-12-11", "active_time_percentage": 60},
                {"date": "2025-12-12", "active_time_percentage": 55},
            ]
            mock_active.return_value = 23400  # 6.5 hours in seconds
            
            # Call service
            result = self.service.get_activity_summary_data(
                self.test_date, self.history_days, self.future_days
            )
            
            # Verify
            assert result is not None
            assert result.today_active_time == "6h 30m"
            assert len(result.daily_activities) == self.history_days + self.future_days + 1
            
            # Verify data provider was called without filter params
            mock_daily.assert_called_once()
            call_args = mock_daily.call_args
            assert call_args[0][2] is None  # category_id
            assert call_args[0][3] is None  # sub_category_id
    
    def test_get_activity_summary_with_category_filter(self):
        """Test fetching activity summary with category filter"""
        with patch.object(
            self.service.statistical_data_provider, 
            'get_daily_active_time'
        ) as mock_daily, patch.object(
            self.service.statistical_data_provider,
            'get_active_time'
        ) as mock_active, patch.object(
            self.service.category_service,
            'get_category_by_id'
        ) as mock_category:
            # Mock return values
            mock_daily.return_value = [
                {"date": "2025-12-10", "active_time_percentage": 25},
                {"date": "2025-12-11", "active_time_percentage": 30},
            ]
            mock_active.return_value = 10800  # 3 hours
            mock_category.return_value = {
                "id": "work",
                "name": "Work",
                "color": "#5B8FF9"
            }
            
            # Call service with category filter
            result = self.service.get_activity_summary_data(
                self.test_date, self.history_days, self.future_days,
                category_id="work"
            )
            
            # Verify
            assert result is not None
            assert result.today_active_time == "3h 0m"
            
            # Verify filter was applied
            mock_daily.assert_called_once()
            call_args = mock_daily.call_args
            assert call_args[0][2] == "work"  # category_id
            
            # Verify color is included
            for daily in result.daily_activities:
                assert daily.color == "#5B8FF9"
    
    def test_get_activity_summary_with_subcategory_filter(self):
        """Test fetching activity summary with sub-category filter"""
        with patch.object(
            self.service.statistical_data_provider, 
            'get_daily_active_time'
        ) as mock_daily, patch.object(
            self.service.statistical_data_provider,
            'get_active_time'
        ) as mock_active, patch.object(
            self.service.category_service,
            'get_category_by_id'
        ) as mock_category:
            # Mock return values
            mock_daily.return_value = [
                {"date": "2025-12-10", "active_time_percentage": 15},
            ]
            mock_active.return_value = 5400  # 1.5 hours
            mock_category.return_value = {
                "id": "work",
                "name": "Work", 
                "color": "#5B8FF9"
            }
            
            # Call service with both filters
            result = self.service.get_activity_summary_data(
                self.test_date, self.history_days, self.future_days,
                category_id="work",
                sub_category_id="coding"
            )
            
            # Verify filter was applied
            mock_daily.assert_called_once()
            call_args = mock_daily.call_args
            assert call_args[0][2] == "work"  # category_id
            assert call_args[0][3] == "coding"  # sub_category_id
    
    def test_date_range_calculation(self):
        """Test that date range is correctly calculated"""
        with patch.object(
            self.service.statistical_data_provider, 
            'get_daily_active_time'
        ) as mock_daily, patch.object(
            self.service.statistical_data_provider,
            'get_active_time'
        ) as mock_active:
            mock_daily.return_value = []
            mock_active.return_value = 0
            
            result = self.service.get_activity_summary_data(
                self.test_date, 3, 2
            )
            
            # Should have 3 + 2 + 1 = 6 days
            assert len(result.daily_activities) == 6
            
            # Verify start date
            call_args = mock_daily.call_args
            start_date = call_args[0][0]
            end_date = call_args[0][1]
            
            expected_start = (datetime.strptime(self.test_date, "%Y-%m-%d") - timedelta(days=3)).strftime("%Y-%m-%d")
            expected_end = (datetime.strptime(self.test_date, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")
            
            assert start_date == expected_start
            assert end_date == expected_end
    
    def test_missing_dates_filled_with_zero(self):
        """Test that missing dates are filled with 0% activity"""
        with patch.object(
            self.service.statistical_data_provider, 
            'get_daily_active_time'
        ) as mock_daily, patch.object(
            self.service.statistical_data_provider,
            'get_active_time'
        ) as mock_active:
            # Return only one day of data
            mock_daily.return_value = [
                {"date": "2025-12-14", "active_time_percentage": 50}
            ]
            mock_active.return_value = 3600
            
            result = self.service.get_activity_summary_data(
                self.test_date, 2, 2
            )
            
            # Should have 5 days total
            assert len(result.daily_activities) == 5
            
            # Only one day should have non-zero value
            non_zero_days = [d for d in result.daily_activities if d.active_time_percentage > 0]
            assert len(non_zero_days) == 1
            assert non_zero_days[0].date == "2025-12-14"
            assert non_zero_days[0].active_time_percentage == 50


class TestStatisticalDataProviderFilter:
    """Test cases for ServerLWDataProvider.get_daily_active_time with filters"""
    
    def test_sql_query_without_filter(self):
        """Test that SQL query is correct without filters"""
        from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
        
        with patch('lifewatch.storage.lw_db_manager') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cursor
            mock_db.get_connection.return_value.__enter__ = lambda x: mock_conn
            mock_db.get_connection.return_value.__exit__ = lambda x, a, b, c: None
            
            provider = ServerLWDataProvider()
            provider.lw_db_manager = mock_db
            
            provider.get_daily_active_time("2025-12-01", "2025-12-15")
            
            # Verify SQL executed
            mock_cursor.execute.assert_called_once()
            sql = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            # Should not have category filter in WHERE
            assert "category_id" not in sql or "category_id = ?" not in sql
            assert len(params) == 2  # Only start and end date
    
    def test_sql_query_with_category_filter(self):
        """Test that SQL query includes category filter"""
        from lifewatch.server.providers.statistical_data_providers import ServerLWDataProvider
        
        with patch('lifewatch.storage.lw_db_manager') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cursor
            mock_db.get_connection.return_value.__enter__ = lambda x: mock_conn
            mock_db.get_connection.return_value.__exit__ = lambda x, a, b, c: None
            
            provider = ServerLWDataProvider()
            provider.lw_db_manager = mock_db
            
            provider.get_daily_active_time("2025-12-01", "2025-12-15", category_id="work")
            
            # Verify SQL executed with filter
            mock_cursor.execute.assert_called_once()
            sql = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert "category_id = ?" in sql
            assert len(params) == 3  # start, end, category_id
            assert params[2] == "work"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
