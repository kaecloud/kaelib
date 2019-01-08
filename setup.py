#!/usr/bin/env python
# -*- coding:utf-8 -*-

import sys
import re
import os
from os.path import dirname, abspath
from setuptools import setup, find_packages


def find_version(*paths):
    fname = os.path.join(*paths)
    with open(fname) as fhandler:
        version_file = fhandler.read()
        version_match = re.search(r"^__VERSION__ = ['\"]([^'\"]*)['\"]",
                                  version_file, re.M)

    if not version_match:
        raise RuntimeError("Unable to find version string in %s" % (fname,))

    version = version_match.group(1)

    return version


def find_readme(*paths):
    with open(os.path.join(*paths)) as f:
        return f.read()


version = find_version('kaelib', '__init__.py')

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

requires = [
    'requests>=2.20.0',
    'websocket-client==0.54.0',
    'humanfriendly==4.17',
    'addict==2.2.0',
    'marshmallow==2.17.0',
]
root_dir = dirname(abspath(__file__))

setup(
    name='kaelib',
    version=version,
    description='kae api library',
    long_description=find_readme('README.md'),
    long_description_content_type='text/markdown',
    author='Yu Yang',
    author_email='yangyu@geetest.com',
    url='https://github.com/kaecloud/kaelib',
    include_package_data=True,
    packages=find_packages(root_dir),
    install_requires=requires,
    setup_requires=pytest_runner,
    tests_require=[
        "pyyaml",
        "pytest-cov",
        "pytest-randomly",
        "pytest-mock",
        "pytest>3.0",
    ],
)
