from setuptools import setup, find_packages

setup(
    name="callsign-lookup",
    version="1.0.0",
    description="A tool for managing and querying FCC amateur radio license database files",
    author="Tiran Dagan",
    author_email="tiran@tirandagan.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests",
        "tqdm",
        "colorama",
    ],
    entry_points={
        "console_scripts": [
            "callsign-lookup=callsign_lookup:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Communications :: Ham Radio",
    ],
) 