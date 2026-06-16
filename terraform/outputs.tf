output "gcs_bucket_name" {
  value       = google_storage_bucket.ingestion_bucket.name
  description = "The name of the GCS ingestion bucket."
}

output "pubsub_topic_name" {
  value       = google_pubsub_topic.notifications.name
  description = "The name of the Pub/Sub notifications topic."
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.processor.uri
  description = "The endpoint URL of the Cloud Run processor service."
}

output "bigquery_dataset_id" {
  value       = google_bigquery_dataset.dataset.dataset_id
  description = "The BigQuery dataset ID."
}

output "bigquery_table_id" {
  value       = google_bigquery_table.metadata_table.table_id
  description = "The BigQuery table ID."
}

output "artifact_registry_repo" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
  description = "The Artifact Registry Docker repository URI."
}
