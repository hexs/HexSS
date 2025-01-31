from setuptools import setup, find_packages
from hexss import __version__ as version

setup(
    name='hexss',
    version=version,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    url='https://github.com/hexs/hexss',
    license="MIT",
    entry_points={
        'console_scripts': [
            'hexss_camera_server = hexss.server.camera_server:run',
            'hexss_file_manager_server = hexss.server.file_manager_server:run',
            'hexss_robot_server = hexss.control_robot.server:main',
            "hexss = hexss.__main__:run",
        ]
    }
)