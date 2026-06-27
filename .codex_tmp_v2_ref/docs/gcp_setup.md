# GCP Setup For BARD

These steps are written for Windows PowerShell and the current repo structure.

For the current complete `run-fragments` pipeline, Processing replay, image-provider commands, and
parameter effects, use [running_the_pipeline.md](running_the_pipeline.md). `run-local` examples in
this setup document describe the older prototype path.

Assumed local folder layout:

```text
<workspace>/
  BARD-CPAC-2026/
  Project/
    secrets/
```

`BARD-CPAC-2026` is the git repo. `Project/secrets` is private and must not be committed.

## 0. Terminal Rules

Use Windows PowerShell first, not the VS Code terminal, while installing tools.

After installing Python or Google Cloud CLI, close every VS Code window and open it again. VS Code terminals inherit the environment variables that existed when VS Code started, so an old VS Code window may not see `python` or `gcloud` even when normal PowerShell can.

To reopen the repo from a fresh PowerShell:

```powershell
cd "<workspace>\BARD-CPAC-2026"
code .
```

If `code .` is not recognized, open VS Code manually, then use `File > Open Folder...`.

## 1. Install Local Tools

Install:

- Python 3.12+
- Docker Desktop
- Google Cloud CLI

Recommended Windows downloads:

- Python: https://www.python.org/downloads/windows/
- Google Cloud CLI: https://cloud.google.com/sdk/docs/install
- Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/

You can also download Python and Google Cloud CLI installers from PowerShell:

```powershell
$Downloads="$env:USERPROFILE\Downloads"

# Python 3.12.10 64-bit installer. During install, select "Add python.exe to PATH".
(New-Object Net.WebClient).DownloadFile(
  "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe",
  "$Downloads\python-3.12.10-amd64.exe"
)
Start-Process "$Downloads\python-3.12.10-amd64.exe"

# Google Cloud CLI installer.
(New-Object Net.WebClient).DownloadFile(
  "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe",
  "$Downloads\GoogleCloudSDKInstaller.exe"
)
Start-Process "$Downloads\GoogleCloudSDKInstaller.exe"
```

For Docker, download and install Docker Desktop from the official Docker page above. After installation, start Docker Desktop once and accept the prompt.

Then restart PowerShell and check:

```powershell
gcloud --version
docker --version
python --version
py --list
```

Expected:

- `gcloud --version` prints the Google Cloud SDK version.
- `docker --version` prints Docker version.
- `python --version` prints Python 3.12.x or newer.
- `py --list` shows at least one Python version.

If these commands work in normal PowerShell but not inside VS Code, fully close VS Code and reopen it from a fresh PowerShell with `code .`.

If `python --version` opens the Microsoft Store or says Python was not found, disable the Microsoft Store aliases:

```text
Windows Settings > Apps > Advanced app settings > App execution aliases
```

Turn off:

```text
python.exe
python3.exe
```

Then reopen PowerShell and test again.

## 2. GCP Project Strategy

Recommended team strategy:

- One team member creates and deploys the shared GCP project.
- Other team members are added to the same GCP project with IAM access.
- Each teammate keeps their own private local env file in their own `Project/secrets` folder.

The owner can add teammates in:

```text
Google Cloud Console > IAM & Admin > IAM > Grant access
```

For local development, teammates usually need:

```text
Vertex AI User
Storage Object Admin
Cloud Run Developer
Artifact Registry Writer
Service Account User
```

For the first project setup, the owner should use Owner permissions, then reduce permissions later if needed.

## 3. Create Or Select The Shared GCP Project

If you already created the project in the GCP web console, set `$PROJECT_ID` to that existing id and skip the `gcloud projects create` line. Anything you create with these commands will also appear in the GCP web console.

If Google Cloud CLI opens `gcloud init` and asks:

```text
Pick cloud project to use:
 [1] existing-project
 [8] Enter a project ID
 [9] Create a new project
```

Choose one of these:

- Choose `[9] Create a new project` if you want a clean BARD project.
- Choose an existing project number if the shared project already exists.
- Choose `[8] Enter a project ID` if the project exists but is not listed.

Set variables for the shared project:

```powershell
$PROJECT_ID="your-shared-gcp-project-id"
$REGION="europe-west1"
gcloud auth login
gcloud config set project $PROJECT_ID
```

Only if the project does not exist yet:

```powershell
gcloud projects create $PROJECT_ID
gcloud config set project $PROJECT_ID
```

Enable billing manually in the Google Cloud Console if it is not already enabled:

```text
https://console.cloud.google.com/billing
```

Most API-enable and deploy commands will fail until billing is active.

## 4. Enable APIs

```powershell
gcloud services enable aiplatform.googleapis.com
gcloud services enable generativelanguage.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudtasks.googleapis.com
```

For the first deployable version, only Vertex AI, Cloud Run, Cloud Build, and Artifact Registry are essential. Pub/Sub and Cloud Tasks are for the async architecture that follows.

For Gemini image generation, also verify access in the Google Cloud Console:

1. Open Vertex AI, Agent Studio, or Model Garden for the selected project.
2. Search for the selected image model, usually `gemini-2.5-flash-image`.
3. Confirm the model is available in the project and location, usually `global`.
4. Run a simple console prompt with image output enabled.
5. If you choose a newer Gemini image model, test that exact model in the console first.

## 5. Create Runtime Service Account And Bucket

```powershell
$SA_NAME="bard-runtime"
$SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud iam service-accounts create $SA_NAME --display-name "BARD runtime"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member "serviceAccount:$SA_EMAIL" `
  --role "roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member "serviceAccount:$SA_EMAIL" `
  --role "roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member "serviceAccount:$SA_EMAIL" `
  --role "roles/storage.objectAdmin"
```

Create an artifact bucket for generated JSON and later image/video files:

```powershell
$BUCKET="$PROJECT_ID-bard-artifacts"
gcloud storage buckets create "gs://$BUCKET" --location=$REGION
```

If the service account or bucket already exists, continue with the next step.

## 6. Local Authentication

For local development, prefer Application Default Credentials:

```powershell
gcloud auth application-default login
```

Avoid JSON service account keys unless absolutely needed. Cloud Run should use its attached service account, not a JSON key.

If a JSON key is required for a specific local machine, keep it outside the repo:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$SECRET_DIR=Join-Path $WORKSPACE "Project\secrets"
New-Item -ItemType Directory -Force -Path $SECRET_DIR
gcloud iam service-accounts keys create "$SECRET_DIR\bard-gcp-key.json" --iam-account $SA_EMAIL
```

Never commit that JSON key.

## 7. Local Python Setup

From the repo root:

```powershell
cd "<workspace>\BARD-CPAC-2026"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[api,cloud]"
```

If `py` is not available, install Python and use `python -m venv .venv` instead.

Use `local-ai` later only if you want to run CLAP/Mistral on your machine:

```powershell
python -m pip install -e ".[local-ai]"
```

If the virtual environment gets confused after Python reinstall and you see `Unable to create process`, recreate it:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[api,cloud]"
```

## 8. Create Private Local Env File

Copy the template:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$SECRET_DIR=Join-Path $WORKSPACE "Project\secrets"
New-Item -ItemType Directory -Force -Path $SECRET_DIR
Copy-Item configs\local.example.env "$SECRET_DIR\bard-local.env"
notepad "$SECRET_DIR\bard-local.env"
```

Edit these values:

```env
BARD_GCP_PROJECT_ID=your-shared-gcp-project-id
GOOGLE_CLOUD_PROJECT=your-shared-gcp-project-id
BARD_GCP_LOCATION=global
GOOGLE_CLOUD_LOCATION=global
BARD_STORAGE_BUCKET=your-shared-gcp-project-id-bard-artifacts
BARD_IMAGE_PROVIDER=imagen
BARD_IMAGE_MODEL=gemini-2.5-flash-image
BARD_IMAGE_LOCATION=global
BARD_REMOVE_IMAGE_BACKGROUND=true
BARD_BACKGROUND_REMOVAL_PROVIDER=rembg
```

Usually leave this commented because local development uses `gcloud auth application-default login`:

```env
# GOOGLE_APPLICATION_CREDENTIALS=...
```

Old image env names are still accepted for backwards compatibility, but prefer the new names:

```env
# BARD_IMAGEN_MODEL=gemini-2.5-flash-image
# BARD_IMAGEN_LOCATION=global
```

Authentication options:

- Option A: run `gcloud auth application-default login` locally and mount ADC into Docker when needed.
- Option B: use a service account JSON key through `GOOGLE_APPLICATION_CREDENTIALS` for local development only when appropriate.

Never commit credentials or copy them into the Docker image.

## 9. Optional Hugging Face Token For Local Models

You do not need a Hugging Face token for the recommended GCP/Vertex path.

You may need or want one for the local path:

```powershell
python -m bard_core run-local --audio data/audio/audio.mp3 --audio-provider clap --story-provider local
```

Why:

- CLAP downloads from Hugging Face and can work without a token, but a token gives better rate limits.
- Mistral models may require accepting model terms on Hugging Face and using a token.

Steps:

1. Create/login to a Hugging Face account.
2. Open https://huggingface.co/settings/tokens
3. Create a token with read access.
4. Add it to your private `bard-local.env`:

```env
HF_TOKEN=paste-your-token-here
```

Optional persistent login:

```powershell
huggingface-cli login
```

Never commit the token to the repo.

## 10. Optional Local GPU Setup

This project does not require local GPU for the recommended GCP/Vertex path.

Local GPU is only useful for:

```powershell
python -m bard_core run-local --audio data/audio/audio.mp3 --audio-provider clap --story-provider local
```

That path runs CLAP and Mistral on your laptop. It needs an NVIDIA CUDA GPU and a CUDA-enabled PyTorch build. If PyTorch cannot see CUDA, it will use CPU and can sit at 95-100% CPU for a long time.

Check whether PyTorch sees the GPU:

```powershell
python -c "import torch; print('torch', torch.__version__); print('cuda build', torch.version.cuda); print('cuda available', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda device')"
```

If `cuda available` is `False`, reinstall PyTorch with CUDA support:

```powershell
python -m pip uninstall -y torch torchvision torchaudio
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Then verify again:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda device')"
```

8GB VRAM may still be tight for Mistral 7B, so the recommended project path remains Vertex AI.

## 11. Run The Pipeline Locally

Recommended first smoke test, using GCP/Vertex AI and no Processing:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --out-dir runs\gcp-smoke-test
```

This should create a new folder under `runs/` with:

```text
result.json
music_segments.json
story.json
full_story.txt
```

If you see this error on a brand-new project:

```text
Service agents are being provisioned. Service agents are needed to read the Cloud Storage file provided.
```

Wait a few minutes and run the command again.

Processing/OSC path, only after opening `apps/processing/bard_story_visuals` in Processing:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider openverse `
  --send-osc `
  --out-dir runs\gcp-processing-test
```

Prototype-compatible path, using local CLAP and local Mistral:

```powershell
python -m pip install -e ".[local-ai]"
python -m bard_core --env-file "$ENV_FILE" run-local --audio data/audio/audio.mp3 --audio-provider clap --story-provider local
```

## 12. Build And Deploy To Cloud Run

Set variables:

```powershell
$PROJECT_ID="your-shared-gcp-project-id"
$REGION="europe-west1"
$MODEL_LOCATION="global"
$SA_NAME="bard-runtime"
$SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$BUCKET="$PROJECT_ID-bard-artifacts"
gcloud config set project $PROJECT_ID
```

Create an Artifact Registry repository:

```powershell
gcloud artifacts repositories create bard-containers `
  --repository-format=docker `
  --location=$REGION `
  --description="BARD containers"
```

If it already exists, continue.

Build and push:

```powershell
$IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/bard-containers/bard-api:dev"
gcloud builds submit --tag $IMAGE
```

Deploy:

```powershell
gcloud run deploy bard-api `
  --image $IMAGE `
  --region $REGION `
  --service-account $SA_EMAIL `
  --allow-unauthenticated `
  --set-env-vars "BARD_AUDIO_PROVIDER=gemini,BARD_STORY_PROVIDER=vertex,BARD_GCP_PROJECT_ID=$PROJECT_ID,BARD_GCP_LOCATION=$MODEL_LOCATION,BARD_STORAGE_BUCKET=$BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$MODEL_LOCATION,BARD_IMAGE_PROVIDER=imagen,BARD_IMAGE_MODEL=gemini-2.5-flash-image,BARD_IMAGE_LOCATION=global,BARD_REMOVE_IMAGE_BACKGROUND=true,BARD_BACKGROUND_REMOVAL_PROVIDER=rembg,GOOGLE_GENAI_USE_ENTERPRISE=true"
```

For public demos, `--allow-unauthenticated` is convenient. For a real performance installation, use authenticated access.

## 13. Call The Cloud Run API

Get the URL:

```powershell
$SERVICE_URL=(gcloud run services describe bard-api --region $REGION --format "value(status.url)")
```

Upload an audio file:

```powershell
curl.exe -X POST "$SERVICE_URL/runs/sync?audio_provider=gemini&story_provider=vertex" `
  -F "audio=@data/audio/audio.mp3"
```

The response contains `music_segments`, `fragments`, `full_story`, and future visual prompt fields.

After this works, also test the local orchestrator against Vertex AI:

```powershell
$WORKSPACE=(Resolve-Path ..).Path
$ENV_FILE=Join-Path $WORKSPACE "Project\secrets\bard-local.env"

python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --out-dir runs\vertex-orchestrator-test
```

Then, with Processing open, test the live OSC bridge:

```powershell
python -m bard_core --env-file "$ENV_FILE" run-fragments `
  --audio data\test_audio\arabesque.mp3 `
  --generate-images `
  --image-provider openverse `
  --send-osc `
  --out-dir runs\vertex-processing-test
```

## Notes On Secrets

- `configs/local.example.env` is the template for each teammate's private laptop env file.
- `deploy/cloud-run.env.example` is the template for deployed Cloud Run settings later.
- Each teammate's actual local file should live outside the repo in their own `Project/secrets/bard-local.env`.
- Local JSON keys stay outside this repo.
- Cloud Run should use its attached service account, not a JSON key.
- Later API keys, if any, should go into Secret Manager and be mounted/injected into Cloud Run.
