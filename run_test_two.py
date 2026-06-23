# run_test_two.py
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adb_bulk_category_search import automate_category_search

# Only 2 test categories in Mangalore to check non-duplicate insertion
test_categories = ["Car Rental", "Mini Bus On Rent"]

if __name__ == "__main__":
    automate_category_search(location="Mangalore", categories=test_categories, scrolls=5)
