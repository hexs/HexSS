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

4. Set the proxy environment variables. if you need to use proxy:

- For Windows (Command Prompt):
  ```shell
  set HTTPS_PROXY=http://<user>:<pass>@<ip>:<port>
  ```
  ```shell
  set HTTP_PROXY=http://<user>:<pass>@<ip>:<port>
  ```

- For Windows (PowerShell):

  ```shell
  $env:HTTPS_PROXY = "http://<user>:<pass>@<ip>:<port>"
  ```
  ```shell
  $env:HTTP_PROXY = "http://<user>:<pass>@<ip>:<port>"
  ```

5. upload 

```shell
twine upload dist/*
```