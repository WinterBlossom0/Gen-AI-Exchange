# Step-by-Step Guide: Deploy Frontend on Render (Branch: Varun)

## Prerequisites ✅
- Your backend is already deployed at: `https://gen-ai-exchange-backend.onrender.com/`
- Frontend is configured to connect to the production backend
- You have a GitHub account and Git installed

## Step 1: Create and Push the "Varun" Branch

### 1.1 Create the new branch
```bash
# Navigate to your project root
cd "C:\Users\Hp\OneDrive - Shri Vile Parle Kelavani Mandal\Desktop\Hackathons\Gen-AI-Exchange"

# Create and switch to the new branch
git checkout -b Varun

# Verify you're on the new branch
git branch
```

### 1.2 Add and commit your changes
```bash
# Add all files to staging
git add .

# Commit the changes
git commit -m "Configure frontend for production deployment with backend URL"

# Push the branch to GitHub
git push origin Varun
```

## Step 2: Prepare Render-Specific Configuration

### 2.1 Create a Render build script (if needed)
Create `frontend/render-build.sh`:
```bash
#!/bin/bash
cd frontend
npm install
npm run build
```

### 2.2 Verify your frontend structure
Make sure your frontend directory has:
- ✅ `package.json` with build script
- ✅ `.env.production` with backend URL
- ✅ Source code in `src/` directory

## Step 3: Deploy on Render

### 3.1 Sign up/Login to Render
1. Go to [render.com](https://render.com)
2. Sign up or login with your GitHub account
3. Grant Render access to your repositories

### 3.2 Create a New Static Site
1. Click **"New +"** button in your Render dashboard
2. Select **"Static Site"**
3. Connect your GitHub repository: `Gen-AI-Exchange`

### 3.3 Configure the Static Site Settings

#### Repository Settings:
- **Repository**: `WinterBlossom0/Gen-AI-Exchange`
- **Branch**: `Varun` ⚠️ **IMPORTANT: Select the Varun branch**

#### Build Settings:
- **Root Directory**: `frontend`
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

#### Environment Variables:
- **Variable Name**: `VITE_API_URL`
- **Value**: `https://gen-ai-exchange-backend.onrender.com`

### 3.4 Advanced Settings (Optional)
- **Auto-Deploy**: `Yes` (deploys automatically on git push)
- **Pull Request Previews**: `No` (unless you want preview deployments)

## Step 4: Deploy and Verify

### 4.1 Start Deployment
1. Click **"Create Static Site"**
2. Render will start building your frontend
3. Monitor the build logs for any errors

### 4.2 Build Process (What Render Does)
```
1. Clones your repository (Varun branch)
2. Navigates to frontend/ directory
3. Runs: npm install
4. Runs: npm run build
5. Serves files from dist/ directory
```

### 4.3 Deployment URL
Once deployed, you'll get a URL like:
`https://your-site-name.onrender.com`

## Step 5: Test Your Deployed Frontend

### 5.1 Verify Backend Connection
1. Open your deployed frontend URL
2. Try uploading a test PDF contract
3. Verify the analysis works (connects to your backend)

### 5.2 Check Browser Console
1. Open browser developer tools (F12)
2. Look for any API connection errors
3. Verify requests go to: `https://gen-ai-exchange-backend.onrender.com`

## Step 6: Custom Domain (Optional)

### 6.1 Add Custom Domain
1. In Render dashboard, go to your static site
2. Click on **"Settings"**
3. Scroll to **"Custom Domains"**
4. Add your domain (if you have one)

## Troubleshooting Common Issues

### Issue 1: Build Fails
**Solution**: Check build logs and ensure:
- Node.js version compatibility
- All dependencies are in package.json
- Build command is correct

### Issue 2: Backend Connection Fails
**Solution**: Verify:
- Environment variable `VITE_API_URL` is set correctly
- Backend URL is accessible
- CORS is configured on backend

### Issue 3: 404 Errors on Routes
**Solution**: Add `_redirects` file in `frontend/public/`:
```
/*    /index.html   200
```

## Complete Command Summary

Here are all the Git commands you need to run:

```bash
# Navigate to project directory
cd "C:\Users\Hp\OneDrive - Shri Vile Parle Kelavani Mandal\Desktop\Hackathons\Gen-AI-Exchange"

# Create and switch to Varun branch
git checkout -b Varun

# Add all changes
git add .

# Commit changes
git commit -m "Configure frontend for production deployment"

# Push to GitHub
git push origin Varun
```

## Final Checklist ✅

Before deploying, ensure:
- [ ] Varun branch is created and pushed to GitHub
- [ ] Frontend `.env.production` has correct backend URL
- [ ] Backend is working at `https://gen-ai-exchange-backend.onrender.com/`
- [ ] Repository is connected to Render
- [ ] Build settings are configured correctly
- [ ] Environment variables are set in Render

## Expected Result

After successful deployment:
- ✅ Frontend accessible at: `https://your-site-name.onrender.com`
- ✅ Connects to backend: `https://gen-ai-exchange-backend.onrender.com`
- ✅ Full contract analysis functionality works
- ✅ Auto-deploys on future pushes to Varun branch

Your Contract Analyzer web app will be fully functional and accessible from anywhere on the internet! 🚀