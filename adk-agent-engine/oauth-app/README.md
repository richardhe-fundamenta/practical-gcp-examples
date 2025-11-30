# GitHub OAuth Demo App

A simple Python Flask application demonstrating GitHub OAuth authentication flow.

## Setup Instructions

### 1. Register a GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the details:
   - **Application name**: `My OAuth Test App` (or whatever you prefer)
   - **Homepage URL**: `http://localhost:5000`
   - **Authorization callback URL**: `http://localhost:5000/callback`
4. Click "Register application"
5. Copy your **Client ID** and generate a **Client Secret**

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```
   GITHUB_CLIENT_ID=your_actual_client_id
   GITHUB_CLIENT_SECRET=your_actual_client_secret
   ```

### 4. Run the Application

```bash
python server.py
```

The server will start at `http://localhost:5000`

### 5. Test the OAuth Flow

1. Open your browser and go to `http://localhost:5000`
2. Click "Sign in with GitHub"
3. Authorize the application
4. You'll be redirected back to the callback URL with your user information

## How It Works

1. **Authorization Request**: User clicks the login button, which redirects to GitHub's OAuth authorization page
2. **User Authorization**: User approves the app's access request
3. **Callback**: GitHub redirects back to `http://localhost:5000/callback` with a temporary code
4. **Token Exchange**: The app exchanges the code for an access token by making a POST request to GitHub
5. **API Requests**: The app uses the access token to fetch user information from the GitHub API

## Files

- `server.py` - Main Flask server with OAuth logic
- `requirements.txt` - Python dependencies
- `.env.example` - Template for environment variables
- `.env` - Your actual credentials (not included, you create this)

## Security Notes

- Never commit your `.env` file to version control
- The client secret should be kept secure
- This is a demo app - for production, you'd want to:
  - Store tokens securely (database, encrypted sessions)
  - Add CSRF protection
  - Use HTTPS
  - Implement proper error handling
  - Add token refresh logic

## Scopes

The app requests `user:email` scope which allows reading:
- User profile information
- User email addresses (both public and private)

You can modify the scope in `server.py` to request different permissions.
