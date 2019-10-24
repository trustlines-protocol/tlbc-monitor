from setuptools import find_packages, setup

setup(
    name="tlbc-monitor",
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    packages=find_packages(),
    package_data={"monitor": ["validator_contract_abi.json"]},
    install_requires=[
        "click",
        "eth_utils",
        "structlog",
        "web3",
        "sqlalchemy",
        "contract-deploy-tools",
        "attrs",
    ],
    extras_require={"test": ["eth-tester[py-evm]", "pytest"]},
    entry_points={
        "console_scripts": [
            "tlbc-monitor=monitor.main:main",
            "report-validator=report_validator.cli:main",
        ]
    },
)
