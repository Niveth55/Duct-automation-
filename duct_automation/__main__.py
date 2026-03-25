"""
Allows running the package directly:
    python -m duct_automation [args...]
"""

import sys
from .cli import main

sys.exit(main())
