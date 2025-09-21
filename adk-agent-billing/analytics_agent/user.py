import google.auth

# How to retrieve user details on a production system is dependent on where how the agent is deployed
class User:
    def __init__(self):
        self.user_email = self._init_user()

    def get_user_email(self):
        return self.user_email

    def _init_user(self):
        try:
            credentials, project_id = google.auth.default()
            user_email = credentials.service_account_email
        except Exception:
            user_email = "anonymous"

        return user_email
