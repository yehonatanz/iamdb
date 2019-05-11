from setuptools import find_packages, setup

setup(
    name="iamdb",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["click", "keyring", "pymongo", "keyring"],
    entry_points={"console_scripts": ["iamdb=iamdb.cli:cli"]},
)
