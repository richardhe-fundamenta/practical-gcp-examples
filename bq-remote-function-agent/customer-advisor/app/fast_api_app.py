import logging
import os
import asyncio
import uuid
import json

from typing import List, Any
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from fastapi import FastAPI, Request
from pydantic import BaseModel
from contextlib import asynccontextmanager

from app.agent import app as adk_app
from google.adk.cli.fast_api import get_fast_api_app

# Set up logging
logger = logging.getLogger(__name__)


# --- Data Models ---
class Feedback(BaseModel):
    run_id: str
    feedback_score: float
    feedback_text: str

class BQRequest(BaseModel):
    caller: str
    sessionUser: str
    userDefinedContext: dict = None
    calls: List[List[Any]]

class BQResponse(BaseModel):
    replies: List[str]

# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services if needed
    yield
    # Shutdown: Clean up resources
    pass

# We utilize the helper to get the standard ADK FastAPI app but manage our own lifecycle for custom routes
app = get_fast_api_app(
    agents_dir=".",
    artifact_service_uri=None,
    allow_origins=["*"],
    session_service_uri=None,
    web=True, 
)

# --- Concurrency Control ---
# Limits how many rows across all requests are processed simultaneously
# to stay within Vertex AI RPM limits and JVM/resource bounds.
MAX_CONCURRENT_ROWS = 10 
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ROWS)

class TransientError(Exception):
    """Exception for errors that should trigger a BigQuery retry (e.g., 429 Quota)."""
    pass

@app.post("/")
async def process_bq_batch(request: BQRequest) -> BQResponse:
    """
    Handles BigQuery Remote Function batches (calls).
    Each item in 'calls' is a row of arguments.
    """
    
    async def process_row(row_values: List[Any]) -> str:
        async with global_semaphore:
            session_id = str(uuid.uuid4())
            user_id = "bq-remote-user"
            app_name = adk_app.name
            
            # Local session service for batch processing
            session_service = InMemorySessionService()
            
            try:
                # 1. Create Session
                await session_service.create_session(
                    session_id=session_id, 
                    app_name=app_name, 
                    user_id=user_id
                )
                
                # 2. Instantiate Runner
                runner = Runner(
                    agent=adk_app.root_agent, 
                    session_service=session_service, 
                    app_name=app_name
                )

                # 3. Construct Message
                prompt_text = f"Analyze Customer Record: {row_values}"
                message = types.Content(
                    role="user", 
                    parts=[types.Part.from_text(text=prompt_text)]
                )
                
                # 4. Run Agent (Wait for completion)
                async for _ in runner.run_async(
                    new_message=message,
                    user_id=user_id,
                    session_id=session_id
                ):
                    pass
                
                # 5. Extract Structured Results from State
                session = await session_service.get_session(
                    app_name=app_name, 
                    user_id=user_id, 
                    session_id=session_id
                )
                state = session.state if session else {}
                
                structured_result = {
                    "security": state.get("security_results", "NO_ISSUE"),
                    "billing": state.get("billing_results", "NO_ISSUE"),
                    "retention": state.get("retention_results", "NO_ISSUE")
                }
                
                return json.dumps(structured_result)

            except Exception as e:
                # Unwrap ExceptionGroups (TaskGroups) for clearer logging
                err_type = type(e).__name__
                err_msg = str(e)
                if hasattr(e, "exceptions") and e.exceptions:
                    err_msg = f"{err_type} sub-error: {str(e.exceptions[0])}"
                
                # If it's a Quota/Rate Limit error, raise TransientError to trigger a batch retry
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    raise TransientError(err_msg)
                
                # Suppress OTel noise but log real logic errors
                if "different Context" not in err_msg:
                    logger.error(f"Permanent error processing row: {err_msg}")
                
                return json.dumps({"error": err_msg})

    # High-Performance Batch Processing with Chunking
    CHUNK_SIZE = 10
    replies = []
    
    from fastapi import HTTPException

    for i in range(0, len(request.calls), CHUNK_SIZE):
        batch_chunk = request.calls[i : i + CHUNK_SIZE]
        tasks = [process_row(row) for row in batch_chunk]
        
        # We process the chunk. If any row raises an unhandled error (like TransientError),
        # the whole chunk_results assignment will fail and propagate the error.
        try:
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in chunk_results:
                if isinstance(res, TransientError):
                    # If we found a transient quota error in the batch, 
                    # tell BQ to retry the whole thing.
                    logger.warning(f"Quota exceeded (429). Triggering BQ retry: {res}")
                    raise HTTPException(status_code=500, detail="Quota Exceeded (429). Retryable.")
                
                if isinstance(res, Exception):
                    # For other unexpected exceptions, log and return error in JSON
                    replies.append(json.dumps({"error": f"Internal Task Error: {str(res)}"}))
                else:
                    replies.append(res)
        except HTTPException:
            # Re-raise FastAPIs HTTP exceptions so they reach the client (BQ)
            raise
        except Exception as e:
            # Catch-all for any other errors in the chunking logic
            logger.error(f"Critical batch error: {e}")
            raise HTTPException(status_code=500, detail="Internal Batch Processing Error")

    return BQResponse(replies=replies)

@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    logger.info(f"Feedback received: {feedback.model_dump()}")
    return {"status": "success"}

# Main execution
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
