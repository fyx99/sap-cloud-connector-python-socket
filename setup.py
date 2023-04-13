from setuptools import setup

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='sapcloudconnectorpythonsocket',
    version='0.1.2',    
    description='Python Package to open socket to SAP Cloud Connector via Connectivity Proxy',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/fyx99/sap-cloud-connector-python-socket',
    author='fxy99',
    author_email='',
    license='MIT',
    packages=['sapcloudconnectorpythonsocket'],
    install_requires=[],

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',  
        'Operating System :: POSIX :: Linux',        
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)