---
description: Learn the prerequisites for using the Intel® Geti™ REST API, including Python setup, required packages, and authentication steps.
---

# Prerequisites

Before we start, make sure you have the following:
1. A Python 3 interpreter installed on your machine. Any version will work, but the Python 3.8 or newer is recommended.

2. Install required `requests` package. You can do this by running the following command in your terminal:

    ```bash
    python3 -m pip install requests
    ```

3. For The Intel® Geti™ Platform Host address please use the host name used to access the Intel® Geti™ UI, e.g.: https://app.geti.intel.com, http://localhost:80, https://10.211.120.123/.

4. Obtain a Personal Access Token that can be used for authentication. You can generate it through the Intel® Geti™ user interface: open the *Account* section, select the *Token* tab and click `Create`. For reference check the [Obtain access section](../get-started.md#obtain-access).

5. [Optional] Proxy environment variables set up on your machine if needed.

```python title="setup.py" showLineNumbers
HOST = "https://app.geti.intel.com/"
TOKEN = "{YOUR_API_KEY}"

# Following the information from the API documentation, append the API version to the host URL.
# All endpoints include the API version in their address and rely on this variable.
HOST = HOST + "api/v1/"

# Include the `x-api-key` header in all API calls to authenticate requests.
headers = {"x-api-key": TOKEN}
```
