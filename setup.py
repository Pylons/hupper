from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(here, 'README.rst')) as f:
        readme = f.read()
    with open(os.path.join(here, 'CHANGES.txt')) as f:
        CHANGES = f.read()
except IOError:
    readme = changes = ''

docs_require = [
    'Sphinx',
    'pylons-sphinx-themes',
]

tests_require = [
    'pytest',
    'pytest-cov',
    'mock',
]

setup(
    name='hupper',
    version='0.1',
    description='Integrated process monitor for developing servers.',
    long_description=readme + '\n\n' + changes,
    author='Michael Merickel',
    author_email='michael@merickel.org',
    url='https://github.com/Pylons/hupper',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    extras_require={
        'docs': docs_require,
        'testing': tests_require,
    },
    test_suite='tests',
    zip_safe=False,
    keywords='server reloader hup file watch process',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
)
