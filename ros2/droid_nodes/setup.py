from setuptools import setup

package_name = "droid_nodes"

setup(
    name=package_name,
    version="1.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="DroidOS project",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "droid_supervisor = droid_nodes.supervisor_node:main",
            "droid_safety_gateway = droid_nodes.safety_gateway_node:main",
            "droid_language = droid_nodes.language_node:main",
        ],
    },
)
