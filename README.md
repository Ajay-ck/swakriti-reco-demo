# Swakriti backend demo - Railway

## Deploy
1. In Railway, create a project from this GitHub repository.
2. Leave Root Directory at the repository root. Railway detects Dockerfile.
   No custom build/start command is required.
3. Add Variables using .env.example. Copy GOOGLE_API_KEY and GEMINI_API_KEY
   (same Google key), QDRANT_URL and QDRANT_API_KEY from your local backend/.env.
   Use your working GEMINI_EXTRACTION_MODEL if it differs from the example.
4. Deploy. First build installs dependencies and downloads embedding models.
5. Settings > Networking > Generate Domain. Share that HTTPS URL with the frontend.
6. Test /docs and / (the prompt test page) before the demo.

PORT is supplied by Railway; the server listens on 0.0.0.0 with one worker.
Start with enough memory for local ONNX embeddings (2 GB is a conservative
starting allocation, not a measured requirement). Docker uses Linux, so Windows
Visual C++ redistributables are not required. No frontend build is included.

Existing nonempty Qdrant collection skus is reused. Do not reset/rebuild it merely
to deploy. CSV changes require explicit reindexing. Allow Railway traffic if
Qdrant IP restrictions are enabled.

DISABLE_ERP_WEBHOOK=true disables an otherwise unauthenticated index-mutation
route for this CSV demo. Keep it enabled. API keys must never go into the frontend.

## Frontend handoff
Use the Railway domain as the API base URL. Existing routes:
POST /parse-answer, POST /recommend, POST /recommend-text,
POST /live-token, POST /tts. Interactive contracts: /docs.
POST /recommend-text accepts:
{"prompt":"I want a women's black cotton A-line dress, size M, under Rs 1500 for everyday wear."}

Preserve recommendation order (or rank); final_score is now 0-100, not a match
probability. Earlier ranking work changed extracted_tags and removed older
individual score breakdown fields in favor of component/attribute scores.
Handle HTTP 422 clarification responses and API errors. Compatibility with an
external frontend must be verified with its actual requests and field usage.
Deployment changes do not alter ranking or recommendation response schemas.
CORS currently allows cross-origin requests without cookie credentials.

## Images
metadata["Image URL"] uses a Google image URL without a size suffix.
The optional /product-image/{file_id} test-page proxy no longer requests =w400.
It passes upstream bytes unchanged: no Python resizing/re-encoding/compression.
Google controls the upstream representation; original upload bytes are not
guaranteed. Images above 10 MB are rejected rather than compressed.
Google Drive images must be publicly accessible. Clear old thumbnail browser caches.

## Verification and limitations
/ ranking-policy (without the space) is the startup health check; it does not test
Gemini availability. Run an actual recommendation from /docs after deployment.
Previous broad evaluation found Gemini quota/provider failures and some
false-empty recommendations; hosting does not resolve those. Ensure adequate
Google API quota for the client demo.

Secrets, virtual environments, frontend sources and evaluation outputs are excluded.
The Docker build must be verified in Railway; Docker is unavailable locally.
