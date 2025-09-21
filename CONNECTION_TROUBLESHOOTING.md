# 🚨 FRONTEND-BACKEND CONNECTION TROUBLESHOOTING

## Problem Identified
Your frontend at `gen-ai-exchange-legal-agent.onrender.com` cannot connect to your backend at `https://gen-ai-exchange-backend.onrender.com/`

## 🔍 DIAGNOSTIC STEPS

### Step 1: Check Backend Status
Run this command to verify backend is working:
```bash
curl -X GET "https://gen-ai-exchange-backend.onrender.com/health"
```
Expected response: `{"status": "ok"}`

### Step 2: Check CORS Configuration
The most likely issue is **CORS (Cross-Origin Resource Sharing)**. Your backend needs to allow requests from your frontend domain.

## 🛠️ SOLUTIONS

### Solution 1: Update Backend CORS Settings
Your backend CORS configuration needs to include your frontend domain:

**In your backend `main.py`, update the CORS origins:**
```python
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    # ADD YOUR FRONTEND DOMAIN HERE
    "https://gen-ai-exchange-legal-agent.onrender.com",
    "https://*.onrender.com",  # Allow all Render subdomains
]
```

### Solution 2: Check Environment Variables on Render
Verify that your frontend on Render has the correct environment variable:

**In Render Dashboard → Your Static Site → Environment:**
- Variable: `VITE_API_URL`
- Value: `https://gen-ai-exchange-backend.onrender.com`

### Solution 3: Verify Backend URL Format
Ensure the backend URL doesn't have trailing slashes or incorrect paths.

**Check your frontend `.env.production`:**
```
VITE_API_URL=https://gen-ai-exchange-backend.onrender.com
```
(No trailing slash!)

### Solution 4: Backend Sleep Issue
Render free tier backends go to sleep after inactivity. First request might fail.

**Solutions:**
- Wait 30-60 seconds and try again
- Implement retry logic in frontend
- Wake up backend by visiting: `https://gen-ai-exchange-backend.onrender.com/health`

## 🔧 IMMEDIATE FIXES

### Fix 1: Update Backend CORS (Recommended)
1. Go to your backend repository
2. Update the CORS origins in `backend/main.py`
3. Add your frontend domain to the allowed origins
4. Redeploy your backend

### Fix 2: Force Backend Wakeup
Visit this URL to wake up your backend:
https://gen-ai-exchange-backend.onrender.com/health

### Fix 3: Check Browser Network Tab
1. Open your frontend in browser
2. Press F12 → Network tab
3. Try uploading a file
4. Look for failed requests and error messages

## 📋 TESTING CHECKLIST

Test these URLs in browser:
- [ ] Backend health: https://gen-ai-exchange-backend.onrender.com/health
- [ ] Backend docs: https://gen-ai-exchange-backend.onrender.com/docs
- [ ] Frontend loads: https://gen-ai-exchange-legal-agent.onrender.com

## 🚀 QUICK FIX COMMAND

If backend is sleeping, wake it up:
```bash
curl "https://gen-ai-exchange-backend.onrender.com/health"
```

## 💡 PREVENTION

To prevent future sleep issues:
1. Upgrade to Render paid plan, OR
2. Set up a cron job to ping your backend every 10 minutes
3. Use a service like UptimeRobot to monitor your backend

## ⚠️ MOST LIKELY ISSUE: CORS

The error "Failed to analyze. Please check your connection" typically indicates a CORS issue. Your backend needs to explicitly allow requests from your frontend domain.

**Priority Fix: Update backend CORS configuration to include your frontend domain!**