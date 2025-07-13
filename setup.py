"""
Setup module for the Airbyte Source HashiCorp Vault connector.
"""

from setuptools import find_packages, setup

MAIN_REQUIREMENTS = [
    "airbyte-cdk>=0.51.0",
    "hvac>=1.2.1",
]

TEST_REQUIREMENTS = [
    "pytest>=7.2.0",
    "pytest-mock",
    "requests-mock",
]

setup(
    name="source_hashicorp_vault",
    description="Source implementation for HashiCorp Vault.",
    author="Airbyte",
    author_email="contact@airbyte.io",
    packages=find_packages(),
    install_requires=MAIN_REQUIREMENTS,
    package_data={"": ["*.json", "*.yaml", "schemas/*.json", "schemas/shared/*.json"]},
    extras_require={
        "tests": TEST_REQUIREMENTS,
    },
)