from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='kanban-simulator',
    version='0.2',
    description='Simulate work flowing through a Kanban board',
    long_description=long_description,
    author='Martin Aspeli',
    author_email='optilude@gmail.com',
    url='https://github.com/optilude/kanban-simulator',
    license='MIT',
    keywords='agile kanban analytics',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=[
    ],

    # extras_require={
    #     'dev': ['check-manifest'],
    #     'test': ['coverage'],
    # },

    # entry_points={
    #     'console_scripts': [
    #         'kanban-simulator=kanban_simulator.cli:main',
    #     ],
    # },
)
