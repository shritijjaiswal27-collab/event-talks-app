# Event-Driven Document Processing Pipeline on GCP

## Overview

The **Event-Driven Document Processing Pipeline on Google Cloud Platform (GCP)** is a serverless application that automatically processes documents uploaded to Google Cloud Storage (GCS).

The pipeline uses Google Cloud services, Python, FastAPI, Docker, and Terraform to automate document ingestion, text processing, metadata extraction, and data storage.

When a user uploads a document, the system generates an event, triggers a processing service, extracts useful information from the document, and stores the resulting metadata in BigQuery for further analysis.

This project demonstrates **event-driven architecture, serverless computing, API development, cloud storage, data engineering, and Infrastructure as Code (IaC).**

## Architecture

```text
          User Uploads Document
                   |
                   v
        Google Cloud Storage
                   |
            Object Finalize
                   |
                   v
              Pub/Sub Topic
                   |
                   v
          Pub/Sub Push Subscription
                   |
                   v
             Cloud Run Service
             (Python + FastAPI)
                   |
                   v
          Retrieve Document from GCS
                   |
                   v
          Document Processing
          - Word Count
          - Keyword Extraction
          - Summary Extraction
                   |
                   v
               BigQuery
           Metadata Storage
```

## How It Works

### 1. Document Ingestion

Users upload documents to a Google Cloud Storage bucket. GCS stores the files and generates an `OBJECT_FINALIZE` event when an object is successfully created.

### 2. Event Notification

The Cloud Storage notification publishes an event to a Google Cloud Pub/Sub topic. Pub/Sub provides asynchronous communication between the storage layer and the processing service.

### 3. Document Processing

A Pub/Sub push subscription sends the event to a Python FastAPI service deployed on Cloud Run.

The service identifies the uploaded document and retrieves it from Google Cloud Storage.

### 4. Text and Metadata Extraction

The processor performs the following operations:

- Retrieves the document content.
- Counts the words in the document.
- Extracts keywords to generate metadata tags.
- Produces a summary of the document content.
- Prepares the extracted information for storage.

**Note:** The current implementation simulates OCR/text processing. It should not be described as a production OCR engine unless an actual OCR service is integrated.

### 5. Data Storage and Analysis

The extracted metadata is streamed into a BigQuery table. The stored information can be queried using SQL for reporting, analysis, and downstream data-processing tasks.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| FastAPI | HTTP API for document processing |
| Google Cloud Storage | Document storage and ingestion |
| Google Cloud Pub/Sub | Event messaging and delivery |
| Google Cloud Run | Serverless application deployment |
| BigQuery | Metadata storage and analytics |
| Docker | Containerization of the application |
| Terraform | Infrastructure as Code |
| Google Cloud CLI (`gcloud`) | Cloud authentication and deployment |
| pytest / FastAPI TestClient | Local application testing |

## Project Structure

```text
event-talks-app/
├── bq_release_notes/
├── processor/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   └── test_local.py
├── terraform/
│   ├── main.tf
│   ├── outputs.tf
│   └── variables.tf
├── .gitignore
└── README.md
```

### Important Files

- `processor/main.py` — Implements the FastAPI application and document-processing logic.
- `processor/Dockerfile` — Defines the container image used to deploy the processor.
- `processor/requirements.txt` — Lists Python dependencies.
- `processor/test_local.py` — Contains local tests using mocked cloud clients.
- `terraform/main.tf` — Defines the Google Cloud infrastructure.
- `terraform/variables.tf` — Declares configurable Terraform variables.
- `terraform/outputs.tf` — Defines useful deployment outputs.

## Prerequisites

Before deploying the project, install and configure:

1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. [Terraform CLI](https://developer.hashicorp.com/terraform/install)
3. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
4. A Google Cloud project with billing enabled.
5. Appropriate permissions to create and manage Google Cloud resources.

The required Google Cloud APIs must also be enabled, including Cloud Run, Cloud Storage, Pub/Sub, BigQuery, Artifact Registry, and any APIs required by the Terraform configuration.

## Setup and Deployment

### Step 1: Authenticate with Google Cloud

Log in to your Google Cloud account:

```bash
gcloud auth login
```

Set your project:

```bash
gcloud config set project YOUR_GCP_PROJECT_ID
```

Configure Application Default Credentials for local development:

```bash
gcloud auth application-default login
```

### Step 2: Configure Terraform

Navigate to the Terraform directory:

```bash
cd terraform
terraform init
```

Create a `terraform.tfvars` file inside the `terraform/` directory:

```hcl
project_id = "YOUR_GCP_PROJECT_ID"
region     = "us-central1"
prefix     = "doc-pipeline"
```

Replace `YOUR_GCP_PROJECT_ID` with your actual Google Cloud project ID.

### Step 3: Create Artifact Registry

Initialize the container repository before deploying Cloud Run:

```bash
terraform apply -target=google_artifact_registry_repository.repo
```

Review the proposed changes before approving the operation.

### Step 4: Build and Push the Docker Image

Configure Docker authentication for Artifact Registry:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

Return to the project root directory:

```bash
cd ..
```

Build the processor image:

```bash
docker build \
  -t us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/doc-pipeline-repo/processor:latest \
  ./processor
```

Push the image to Artifact Registry:

```bash
docker push \
  us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/doc-pipeline-repo/processor:latest
```

Ensure that the image path matches the repository and image configuration defined in Terraform.

### Step 5: Deploy the Infrastructure

Navigate back to the Terraform directory:

```bash
cd terraform
```

Apply the infrastructure configuration:

```bash
terraform apply
```

Review the plan and confirm the deployment when prompted.

Terraform provisions the resources defined in the configuration, which may include Cloud Storage, Pub/Sub, Cloud Run, BigQuery, IAM permissions, and Artifact Registry.

Check the Terraform outputs for the deployed resource names and endpoints.

## Testing

### 1. Install Dependencies

From the project root, create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the processor dependencies:

```bash
pip install -r processor/requirements.txt
pip install httpx
```

### 2. Run Local Tests

Execute the local test script:

```bash
python3 processor/test_local.py
```

The tests use mocked cloud clients so that the application logic can be tested without making real Google Cloud requests, provided the tests are correctly configured to mock all external dependencies.

### 3. Upload a Test Document

After deployment, use the actual ingestion bucket name returned by Terraform:

```bash
gcloud storage cp processor/requirements.txt gs://YOUR_INGESTION_BUCKET/
```

Uploading a file should generate the configured Cloud Storage event and trigger the Pub/Sub-to-Cloud-Run processing flow.

### 4. Verify Cloud Run Logs

Inspect the service logs:

```bash
gcloud run services logs read YOUR_CLOUD_RUN_SERVICE \
  --region=us-central1 \
  --limit=50
```

Check for successful event delivery, document retrieval, processing, and BigQuery insertion. The exact log messages depend on the implementation in `processor/main.py`.

### 5. Verify BigQuery Results

Run the following SQL query in the BigQuery console, replacing the project, dataset, and table names with the values configured in Terraform:

```sql
SELECT *
FROM `YOUR_GCP_PROJECT_ID.doc_pipeline.metadata`
LIMIT 10;
```

If processing succeeds, the table should contain metadata records for the uploaded documents.

## Key Features

- **Event-driven processing:** Automatically responds to document-upload events.
- **Serverless deployment:** Runs the processor on Cloud Run without managing application servers.
- **Asynchronous messaging:** Uses Pub/Sub to decouple file uploads from processing.
- **Automated metadata extraction:** Generates word counts, keywords, and summaries.
- **Analytical storage:** Stores extracted metadata in BigQuery.
- **Infrastructure as Code:** Provisions cloud resources through Terraform.
- **Containerized deployment:** Packages the application with Docker.
- **Local testing:** Supports testing with mocked cloud dependencies.

## Potential Improvements

The project can be extended with the following features:

- Integrate Google Cloud Vision API or Document AI for actual OCR.
- Add support for PDF, DOCX, and scanned image documents.
- Implement more advanced summarization and keyword extraction.
- Introduce dead-letter topics and retry policies for failed events.
- Add structured logging, monitoring, and alerting.
- Implement authentication and request validation.
- Use Secret Manager for sensitive configuration.
- Add CI/CD automation using GitHub Actions.
- Add idempotency checks to prevent duplicate processing.
- Configure lifecycle policies and retention rules for uploaded documents.

## Learning Outcomes

This project provides practical experience with:

- Designing event-driven cloud architectures.
- Building REST APIs using FastAPI.
- Deploying Python applications to Cloud Run.
- Integrating Cloud Storage, Pub/Sub, and BigQuery.
- Building and publishing Docker images.
- Managing cloud infrastructure with Terraform.
- Testing applications with mocked external dependencies.
- Debugging distributed cloud-processing workflows.

## Conclusion

The Event-Driven Document Processing Pipeline demonstrates how cloud-native services can work together to automate document ingestion and metadata extraction.

By combining Google Cloud Storage, Pub/Sub, Cloud Run, BigQuery, Docker, FastAPI, and Terraform, the project provides a foundation for building scalable document-processing and data-ingestion applications.

## Author

**Shritij Jaiswal**

GitHub: [shritijjaiswal27-collab](https://github.com/shritijjaiswal27-collab)

Repository: [event-talks-app](https://github.com/shritijjaiswal27-collab/event-talks-app)
