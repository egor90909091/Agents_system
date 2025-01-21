from setuptools import setup, find_packages

setup(
    name="delivery_system",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'mesa',
        'numpy',
        'networkx',
        'pandas'
    ],
    python_requires='>=3.7',
)