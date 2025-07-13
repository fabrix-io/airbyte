#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

import sys

from airbyte_cdk.entrypoint import launch
from source_hashicorp_vault import SourceHashicorpVault

if __name__ == "__main__":
    source = SourceHashicorpVault()
    launch(source, sys.argv[1:])