from __future__ import annotations

import sys

from airbyte_cdk import launch

from .source import SourceOdbc


def run() -> None:
    source = SourceOdbc()
    launch(source, sys.argv[1:])
