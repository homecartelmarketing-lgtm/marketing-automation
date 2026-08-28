"""CLI entrypoint to run This or That End-to-End Automation Pipeline.

Usage::

    # Run 1 row (Scrape 1 pair -> Generate Story -> Save to Airtable)
    python run_this_or_that.py --target wall_lights
    python run_this_or_that.py --target table_lamps
    python run_this_or_that.py --target cluster_chandelier
    python run_this_or_that.py --target floor_lamp

    # Run multiple rows end-to-end (one by one)
    python run_this_or_that.py --target wall_lights --count 3

    # Generate only on existing pending rows in Airtable
    python run_this_or_that.py --target wall_lights --mode generate

    # Target a specific Airtable Record ID
    python run_this_or_that.py --target wall_lights --record-id rec1GhZHJXRVC5Mf8
"""

import sys
from generate_this_or_that_pipeline import main

if __name__ == "__main__":
    sys.exit(main())
