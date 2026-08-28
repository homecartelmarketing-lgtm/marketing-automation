"""Alias for run_1_product_3_styles_feed.py."""
import sys
from run_1_product_3_styles_feed import (
    OneProductThreeStylesRunner,
    PRESETS,
    main,
)

# Backward-compatibility alias
OneStyleThreeProductsRunner = OneProductThreeStylesRunner

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
