#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

import sys
from airbyte_cdk.entrypoint import launch
from .source import SourceOnepassword


def run():
    source = SourceOnepassword()
    launch(source, sys.argv[1:])


if __name__ == "__main__":
    run()