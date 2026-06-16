terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Get current project metadata
data "google_project" "project" {}

# 1. Enable Required API Services
resource "google_project_service" "services" {
  for_each = toset([
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry Repository to host the Processor Docker Image
resource "google_artifact_registry_repository" "repo" {
  depends_on    = [google_project_service.services]
  location      = var.region
  repository_id = "${var.prefix}-repo"
  description   = "Docker repository for document processing pipeline"
  format        = "DOCKER"
}

# 3. GCS Ingestion Bucket
resource "google_storage_bucket" "ingestion_bucket" {
  depends_on                  = [google_project_service.services]
  name                        = "${var.prefix}-ingestion-${var.project_id}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# 4. Pub/Sub Topic for GCS upload events
resource "google_pubsub_topic" "notifications" {
  depends_on = [google_project_service.services]
  name       = "${var.prefix}-gcs-notifications"
}

# 5. IAM binding: Allow GCS to publish to the Pub/Sub topic
data "google_storage_project_service_account" "gcs_account" {
  depends_on = [google_project_service.services]
}

resource "google_pubsub_topic_iam_binding" "gcs_publisher" {
  topic = google_pubsub_topic.notifications.name
  role  = "roles/pubsub.publisher"
  members = [
    "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
  ]
}

# 6. GCS Bucket Notification to trigger Pub/Sub when files are uploaded
resource "google_storage_notification" "gcs_notification" {
  depends_on     = [google_pubsub_topic_iam_binding.gcs_publisher]
  bucket         = google_storage_bucket.ingestion_bucket.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.notifications.id
  event_types    = ["OBJECT_FINALIZE"]
}

# 7. BigQuery Dataset & Table for processing metadata
resource "google_bigquery_dataset" "dataset" {
  depends_on = [google_project_service.services]
  dataset_id = replace(var.prefix, "-", "_")
  location   = var.region
}

resource "google_bigquery_table" "metadata_table" {
  dataset_id          = google_bigquery_dataset.dataset.dataset_id
  table_id            = "metadata"
  deletion_protection = false

  schema = <<EOF
[
  {
    "name": "filename",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "The name of the processed file"
  },
  {
    "name": "bucket",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "The GCS bucket name where the file was uploaded"
  },
  {
    "name": "uploaded_at",
    "type": "TIMESTAMP",
    "mode": "NULLABLE",
    "description": "The file upload timestamp"
  },
  {
    "name": "processed_at",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "The processing timestamp"
  },
  {
    "name": "word_count",
    "type": "INTEGER",
    "mode": "NULLABLE",
    "description": "Extracted or simulated word count"
  },
  {
    "name": "tags",
    "type": "STRING",
    "mode": "REPEATED",
    "description": "Extracted keywords or tags"
  },
  {
    "name": "ocr_summary",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "First 200 characters of text or simulated description"
  }
]
EOF
}

# 8. Cloud Run Processor Service Account & Permissions
resource "google_service_account" "cloud_run_sa" {
  depends_on   = [google_project_service.services]
  account_id   = "${var.prefix}-run-sa"
  display_name = "Cloud Run Service Account for Document Processing"
}

# Grant custom Cloud Run SA permission to read from the GCS bucket
resource "google_storage_bucket_iam_member" "gcs_viewer" {
  bucket = google_storage_bucket.ingestion_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Grant custom Cloud Run SA permission to write to the BigQuery dataset
resource "google_bigquery_dataset_iam_member" "bq_editor" {
  dataset_id = google_bigquery_dataset.dataset.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Grant custom Cloud Run SA permission to launch jobs in BigQuery
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 9. Cloud Run Service (deployed using Docker image path from repository)
resource "google_cloud_run_v2_service" "processor" {
  depends_on = [google_artifact_registry_repository.repo]
  name       = "${var.prefix}-processor"
  location   = var.region
  ingress    = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Restricts access to internal/authenticated callers (like Pub/Sub)

  template {
    service_account = google_service_account.cloud_run_sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/processor:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.dataset.dataset_id
      }
      env {
        name  = "BQ_TABLE"
        value = google_bigquery_table.metadata_table.table_id
      }
    }
  }
}

# 10. Service Account for Pub/Sub Subscription & Permissions
resource "google_service_account" "pubsub_subscriber_sa" {
  depends_on   = [google_project_service.services]
  account_id   = "${var.prefix}-pubsub-sa"
  display_name = "Service Account for Pub/Sub Push Subscription"
}

# Allow Pub/Sub Subscriber SA to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  name     = google_cloud_run_v2_service.processor.name
  location = google_cloud_run_v2_service.processor.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_subscriber_sa.email}"
}

# Allow Pub/Sub Service Agent to create OIDC identity tokens using our subscriber SA
resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.pubsub_subscriber_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# 11. Pub/Sub Push Subscription routing GCS events to Cloud Run
resource "google_pubsub_subscription" "push_sub" {
  name  = "${var.prefix}-push-subscription"
  topic = google_pubsub_topic.notifications.name

  ack_deadline_seconds = 60

  push_config {
    push_endpoint = google_cloud_run_v2_service.processor.uri

    oidc_token {
      service_account_email = google_service_account.pubsub_subscriber_sa.email
      audience              = google_cloud_run_v2_service.processor.uri
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.invoker,
    google_service_account_iam_member.pubsub_token_creator
  ]
}
