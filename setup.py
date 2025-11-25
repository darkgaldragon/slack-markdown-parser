"""
Setup script for slack-markdown-parser package
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='slack-markdown-parser',
    version='1.0.0',
    author='darkgaldragon（ぎゃうどら）',
    description='Convert Markdown text to Slack blocks with table support',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/darkgaldragon/slack-markdown-parser',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.8',
    install_requires=[
        # 標準ライブラリのみ使用（reモジュール）
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ],
    },
    keywords='slack markdown parser converter blocks table',
    project_urls={
        'Bug Reports': 'https://github.com/darkgaldragon/slack-markdown-parser/issues',
        'Source': 'https://github.com/darkgaldragon/slack-markdown-parser',
    },
)
