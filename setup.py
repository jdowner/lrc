#!/usr/bin/env python

import setuptools


setuptools.setup(
        name='lrc',
        version='0.1',
        license='MIT',
        author='Joshua Downer',
        author_email='joshua.downer@gmail.com',
        packages=['lrc'],
        package_data={
          '': ['share/*', '*.md', 'LICENSE'],
        },
        data_files=[
          ('share/lrc/', [
              'README.md',
              'LICENSE',
              ]),
        ],
        scripts=['bin/lrcc'],
        platforms=['Unix'],
        classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: Unix',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3.4',
            'Topic :: Software Development',
            ]
        )
