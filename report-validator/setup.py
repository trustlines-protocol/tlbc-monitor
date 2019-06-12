from setuptools import setup, find_packages

setup(
    nam="report-validator",
    setup_requires="setuptools_scm",
    # use_scm_version=True,
    version="0.0.1",
    packages=find_packages(),
    package_data={"report_validator": ["contracts.json"]},
    install_requires=["click", "web3", "contract-deploy-tools"],
    entry_points="""
    [console_scripts]
    report-validator=report_validator.cli:main
    """,
)
