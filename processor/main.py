import base64
import datetime
import json
import os
import logging
from typing import List
from fastapi import FastAPI, Request, Response, status
from google.cloud import storage
from google.cloud import bigquery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Read configurations from environment variables (injected by Cloud Run/Terraform)
PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
BQ_DATASET = os.environ.get("BQ_DATASET", "document_pipeline")
BQ_TABLE = os.environ.get("BQ_TABLE", "metadata")

# Initialize GCP clients with local fallback when no credentials are found
# Note: In production, clients will authenticate automatically using the assigned Service Account.
try:
    storage_client = storage.Client()
    logger.info("Google Cloud Storage client initialized successfully.")
except Exception as e:
    logger.warning(f"Could not initialize GCS client (falling back to mock storage): {e}")
    storage_client = None

try:
    bq_client = bigquery.Client()
    logger.info("Google Cloud BigQuery client initialized successfully.")
except Exception as e:
    logger.warning(f"Could not initialize BigQuery client (falling back to mock database): {e}")
    bq_client = None

def simulate_ocr(file_content: bytes, filename: str, content_type: str) -> dict:
    """
    Simulates OCR processing on the file content.
    Returns:
        dict: containing word_count, tags, and ocr_summary
    """
    word_count = 0
    tags = []
    ocr_summary = ""

    # Check if the file is text-based
    is_text = False
    text_content = ""
    
    if filename.endswith(".txt") or filename.endswith(".md") or (content_type and "text/" in content_type):
        is_text = True
        try:
            text_content = file_content.decode("utf-8")
        except UnicodeDecodeError:
            is_text = False

    if is_text:
        # Exact word count for text files
        words = text_content.split()
        word_count = len(words)
        
        # Simple keyword tagging
        keywords = ["invoice", "report", "receipt", "urgent", "draft", "final", "design", "code", "contract", "billing"]
        lower_text = text_content.lower()
        for kw in keywords:
            if kw in lower_text:
                tags.append(kw)
        
        # Extract summary
        ocr_summary = text_content[:200].strip() + ("..." if len(text_content) > 200 else "")
    else:
        # Simulated OCR for binary/unsupported files (e.g., PDF, images)
        # We generate a mock word count based on file size
        file_size = len(file_content)
        word_count = max(1, file_size // 10)  # rough mock
        
        # Guess tags from filename
        lower_name = filename.lower()
        keywords = ["invoice", "report", "receipt", "urgent", "draft", "final", "design", "code", "contract", "billing"]
        for kw in keywords:
            if kw in lower_name:
                tags.append(kw)
                
        ocr_summary = f"Simulated OCR extraction for binary file: {filename}. Content-type: {content_type or 'unknown'}. Size: {file_size} bytes."

    # Default fallback tag if none found
    if not tags:
        tags.append("generic")
        
    return {
        "word_count": word_count,
        "tags": tags,
        "ocr_summary": ocr_summary
    }

@app.post("/", status_code=status.HTTP_200_OK)
async def handle_pubsub_message(request: Request, response: Response):
    """
    Receives and processes Pub/Sub push notifications.
    """
    try:
        envelope = await request.json()
    except Exception as e:
        logger.error(f"Error parsing request JSON: {e}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid JSON envelope"}

    if not envelope or "message" not in envelope:
        logger.error("Invalid Pub/Sub envelope: missing 'message' key")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Missing message field"}

    pubsub_message = envelope["message"]
    
    # 1. Decode GCS Object Metadata from Pub/Sub message data
    if "data" not in pubsub_message:
        logger.error("Pub/Sub message contains no data payload")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Missing data field in Pub/Sub message"}

    try:
        data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        event_data = json.loads(data_str)
    except Exception as e:
        logger.error(f"Failed to decode base64 data: {e}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Failed to decode payload"}

    # Extract bucket name and object name
    bucket_name = event_data.get("bucket")
    object_name = event_data.get("name")
    content_type = event_data.get("contentType", "")
    time_created = event_data.get("timeCreated")

    if not bucket_name or not object_name:
        logger.warning(f"Ignored non-GCS finalize event or missing metadata. Payload: {event_data}")
        return {"status": "ignored", "reason": "Missing bucket or name"}

    logger.info(f"Processing file: gs://{bucket_name}/{object_name}")

    try:
        # 2. Download the object from GCS (or mock if running offline)
        if storage_client:
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)
            
            if not blob.exists():
                logger.error(f"Blob does not exist in bucket: gs://{bucket_name}/{object_name}")
                return {"status": "error", "reason": "Blob does not exist"}

            file_content = blob.download_as_bytes()
            logger.info(f"Downloaded {len(file_content)} bytes for gs://{bucket_name}/{object_name}")
        else:
            logger.warning(f"GCS client unavailable. Simulating file download for gs://{bucket_name}/{object_name}")
            # Mock content based on filename extension for testing OCR logic
            if object_name.endswith(".txt") or object_name.endswith(".md"):
                file_content = b"This is a simulated invoice document created during local testing. Pay urgently."
            else:
                file_content = b"\x25\x50\x44\x46-1.4 mock pdf data"

        # 3. Perform simulated OCR
        ocr_results = simulate_ocr(file_content, object_name, content_type)
        logger.info(f"Simulated OCR completed: {ocr_results}")

        # 4. Stream metadata to BigQuery (or mock if running offline)
        # format timestamps for BigQuery
        uploaded_at = time_created if time_created else datetime.datetime.utcnow().isoformat()
        processed_at = datetime.datetime.utcnow().isoformat()

        row_to_insert = {
            "filename": object_name,
            "bucket": bucket_name,
            "uploaded_at": uploaded_at,
            "processed_at": processed_at,
            "word_count": ocr_results["word_count"],
            "tags": ocr_results["tags"],
            "ocr_summary": ocr_results["ocr_summary"]
        }

        if bq_client:
            table_ref = bq_client.dataset(BQ_DATASET).table(BQ_TABLE)
            errors = bq_client.insert_rows_json(table_ref, [row_to_insert])
            if errors:
                logger.error(f"BigQuery streaming errors: {errors}")
                raise RuntimeError(f"BigQuery insert failed: {errors}")
            logger.info(f"Successfully saved metadata for {object_name} to BigQuery table {BQ_DATASET}.{BQ_TABLE}")
        else:
            logger.warning("BigQuery client unavailable. Local run log of metadata to insert:")
            logger.info(json.dumps(row_to_insert, indent=2))

        return {"status": "success", "file": object_name, "mocked": storage_client is None}

    except Exception as e:
        logger.exception(f"Unhandled error processing gs://{bucket_name}/{object_name}: {e}")
        # Note: If it is a transient error, we return 500 so Pub/Sub will retry.
        # If it is a permanent processing error, we might want to return 200 to acknowledge and move on,
        # but for safety, we return 500 to catch configuration/infrastructure errors.
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
