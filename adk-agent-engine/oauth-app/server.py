from flask import Flask, request, redirect, session
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# GitHub OAuth App credentials
CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
REDIRECT_URI = 'https://vertexaisearch.cloud.google.com/oauth-redirect'

@app.route('/')
def home():
    return f'''
    <!DOCTYPE html>
    <html>
      <head>
        <title>GitHub OAuth Demo</title>
        <style>
          body {{
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
          }}
          .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #24292e;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
          }}
          .button:hover {{
            background-color: #0366d6;
          }}
        </style>
      </head>
      <body>
        <h1>GitHub OAuth Demo</h1>
        <p>Click the button below to authenticate with GitHub:</p>
        <a href="https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=user:email" class="button">
          Sign in with GitHub
        </a>
      </body>
    </html>
    '''


@app.route('/callback')
def callback():
    # Get the temporary code from GitHub
    code = request.args.get('code')
    
    if not code:
        return 'Error: No code provided', 400
    
    try:
        # Exchange the code for an access token
        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'redirect_uri': REDIRECT_URI
            },
            headers={'Accept': 'application/json'}
        )
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        scope = token_data.get('scope', '')
        
        if not access_token:
            return f'Error: Failed to get access token. Response: {token_data}', 400
        
        # Use the access token to get user information
        user_response = requests.get(
            'https://api.github.com/user',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
        )
        
        user_data = user_response.json()
        
        # Get user emails if we have the right scope
        emails = []
        if 'user:email' in scope or 'user' in scope:
            email_response = requests.get(
                'https://api.github.com/user/emails',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json'
                }
            )
            emails = email_response.json()
        
        # Build the email list HTML
        email_list_html = ''
        if emails:
            email_items = ''.join([
                f'<li>{email["email"]} {"(primary)" if email.get("primary") else ""}</li>'
                for email in emails
            ])
            email_list_html = f'''
                <p><strong>Private Emails:</strong></p>
                <ul>{email_items}</ul>
            '''
        
        # Display the user information
        return f'''
        <!DOCTYPE html>
        <html>
          <head>
            <title>GitHub OAuth - Success</title>
            <style>
              body {{
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
              }}
              .info-box {{
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 16px;
                margin: 10px 0;
              }}
              .token {{
                word-break: break-all;
                background-color: #fff;
                padding: 8px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
              }}
              img {{
                border-radius: 50%;
              }}
            </style>
          </head>
          <body>
            <h1>Authentication Successful!</h1>
            
            <div class="info-box">
              <img src="{user_data.get('avatar_url')}" width="80" height="80" alt="Avatar">
              <h2>{user_data.get('name') or user_data.get('login')}</h2>
              <p><strong>Username:</strong> {user_data.get('login')}</p>
              <p><strong>Bio:</strong> {user_data.get('bio') or 'No bio available'}</p>
              <p><strong>Public Email:</strong> {user_data.get('email') or 'Not public'}</p>
              {email_list_html}
            </div>

            <div class="info-box">
              <h3>Access Token:</h3>
              <p class="token">{access_token}</p>
              <p><strong>Granted Scopes:</strong> {scope or 'none'}</p>
            </div>

            <p><a href="/">← Back to home</a></p>
          </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <h1>Error</h1>
        <p>{str(e)}</p>
        <p><a href="/">Try again</a></p>
        ''', 500


if __name__ == '__main__':
    print(f'Server running at http://localhost:8081')
    print(f'Callback URL: {REDIRECT_URI}')
    print('\nMake sure you have set up your GitHub OAuth App with:')
    print(f'- Homepage URL: http://localhost:8081')
    print(f'- Authorization callback URL: {REDIRECT_URI}')
    app.run(debug=True, port=8081)