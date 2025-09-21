# Quick Deployment Checklist - Execute These Commands

## 🚀 IMMEDIATE ACTIONS (Run these commands in PowerShell)

### Step 1: Navigate to your project
```powershell
cd "C:\Users\Hp\OneDrive - Shri Vile Parle Kelavani Mandal\Desktop\Hackathons\Gen-AI-Exchange"
```

### Step 2: Check git status
```powershell
git status
```

### Step 3: Create and switch to Varun branch
```powershell
git checkout -b Varun
```

### Step 4: Add all changes
```powershell
git add .
```

### Step 5: Commit changes
```powershell
git commit -m "Configure frontend for production deployment with backend URL"
```

### Step 6: Push to GitHub
```powershell
git push origin Varun
```

## 📋 RENDER DEPLOYMENT SETTINGS

### Repository Configuration:
- **Repository**: `WinterBlossom0/Gen-AI-Exchange`
- **Branch**: `Varun` ⚠️ **CRITICAL: Select Varun branch**
- **Root Directory**: `frontend`

### Build Configuration:
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

### Environment Variables:
- **Key**: `VITE_API_URL`
- **Value**: `https://gen-ai-exchange-backend.onrender.com`

## 🔗 RENDER SETUP STEPS

1. **Go to**: [render.com](https://render.com)
2. **Login** with your GitHub account
3. **Click**: "New +" → "Static Site"
4. **Select**: Your `Gen-AI-Exchange` repository
5. **Choose Branch**: `Varun` (NOT main)
6. **Set Root Directory**: `frontend`
7. **Set Build Command**: `npm install && npm run build`
8. **Set Publish Directory**: `dist`
9. **Add Environment Variable**: 
   - Name: `VITE_API_URL`
   - Value: `https://gen-ai-exchange-backend.onrender.com`
10. **Click**: "Create Static Site"

## ✅ VERIFICATION

After deployment, test:
- [ ] Frontend loads at your Render URL
- [ ] File upload works
- [ ] Backend connection successful
- [ ] Contract analysis functions properly

## 🆘 IF YOU ENCOUNTER ISSUES

### Build Fails?
- Check Render build logs
- Ensure package.json is in frontend directory
- Verify Node.js compatibility

### Backend Connection Fails?
- Verify environment variable is set correctly
- Check if backend is responsive
- Ensure CORS is configured

Your frontend will be deployed and fully functional! 🎉