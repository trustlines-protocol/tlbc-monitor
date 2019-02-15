from setuptools import setup, find_packages

setup(
    name='tlbc-watchdog',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        'click',
        'eth_utils',
        'structlog',
        'web3',
        'sqlalchemy',
    ],
    extras_require={
        'test': [
            'eth-tester[py-evm]',
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'tlbc-watchdog=watchdog.main:main',
        ],
    }
)
