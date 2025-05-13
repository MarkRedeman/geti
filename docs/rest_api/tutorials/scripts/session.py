# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import requests
import urllib3
from os import getenv

HOST = getenv("GETI_HOST")
TOKEN = getenv("GETI_API_KEY")

if TOKEN is None:
    raise Exception("The environment variable `GETI_API_KEY` has not been set")

if HOST is None:
    raise Exception("The environment variable `GETI_API_HOST` has not been set")

# Following the information from the API documentation, append the API version to the host URL.
# All endpoints include the API version in their address and rely on this variable.
BASE_URL = f"{HOST}/api/v1"

# Create a session to reuse connection settings and headers.
session = requests.Session()

# Add default headers
session.headers.update({"x-api-key": TOKEN})
session.headers.update({"Accept": "application/json"})

if getenv("GETI_VERIFY_SSL") != "false":
    # Disable insecure request warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session.verify = False  # Set SSL verification
