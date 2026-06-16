# Event-Driven Document Processing Pipeline on GCP

This project contains the complete code and infrastructure configurations to set up a serverless, event-driven document processing pipeline on Google Cloud Platform (GCP).

## Architecture

1. **Ingestion**: Users upload files to a Cloud Storage bucket.
2. **Trigger**: GCS notifications publish an `OBJECT_FINALIZE` event to a Pub/Sub topic.
3. **Processor**: A Python FastAPI service on Cloud Run is invoked by a Pub/Sub push subscription.
4. **OCR Simulation**: The processor retrieves the file from GCS, counts the words, parses keywords for metadata tags, and extracts a summary.
5. **Storage**: The processor streams the metadata into a BigQuery table.

---

## Directory Structure

```
.
├── README.md               # This project documentation
├── processor/              # Python FastAPI Application
│   ├── Dockerfile          # Container config for Cloud Run
│   ├── main.py             # Service logic (GCS download, OCR, BQ stream)
│   ├── requirements.txt    # Python dependencies
│   └── test_local.py       # Offline unit tests using FastAPI TestClient
└── terraform/              # Terraform Infrastructure-as-Code
    ├── main.tf             # Core GCP resource declarations
    ├── outputs.tf          # Deployment outputs
    └── variables.tf        # Input variables
```

---

## Deployment Instructions

### Prerequisites
1. [Terraform CLI](https://developer.hashicorp.com/terraform/downloads) installed locally.
2. [gcloud CLI](https://cloud.google.com/sdk/gcloud) installed and authenticated.
3. [Docker](https://www.docker.com/) installed and running locally.

### Step 1: Initialize Terraform
Navigate to the `terraform/` directory and initialize:
```bash
cd terraform
terraform init
```

Create a `terraform.tfvars` file to supply variables:
```hcl
project_id = "YOUR_GCP_PROJECT_ID"
region     = "us-central1"
prefix     = "doc-pipeline"
```

### Step 2: Bootstrap Artifact Registry (Phase 1)
To deploy Cloud Run, the Docker image must already exist. We bootstrap by creating only the Artifact Registry repository first:
```bash
terraform apply -target=google_artifact_registry_repository.repo
```

This will output the Artifact Registry repository URL, which looks like:
`us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/doc-pipeline-repo`

### Step 3: Build & Push the Docker Image
1. Configure Docker to authenticate with GCP Artifact Registry:
   ```bash
   gcloud auth configure-docker us-central1-docker.pkg.dev
   ```
2. Build the Docker container (run from the project root directory):
   ```bash
   docker build -t us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/doc-pipeline-repo/processor:latest ./processor
   ```
3. Push the image:
   ```bash
   docker push us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/doc-pipeline-repo/processor:latest
   ```

### Step 4: Deploy the Full Pipeline (Phase 2)
Now deploy the rest of the infrastructure (GCS, Pub/Sub, Cloud Run, BigQuery, and IAM):
```bash
cd terraform
terraform apply
```

---

## Verification & Testing

### 1. Run Local Tests (Offline Mocking)
You can verify the Python application code locally without GCP credentials using mock clients:
```bash
# Setup environment and dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r processor/requirements.txt httpx

# Run tests
python3 processor/test_local.py
```

### 2. Manual End-to-End Pipeline Testing
Once deployed:
1. Upload a file to your GCS ingestion bucket (you can find the bucket name in the Terraform output):
   ```bash
   gcloud storage cp processor/requirements.txt gs://doc-pipeline-ingestion-YOUR_GCP_PROJECT_ID/
   ```
2. Check the logs of the Cloud Run service in the GCP Console to see the incoming Pub/Sub message trigger and the processing log.
3. Query the BigQuery metadata table to verify the streamed row:
   ```sql
   SELECT * FROM `YOUR_GCP_PROJECT_ID.doc_pipeline.metadata` LIMIT 10;
   ```
