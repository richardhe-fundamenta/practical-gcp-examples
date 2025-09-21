
from google import genai
from .logging_utils import setup_llm_logger, log_llm_call
from .user import User


class GenAIClientDecorator:
    def __init__(self, agent_name,  client: genai.Client):
        self._client = client
        self._logger = setup_llm_logger()
        self._user_email = User().get_user_email()
        self._agent_name = agent_name

    @property
    def models(self):
        return self

    def generate_content(self, *args, **kwargs):
        response = self._client.models.generate_content(*args, **kwargs)
        log_llm_call(self._logger, self._agent_name, self._user_email, response.usage_metadata)
        return response

    def __getattr__(self, name):
        return getattr(self._client, name)
