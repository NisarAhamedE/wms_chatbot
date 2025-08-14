"""
Setup configuration for WMS Chatbot package
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    return "WMS Chatbot - Enterprise Warehouse Management System AI Assistant"

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="wms-chatbot",
    version="1.0.0",
    author="WMS Development Team",
    author_email="dev@wms-chatbot.com",
    description="Enterprise AI-powered chatbot for warehouse management systems",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/wms-chatbot",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Office/Business :: Financial :: Point-Of-Sale",
    ],
    python_requires=">=3.11",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pre-commit>=3.0.0",
            "httpx>=0.24.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0",
            "grafana-api>=1.0.3",
        ],
        "production": [
            "gunicorn>=21.0.0",
            "uvicorn[standard]>=0.23.0",
            "psutil>=5.9.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "wms-chatbot=src.api.main:main",
            "wms-setup=src.scripts.setup:main",
            "wms-migrate=src.scripts.migrate:main",
        ],
    },
    include_package_data=True,
    package_data={
        "wms_chatbot": [
            "database/*.sql",
            "monitoring/*.yml",
            "nginx/*.conf",
        ],
    },
    zip_safe=False,
    keywords="wms warehouse management chatbot ai langchain fastapi",
    project_urls={
        "Bug Reports": "https://github.com/your-org/wms-chatbot/issues",
        "Source": "https://github.com/your-org/wms-chatbot",
        "Documentation": "https://docs.wms-chatbot.com",
    },
)