### Development Setup

1. Create a Virtual Environment

```shell
python -m venv .venv
   ```

2. Install Required Tools

```shell
pip install setuptools wheel twine
```

3. Build Distribution Packages

```shell
python setup.py sdist bdist_wheel
```