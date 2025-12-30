"""Google Cloud Storage handler for uploading and downloading files."""
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional, Callable
from google.cloud import storage
from google.oauth2 import service_account
import config


class StorageHandler:
    """Handle file operations with Google Cloud Storage."""
    
    def __init__(self):
        """Initialize the GCS client."""
        self.project_id = config.GCP_PROJECT_ID
        self.bucket_name = config.GCP_BUCKET_NAME
        self.client = None
        self.bucket = None
        
        if config.GCP_SERVICE_ACCOUNT_KEY and os.path.exists(config.GCP_SERVICE_ACCOUNT_KEY):
            credentials = service_account.Credentials.from_service_account_file(
                config.GCP_SERVICE_ACCOUNT_KEY
            )
            self.client = storage.Client(
                project=self.project_id,
                credentials=credentials
            )
        elif config.GCP_PROJECT_ID:
            # Try default credentials
            try:
                self.client = storage.Client(project=self.project_id)
            except Exception as e:
                print(f"Warning: Could not initialize GCS client: {e}")
        
        if self.client and self.bucket_name:
            try:
                self.bucket = self.client.bucket(self.bucket_name)
            except Exception as e:
                print(f"Warning: Could not access bucket {self.bucket_name}: {e}")
    
    def upload_file(
        self,
        local_path: str,
        blob_name: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Upload a file to GCS with progress tracking.
        
        Args:
            local_path: Path to the local file
            blob_name: Name of the blob in GCS
            progress_callback: Optional callback function(bytes_uploaded, total_bytes)
            
        Returns:
            GCS URI of the uploaded file or None if failed
        """
        if not self.bucket:
            print("Error: GCS bucket not initialized")
            return None
            
        try:
            local_path = Path(local_path)
            if not local_path.exists():
                print(f"Error: File not found: {local_path}")
                return None
            
            file_size = local_path.stat().st_size
            blob = self.bucket.blob(blob_name)
            
            # For large files, use chunked upload
            chunk_size = config.CHUNK_SIZE_MB * 1024 * 1024  # Convert to bytes
            
            if file_size > chunk_size:
                # Chunked upload with progress tracking
                with open(local_path, 'rb') as file_obj:
                    bytes_uploaded = 0
                    while True:
                        chunk = file_obj.read(chunk_size)
                        if not chunk:
                            break
                        
                        bytes_uploaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(bytes_uploaded, file_size)
                    
                # Actually upload the file
                blob.upload_from_filename(str(local_path))
            else:
                # Simple upload for smaller files
                blob.upload_from_filename(str(local_path))
                if progress_callback:
                    progress_callback(file_size, file_size)
            
            gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
            print(f"Uploaded {local_path.name} to {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            print(f"Error uploading file: {e}")
            return None
    
    def download_file(
        self,
        blob_name: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download a file from GCS.
        
        Args:
            blob_name: Name of the blob in GCS
            local_path: Local path to save the file
            progress_callback: Optional callback function(bytes_downloaded, total_bytes)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            print("Error: GCS bucket not initialized")
            return False
            
        try:
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                print(f"Error: Blob not found: {blob_name}")
                return False
            
            # Create parent directory if it doesn't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file
            blob.download_to_filename(local_path)
            
            if progress_callback:
                file_size = Path(local_path).stat().st_size
                progress_callback(file_size, file_size)
            
            print(f"Downloaded {blob_name} to {local_path}")
            return True
            
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False
    
    def generate_signed_url(
        self,
        blob_name: str,
        expiration_minutes: int = 60
    ) -> Optional[str]:
        """
        Generate a signed URL for downloading a file.
        
        Args:
            blob_name: Name of the blob in GCS
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed URL or None if failed
        """
        if not self.bucket:
            print("Error: GCS bucket not initialized")
            return None
            
        try:
            blob = self.bucket.blob(blob_name)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )
            
            return url
            
        except Exception as e:
            print(f"Error generating signed URL: {e}")
            return None
    
    def list_blobs(self, prefix: str = "") -> list:
        """
        List all blobs with a given prefix.
        
        Args:
            prefix: Prefix to filter blobs
            
        Returns:
            List of blob names
        """
        if not self.bucket:
            return []
            
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            print(f"Error listing blobs: {e}")
            return []
    
    def delete_blob(self, blob_name: str) -> bool:
        """
        Delete a blob from GCS.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            return False
            
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            print(f"Deleted {blob_name}")
            return True
        except Exception as e:
            print(f"Error deleting blob: {e}")
            return False
