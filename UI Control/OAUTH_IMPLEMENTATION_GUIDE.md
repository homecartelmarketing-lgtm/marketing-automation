# OAuth 2.0 Implementation Guide for Social Media Platforms

This guide explains how to implement real OAuth authentication for each social media platform.

## Overview

The app now uses OAuth 2.0 simulation. To implement real OAuth, you'll need to:

1. Register your app with each platform
2. Get API credentials (Client ID & Client Secret)
3. Set up OAuth redirect URLs
4. Implement backend token exchange
5. Store tokens securely

---

## 1. Instagram (Meta/Facebook Platform)

### Registration
1. Go to https://developers.facebook.com/
2. Create a new app and add Instagram Basic Display or Instagram Graph API
3. Get your App ID and App Secret

### OAuth Flow
```javascript
// Step 1: Redirect to authorization URL
const authUrl = `https://api.instagram.com/oauth/authorize?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=user_profile,user_media&response_type=code`;
window.location.href = authUrl;

// Step 2: Handle callback and exchange code for token
const response = await fetch('https://api.instagram.com/oauth/access_token', {
  method: 'POST',
  body: new URLSearchParams({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    grant_type: 'authorization_code',
    redirect_uri: REDIRECT_URI,
    code: authorizationCode
  })
});

const { access_token, user_id } = await response.json();
```

### Required Scopes
- `user_profile` - Read profile info
- `user_media` - Access posts and media
- `instagram_content_publish` - Post on behalf of user

---

## 2. TikTok

### Registration
1. Go to https://developers.tiktok.com/
2. Create a new app
3. Enable "Login Kit" and "Content Posting API"

### OAuth Flow
```javascript
// Step 1: Authorization URL
const authUrl = `https://www.tiktok.com/v2/auth/authorize/?client_key=${CLIENT_KEY}&scope=user.info.basic,video.list,video.upload&response_type=code&redirect_uri=${REDIRECT_URI}`;

// Step 2: Token exchange
const response = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: new URLSearchParams({
    client_key: CLIENT_KEY,
    client_secret: CLIENT_SECRET,
    code: authorizationCode,
    grant_type: 'authorization_code',
    redirect_uri: REDIRECT_URI
  })
});
```

### Required Scopes
- `user.info.basic` - User profile
- `video.list` - Access videos
- `video.upload` - Upload videos
- `video.publish` - Publish videos

---

## 3. Twitter (X)

### Registration
1. Go to https://developer.twitter.com/
2. Create a project and app
3. Enable OAuth 2.0 and get Client ID

### OAuth Flow
```javascript
// Twitter uses PKCE for OAuth 2.0
// Step 1: Generate code challenge
const codeVerifier = generateRandomString();
const codeChallenge = await sha256(codeVerifier);

// Step 2: Authorization URL
const authUrl = `https://twitter.com/i/oauth2/authorize?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=tweet.read%20tweet.write%20users.read&state=${STATE}&code_challenge=${codeChallenge}&code_challenge_method=S256`;

// Step 3: Token exchange
const response = await fetch('https://api.twitter.com/2/oauth2/token', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: new URLSearchParams({
    code: authorizationCode,
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    code_verifier: codeVerifier
  })
});
```

### Required Scopes
- `tweet.read` - Read tweets
- `tweet.write` - Post tweets
- `users.read` - Read user profile
- `offline.access` - Refresh tokens

---

## 4. Facebook

### Registration
1. Go to https://developers.facebook.com/
2. Create app and add Facebook Login
3. Configure OAuth redirect URIs

### OAuth Flow
```javascript
// Step 1: Authorization URL
const authUrl = `https://www.facebook.com/v18.0/dialog/oauth?client_id=${APP_ID}&redirect_uri=${REDIRECT_URI}&scope=pages_manage_posts,pages_read_engagement,pages_show_list&response_type=code`;

// Step 2: Exchange code for token
const response = await fetch(
  `https://graph.facebook.com/v18.0/oauth/access_token?client_id=${APP_ID}&redirect_uri=${REDIRECT_URI}&client_secret=${APP_SECRET}&code=${code}`
);

const { access_token } = await response.json();
```

### Required Scopes
- `pages_manage_posts` - Publish posts
- `pages_read_engagement` - Read insights
- `pages_show_list` - List pages
- `publish_to_groups` - Post to groups (optional)

---

## 5. LinkedIn

### Registration
1. Go to https://www.linkedin.com/developers/
2. Create an app
3. Request access to necessary APIs

### OAuth Flow
```javascript
// Step 1: Authorization URL
const authUrl = `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=w_member_social%20r_liteprofile%20r_organization_social`;

// Step 2: Token exchange
const response = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: new URLSearchParams({
    grant_type: 'authorization_code',
    code: authorizationCode,
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    redirect_uri: REDIRECT_URI
  })
});
```

### Required Scopes
- `r_liteprofile` - Read profile
- `w_member_social` - Post on behalf of user
- `r_organization_social` - Read company pages
- `w_organization_social` - Post to company pages

---

## Backend Implementation (Required)

**CRITICAL:** OAuth token exchange MUST happen on your backend, never expose Client Secrets in frontend code.

### Example Express.js Backend

```javascript
// backend/routes/oauth.js
const express = require('express');
const router = express.Router();

router.get('/auth/:platform', (req, res) => {
  const { platform } = req.params;
  // Redirect to platform's OAuth URL
  const authUrl = getAuthUrl(platform);
  res.redirect(authUrl);
});

router.get('/callback/:platform', async (req, res) => {
  const { platform } = req.params;
  const { code } = req.query;
  
  try {
    // Exchange code for tokens on backend
    const tokens = await exchangeCodeForTokens(platform, code);
    
    // Store tokens securely (encrypted in database)
    await storeTokens(req.user.id, platform, tokens);
    
    // Redirect back to frontend
    res.redirect('/app?auth=success');
  } catch (error) {
    res.redirect('/app?auth=error');
  }
});

module.exports = router;
```

---

## Security Best Practices

1. **Never store tokens in localStorage** - Use httpOnly cookies or secure backend storage
2. **Encrypt tokens at rest** - Use encryption before storing in database
3. **Implement token rotation** - Use refresh tokens to get new access tokens
4. **Use HTTPS only** - All OAuth redirects must use HTTPS in production
5. **Validate state parameter** - Prevent CSRF attacks
6. **Handle token expiration** - Implement automatic refresh logic
7. **Rate limiting** - Implement rate limits on your OAuth endpoints
8. **Scope minimization** - Only request necessary permissions

---

## Token Storage Schema

```sql
CREATE TABLE oauth_tokens (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  platform VARCHAR(50) NOT NULL,
  access_token_encrypted TEXT NOT NULL,
  refresh_token_encrypted TEXT,
  token_expiry TIMESTAMP,
  scope TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, platform)
);
```

---

## Environment Variables

Create a `.env` file:

```env
# Instagram
INSTAGRAM_CLIENT_ID=your_app_id
INSTAGRAM_CLIENT_SECRET=your_app_secret

# TikTok
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret

# Twitter
TWITTER_CLIENT_ID=your_client_id
TWITTER_CLIENT_SECRET=your_client_secret

# Facebook
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret

# LinkedIn
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret

# OAuth
OAUTH_REDIRECT_URI=https://yourdomain.com/api/oauth/callback
ENCRYPTION_KEY=your_encryption_key_32_chars
```

---

## Testing OAuth Locally

1. Use ngrok to create HTTPS tunnel: `ngrok http 3000`
2. Update redirect URIs in each platform's developer console
3. Test OAuth flow with the ngrok URL
4. Check tokens are stored correctly
5. Test token refresh logic

---

## Additional Resources

- **Instagram**: https://developers.facebook.com/docs/instagram-api
- **TikTok**: https://developers.tiktok.com/doc/login-kit-web
- **Twitter**: https://developer.twitter.com/en/docs/authentication/oauth-2-0
- **Facebook**: https://developers.facebook.com/docs/facebook-login
- **LinkedIn**: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication

---

## Current Implementation

The current app uses a **simulation** of OAuth that:
- Shows the proper OAuth UI flow
- Demonstrates permission requests
- Generates mock tokens for testing
- Displays how tokens would be stored

To go live, implement the real OAuth flows described above with proper backend infrastructure.
