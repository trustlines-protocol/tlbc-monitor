from setuptools import setup, find_packages

setup(
    name="tlbc-monitor",
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    packages=find_packages(),
    install_requires=["click", "eth_utils", "structlog", "web3", "sqlalchemy"],
    extras_require={"test": ["eth-tester[py-evm]", "pytest"]},
    entry_points={"console_scripts": ["tlbc-monitor=monitor.main:main"]},
)
