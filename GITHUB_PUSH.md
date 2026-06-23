# Push to GitHub — Quick Steps

## 1. Create repo on GitHub.com
- Go to github.com → New Repository
- Name: `mf-analysis`  (or your choice)
- Set to Private, no README (we already have one)
- Copy the remote URL

## 2. Add remote & push
```bash
cd mf_analysis

# Replace with your actual repo URL
git remote add origin https://github.com/YOUR_USERNAME/mf-analysis.git

# Rename branch to main (recommended)
git branch -m master main

# Push
git push -u origin main
```

## 3. Verify
Your commit "Day 1: Data ingestion complete" should appear on GitHub with all 16 files.
