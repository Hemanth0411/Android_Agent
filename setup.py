#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="android-agent",
    version="0.1.0",
    description="A lightweight automation system for Android devices using vision models",
    author="AI Agent Developer",
    author_email="example@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "openai",
        "Pillow",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 