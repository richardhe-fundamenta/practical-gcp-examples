# ruff: noqa
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

import os
from typing import Annotated

import google.auth
from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.apps.app import App
from google.adk.models import Gemini
from google.genai import types

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


# ==========================================
# 1. Define Sub-Agents (The Specialists)
# ==========================================

security_agent = LlmAgent(
    name="SecurityGuardian",
    model=Gemini(model="gemini-3-flash-preview"),
    description="Handles critical security alerts.",
    instruction="""
    You are the 'SecurityGuardian'.
    Scan the input data for: 'suspicious_login', 'no_2fa', 'password_old'.
    
    If NONE of these triggered: Output exactly "NO_ISSUE".
    
    If an issue exists, output:
    "URGENT: [Subject Line]
    [Body text]"
    """,
    output_key="security_results",
)

billing_agent = LlmAgent(
    name="BillingAdvisor",
    model=Gemini(model="gemini-3-flash-preview"),
    description="Handles payment and subscription issues.",
    instruction="""
    You are the 'BillingAdvisor'.
    Scan the input data for: 'card_expiring', 'payment_failed', 'renewal_soon'.
    
    If NONE of these triggered: Output exactly "NO_ISSUE".
    
    If an issue exists, output:
    "Action Required: [Subject Line]
    [Body text]"
    """,
    output_key="billing_results",
)

retention_agent = LlmAgent(
    name="RetentionSpecialist",
    model=Gemini(model="gemini-3-flash-preview"),
    description="Handles engagement and rewards.",
    instruction="""
    You are the 'RetentionSpecialist'.
    Scan the input data for: 'low_usage', 'unused_points', 'inactive'.
    
    If NONE of these triggered: Output exactly "NO_ISSUE".
    
    If an opportunity exists, output:
    "Hi there! [Friendly Subject Line]
    [Body text]"
    """,
    output_key="retention_results",
)


# ==========================================
# 2. Define Root Agent (Parallel Orchestrator)
# ==========================================

class CustomerScanner(ParallelAgent):
    """Custom wrapper to identify the agent as part of the local app module."""
    pass

root_agent = CustomerScanner(
    name="customer_advisor",
    description="Scans customer data across Security, Billing, and Retention tracks simultaneously.",
    sub_agents=[security_agent, billing_agent, retention_agent],
)

app = App(root_agent=root_agent, name="app")
