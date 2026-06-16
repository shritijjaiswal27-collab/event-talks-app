import base64
import json
import unittest
from unittest.mock import MagicMock, patch

# Set dummy environment variables for clients
import os
os.environ["PROJECT_ID"] = "mock-project-id"
os.environ["BQ_DATASET"] = "mock_dataset"
os.environ["BQ_TABLE"] = "mock_table"

# Mock the GCP clients before importing the app to avoid credentials errors
mock_storage_client = MagicMock()
mock_bq_client = MagicMock()

with patch("google.cloud.storage.Client", return_value=mock_storage_client), \
     patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
    from main import app
    from fastapi.testclient import TestClient

class TestDocumentProcessor(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Reset mocks before each test
        mock_storage_client.reset_mock()
        mock_bq_client.reset_mock()

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_process_text_file(self):
        # 1. Setup mock storage to return a sample invoice text file
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"This is an urgent invoice document. Please pay by tomorrow. Draft code: 1234."
        
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # 2. Setup mock BigQuery to return no errors (empty list)
        mock_bq_client.insert_rows_json.return_value = []

        # 3. Construct the Pub/Sub push notification payload
        gcs_notification = {
            "bucket": "input-bucket-name",
            "name": "invoices/june_invoice.txt",
            "contentType": "text/plain",
            "timeCreated": "2026-06-15T12:00:00Z"
        }
        
        # Base64 encode the notification
        encoded_data = base64.b64encode(json.dumps(gcs_notification).encode("utf-8")).decode("utf-8")
        
        pubsub_payload = {
            "message": {
                "data": encoded_data,
                "messageId": "1234567890",
                "publishTime": "2026-06-15T12:00:01Z"
            },
            "subscription": "projects/mock-project-id/subscriptions/mock-sub"
        }

        # 4. Invoke the FastAPI service
        response = self.client.post("/", json=pubsub_payload)
        
        # 5. Assertions
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "file": "invoices/june_invoice.txt", "mocked": False})
        
        # Verify GCS download was called correctly
        mock_storage_client.bucket.assert_called_once_with("input-bucket-name")
        mock_bucket.blob.assert_called_once_with("invoices/june_invoice.txt")
        mock_blob.download_as_bytes.assert_called_once()

        # Verify BigQuery insert was called with expected fields
        mock_bq_client.insert_rows_json.assert_called_once()
        call_args = mock_bq_client.insert_rows_json.call_args[0]
        
        # First arg is the Table reference, second is list of rows
        inserted_rows = call_args[1]
        self.assertEqual(len(inserted_rows), 1)
        
        inserted_row = inserted_rows[0]
        self.assertEqual(inserted_row["filename"], "invoices/june_invoice.txt")
        self.assertEqual(inserted_row["bucket"], "input-bucket-name")
        self.assertEqual(inserted_row["uploaded_at"], "2026-06-15T12:00:00Z")
        self.assertEqual(inserted_row["word_count"], 13)  # "This is an urgent..." has 13 words
        self.assertIn("invoice", inserted_row["tags"])
        self.assertIn("urgent", inserted_row["tags"])
        self.assertIn("code", inserted_row["tags"])
        self.assertIn("draft", inserted_row["tags"])
        self.assertTrue(inserted_row["ocr_summary"].startswith("This is an urgent invoice"))

    def test_process_binary_file(self):
        # 1. Setup mock storage to return binary data (e.g. mock PDF content)
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b"\x25\x50\x44\x46-1.4 mock pdf contents" # PDF magic bytes
        
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_bq_client.insert_rows_json.return_value = []

        # 2. Construct Pub/Sub payload for PDF
        gcs_notification = {
            "bucket": "input-bucket-name",
            "name": "reports/monthly_report.pdf",
            "contentType": "application/pdf",
            "timeCreated": "2026-06-15T12:05:00Z"
        }
        
        encoded_data = base64.b64encode(json.dumps(gcs_notification).encode("utf-8")).decode("utf-8")
        
        pubsub_payload = {
            "message": {
                "data": encoded_data,
                "messageId": "1234567891"
            }
        }

        # 3. Invoke endpoint
        response = self.client.post("/", json=pubsub_payload)
        
        # 4. Assertions
        self.assertEqual(response.status_code, 200)
        
        mock_bq_client.insert_rows_json.assert_called_once()
        inserted_row = mock_bq_client.insert_rows_json.call_args[0][1][0]
        
        self.assertEqual(inserted_row["filename"], "reports/monthly_report.pdf")
        self.assertIn("report", inserted_row["tags"])  # inferred from filename
        self.assertTrue("binary file" in inserted_row["ocr_summary"].lower())

    def test_missing_message(self):
        response = self.client.post("/", json={"invalid": "payload"})
        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
