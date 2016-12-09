'''Packager'''
## Standard Library
import codecs
import os
## Third Party
import setuptools


def read(*parts):
    '''Read external file.'''
    here = os.path.abspath(os.path.dirname(__file__))
    return codecs.open(os.path.join(here, *parts), 'r').read()


setuptools.setup(
    name='flowlogd',
    version='1.0.0',
    packages=setuptools.find_packages(),
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Intended Audience :: Developers',
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Distributed Computing',
    ],
    license='BSD License',
    author='Saju Madhavan',
    author_email='sajuptpm@gmail.com',
    description='FlowLogd',
    long_description=read('README.md'),
    keywords='',
    platforms='any',
    url='https://github.com/JioCloudVPC/flowlogd',
    #data_files = [('/etc/flowlog', ['flowlogd/vpc_flow_logs.cfg'])]
)

