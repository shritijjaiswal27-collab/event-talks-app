variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID."
}

variable "region" {
  type        = string
  description = "The primary Google Cloud region to deploy resources."
  default     = "us-central1"
}

variable "prefix" {
  type        = string
  description = "A naming prefix to ensure resource name uniqueness."
  default     = "doc-pipeline"
}
