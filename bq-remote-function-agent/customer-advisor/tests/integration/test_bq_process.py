# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
from fastapi.testclient import TestClient
from app.fast_api_app import app

# Initialize Test Client
client = TestClient(app)

def test_bq_process_endpoint():
    """
    Independently verify the /bq_process endpoint using the provided 
    customer_scenarios.json data.
    """
    # 1. Load Test Data
    data_path = os.path.join("data", "customer_scenarios.json")
    if not os.path.exists(data_path):
        # Fallback if running relative to root or tests folder
        data_path = os.path.join(os.getcwd(), "data", "customer_scenarios.json")
    
    with open(data_path, "r") as f:
        payload = json.load(f)

    # 2. Make Request
    response = client.post("/", json=payload)

    # 3. Assertions
    assert response.status_code == 200, f"Request failed: {response.text}"
    
    response_json = response.json()
    assert "replies" in response_json, "Response missing 'replies' key"
    
    replies = response_json["replies"]
    assert len(replies) == len(payload["calls"]), "Mismatch in number of replies vs input calls"
    
    # 4. Content Verification (Spot checks)
    # Check that we got meaningful text back, not just empty strings
    for reply in replies:
        assert isinstance(reply, str), "Reply should be a string"
        # We expect either "NO_ISSUE" or specific agent content. 
        # If string is empty, that's a potential failure of logic.
        assert len(reply.strip()) > 0, "Reply should not be empty"

    print(f"\n✅ Successfully validated {len(replies)} scenarios.")
    for i, reply in enumerate(replies[:3]): # Print first 3 for visual confirmation
        print(f"--- Reply {i+1} ---\n{reply[:100]}...") 
