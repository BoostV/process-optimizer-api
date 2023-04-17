import os
import sys

if True:
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../optimizerapi"))
    )
    import optimizer
    import securepickle
