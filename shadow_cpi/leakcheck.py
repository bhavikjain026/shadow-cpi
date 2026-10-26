"""Look-ahead check (safe / date_flag / leak). Moved to the standalone timelock/ module; kept here for old imports."""
from timelock.check import DATE_FLAG, LEAK, SAFE, check_result, check_results
from timelock.dates import url_date

__all__ = ["check_result", "check_results", "url_date", "SAFE", "DATE_FLAG", "LEAK"]
