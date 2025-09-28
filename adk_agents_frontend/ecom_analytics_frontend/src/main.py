import os
import uvicorn
import vertexai

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from google import genai
from google.genai.types import HttpOptions

app = FastAPI()
SESSIONS = {}
BASE_DIR = Path(__file__).resolve().parent

# Replace PROJECT_ID and ENGINE_ID with your values
ENGINE_ID = os.environ.get("ENGINE_ID")
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", 'europe-west4')
AGENT_ENGINE_ID = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"
GENAI_CLIENT = genai.Client(http_options=HttpOptions(api_version="v1"))

# Get the existing agent engine
remote_agent_engine = vertexai.Client(location=LOCATION, ).agent_engines.get(name=AGENT_ENGINE_ID)

app.mount("/static", StaticFiles(directory=f"{BASE_DIR}/static"), name="static")
templates = Jinja2Templates(directory=f"{BASE_DIR}/templates")


def get_user_id(request: Request):
    # Important, to run on production, always validate user identity see https://github.com/googlecodelabs/user-authentication-with-iap/blob/master/3-HelloVerifiedUser/auth.py
    user_email = request.headers.get('X-Goog-Authenticated-User-Email',
                                     'user@example.com')  # Example from: https://github.com/googlecodelabs/user-authentication-with-iap/blob/master/2-HelloUser/main.py#L30
    return user_email


def genai_generate_content(prompt):
    return GENAI_CLIENT.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    ).text


async def create_session(user_id: str):
    remote_session = await remote_agent_engine.async_create_session(user_id=user_id)
    return remote_session


async def fetch_results(user_id, session, message):
    async for event in remote_agent_engine.async_stream_query(
            user_id=user_id,
            session_id=session["id"],
            message=message
    ):
        part = event['content']['parts'][0]
        if 'function_call' in event['content']['parts'][0]:
            yield f"Question asked: {part['function_call']['args']['question']}"

        elif 'function_response' in event['content']['parts'][0]:
            yield f"<pre><code>{part['function_response']['response']['results']['generated_sql']}</code></pre>"

        if 'text' in event['content']['parts'][0]:
            base_prompt = (""" Convert the following data into a single HTML block containing the table with the 
            given CSS styling below:
            <style>
.dark-data-table {
    /* Overall Structure */
    width: 100%;
    border-collapse: collapse;
    font-family: Arial, sans-serif;
    background-color: #1a1a1a; /* Very dark background */
    color: white;
}

/* Header Styling */
.dark-data-table thead th {
    background-color: #007bff; /* Bright blue header band */
    color: white;
    padding: 12px 15px;
    text-align: left;
    text-transform: uppercase;
    font-size: 14px;
    letter-spacing: 0.5px;
}

/* Data Row and Cell Styling */
.dark-data-table tbody td {
    padding: 12px 15px;
    /* Separator line for rows */
    border-bottom: 1px solid #333; 
}

/* Alignment for Columns */
.dark-data-table tbody td:nth-child(2) {
    /* Targets the 'TOTAL ORDER VALUE' column */
    text-align: right; 
    font-weight: bold; /* Makes the values stand out */
}

/* Optional: Slight hover effect for interactivity */
.dark-data-table tbody tr:hover {
    background-color: #2a2a2a;
}
</style>
            """)
            yield genai_generate_content(f"{base_prompt}{event['content']['parts'][0]['text']}")


@app.get("/favicon.ico", response_class=HTMLResponse)
async def favicon():
    return "<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚀</text></svg>"


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    return "User-agent: *\nDisallow: /"


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/clear", response_class=HTMLResponse)
async def clear_chat(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]
    response = HTMLResponse(content="")
    response.delete_cookie(key="session_id")
    return response


@app.post("/clicked", response_class=HTMLResponse)
async def clicked(request: Request):
    return "<p>You clicked the button!</p>"


async def stream_message(user_id, session, message):
    async for chunk in fetch_results(user_id, session, message):
        yield f"<div class='text-left my-2'><span class='inline-block bg-green-500 text-white rounded-lg p-2'>{chunk}</span></div>"


@app.post("/chat")
async def chat(request: Request, message: str = Form(...)):
    session_id = request.cookies.get("session_id")
    user_id = get_user_id(request)
    if not session_id or session_id not in SESSIONS:
        SESSIONS[session_id] = await create_session(user_id=user_id)

    session = SESSIONS[session_id]
    response = StreamingResponse(
        stream_message(user_id=user_id, session=session, message=message), media_type="text/html"
    )

    if not request.cookies.get("session_id"):
        response.set_cookie(key="session_id", value=session_id)
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
