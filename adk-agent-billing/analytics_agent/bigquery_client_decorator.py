from google.cloud import bigquery
from .logging_utils import setup_bigquery_logger, log_bigquery_job
from .user import User


class BigQueryClientDecorator:
    def __init__(self, agent_name,  client: bigquery.Client):
        self._client = client
        self._logger = setup_bigquery_logger()
        self._user_email = User().get_user_email()
        self._agent_name = agent_name

    def query(self, *args, **kwargs):
        query_job = self._client.query(*args, **kwargs)
        log_bigquery_job(self._logger, self._agent_name, self._user_email, query_job)
        return query_job

    def __getattr__(self, name):
        return getattr(self._client, name)
