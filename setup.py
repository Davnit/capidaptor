#!/usr/bin/env python3

from setuptools import setup

setup(
    name='capidaptor',
    version='0.1',
    description='Proxy to allow legacy BNET clients to connect to the chat API',
    author='Davnit',
    author_email='david@davnit.net',
    install_requires=['websocket-client>=0.53.0']
)
