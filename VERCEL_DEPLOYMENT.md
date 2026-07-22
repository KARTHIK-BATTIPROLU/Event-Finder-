# Deploying EventRadar to Vercel 🚀

This repository is pre-configured for seamless deployment to **Vercel** as a Python Serverless application.

---

## 📋 Prerequisites

1. A free **MongoDB Atlas M0 Cluster** (or any cloud MongoDB instance).
   - Get connection string from [MongoDB Atlas](https://cloud.mongodb.com) → Connect → Drivers → Python.
2. A free **Vercel Account** ([vercel.com](https://vercel.com)).

---

## ⚡ Option A: Deploy via Vercel CLI (Recommended)

Run the following command from the project root:

```bash
npx vercel
```

Follow the interactive prompts:
- **Set up and deploy?** → `Y`
- **Which scope?** → Select your account
- **Link to existing project?** → `N`
- **What's your project's name?** → `eventradar`
- **In which directory is your code located?** → `./`
- **Want to modify build settings?** → `N`

After initial deployment, add your **`MONGO_URI`** environment variable:

```bash
npx vercel env add MONGO_URI
```
- Paste your MongoDB Atlas URI when prompted (e.g. `mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority`).
- Select environments: **Production**, **Preview**, **Development**.

Deploy to production:

```bash
npx vercel --prod
```

---

## 🌐 Option B: Deploy via GitHub / Vercel Dashboard

1. Push this project to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repository.
3. Under **Environment Variables**, add:
   - `MONGO_URI`: `mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`
   - *(Optional)* `EVENTBRITE_TOKEN`, `MEETUP_TOKEN`, `LUMA_API_KEY`
4. Click **Deploy**.

Vercel will automatically detect `vercel.json` and deploy `server.py` as a Python Serverless Function!

---

## 📁 Key Vercel Configuration Files Created

- **`vercel.json`**: Directs all incoming traffic to `server.py` using the `@vercel/python` serverless builder.
- **`requirements.txt`**: Includes `Flask`, `requests`, `beautifulsoup4`, `pymongo`, and `python-dotenv`.
- **`.vercelignore`**: Excludes `.env`, virtual environments, and temporary logs from build uploads.
