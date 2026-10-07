# Deploy and test on a phone

## Fastest: static hosting (works offline)
1. Push this repo to GitHub. Settings → Pages → deploy from branch, folder `/web`
   (or drag the `web/` folder onto Netlify).
2. Open the https URL on your phone. Android Chrome: menu → *Install app*. iPhone Safari: Share → *Add to Home Screen*.
3. Turn on airplane mode and open it again. It should still load. (Not yet tried on a real phone: please tell me what you see.)

## With Smart mode on Render
1. New → Blueprint → pick the repo (`render.yaml`). Free plan sleeps when idle; first request may take ~1 min, and the app falls back to offline meanwhile.
2. Open `https://<name>.onrender.com`: it serves the app and the API from one address.
3. In the app: Settings → Smart-mode server address → paste your Render URL (even when you opened the app from that same URL).
4. For TabPFN: set build command to `pip install -r requirements.txt -r requirements-tabpfn.txt`. TabPFN is heavy; the free plan likely lacks memory. Run it on a bigger instance or your own machine and compare with `python -m grassy.server`.
5. Gemma: run Ollama somewhere reachable, then set `GRASSY_BASE_URL=http://host:11434/v1` and `GRASSY_MODEL=gemma3`.
