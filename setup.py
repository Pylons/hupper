from setuptools import setup, find_packages

def readfile(name):
    with open(name) as f:
        return f.read()

readme = readfile('README.rst')
changes = readfile('CHANGES.rst')

docs_require = [
    'watchdog',
    'Sphinx',
    'pylons-sphinx-themes',
]

tests_require = [
    'watchdog',
    'pytest',
    'pytest-cov',
    'mock',
]

setup(
    name='hupper',
    version='0.4.1',
    description='Integrated process monitor for developing servers.',
    long_description=readme + '\n\n' + changes,
    author='Michael Merickel',
    author_email='michael@merickel.org',
    url='https://github.com/Pylons/hupper',
    packages=find_packages('src', exclude=['tests']),
    package_dir={'': 'src'},
    include_package_data=True,
    extras_require={
        'docs': docs_require,
        'testing': tests_require,
    },
    entry_points={"console_scripts": ["hupper = hupper.cli:main"]},
    zip_safe=False,
    keywords='server daemon autoreload reloader hup file watch process',
    classifiers=[
        'Development Status :: 4 - Beta',
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
