from setuptools import setup

setup(
    name="temp-controller",
    version="0.0.1",
    description='RPI cpu temperature pwm fan controller',
    long_description=open('README.md').read(),
    classifiers=[],
    install_requires=['rpi-hardware-pwm'],
    setup_requires=['setuptools_scm', 'tox'],
    scripts=[],
    entry_points={},
    zip_safe=False,
    include_package_data=True,
    python_requires='>3.0'
)