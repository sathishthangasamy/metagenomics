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
    
    def list_gcs_files(
        self,
        bucket_name: str,
        prefix: str = "",
        file_extensions: list = None
    ) -> list:
        """
        List files in a GCS bucket matching the given extensions.
        
        Args:
            bucket_name: Name of the GCS bucket
            prefix: Prefix to filter files (e.g., 'samples/')
            file_extensions: List of file extensions to filter (e.g., ['.fq.gz', '.fastq.gz'])
            
        Returns:
            List of dicts with: name, path, size, size_human_readable
        """
        if file_extensions is None:
            file_extensions = [".fq.gz", ".fastq.gz"]
        
        files = []
        
        try:
            # Get the bucket
            if bucket_name and bucket_name != self.bucket_name:
                bucket = self.client.bucket(bucket_name)
            elif self.bucket:
                bucket = self.bucket
            else:
                print("Error: No bucket available")
                return []
            
            # List blobs with prefix
            blobs = bucket.list_blobs(prefix=prefix)
            
            for blob in blobs:
                # Skip directories
                if blob.name.endswith('/'):
                    continue
                
                # Check if file matches any of the extensions
                if any(blob.name.endswith(ext) for ext in file_extensions):
                    files.append({
                        'name': blob.name.split('/')[-1],
                        'path': blob.name,
                        'size': blob.size,
                        'size_human_readable': format_file_size(blob.size)
                    })
        
        except Exception as e:
            print(f"Error listing GCS files: {e}")
        
        return files
    
    def get_gcs_file_info(self, bucket_name: str, file_path: str) -> dict:
        """
        Get metadata for a specific file in GCS.
        
        Args:
            bucket_name: Name of the GCS bucket
            file_path: Full path to the file in the bucket
            
        Returns:
            Dict with: name, path, size, size_human_readable, created, updated
        """
        try:
            # Get the bucket
            if bucket_name and bucket_name != self.bucket_name:
                bucket = self.client.bucket(bucket_name)
            elif self.bucket:
                bucket = self.bucket
            else:
                print("Error: No bucket available")
                return {}
            
            # Get blob
            blob = bucket.blob(file_path)
            
            if not blob.exists():
                print(f"Error: File not found: {file_path}")
                return {}
            
            # Reload to get latest metadata
            blob.reload()
            
            return {
                'name': blob.name.split('/')[-1],
                'path': blob.name,
                'size': blob.size,
                'size_human_readable': format_file_size(blob.size),
                'created': blob.time_created,
                'updated': blob.updated
            }
        
        except Exception as e:
            print(f"Error getting file info: {e}")
            return {}


def validate_paired_files(file_list: list) -> tuple:
    """
    Validate that selected files are proper paired-end reads.
    
    Args:
        file_list: List of file paths or names
        
    Returns:
        (is_valid, forward_file, reverse_file, error_message)
    """
    if not file_list or len(file_list) == 0:
        return (False, None, None, "No files selected")
    
    if len(file_list) == 1:
        return (False, None, None, "Please select both forward and reverse read files (R1 and R2)")
    
    if len(file_list) > 2:
        return (False, None, None, "Please select exactly 2 files (forward and reverse reads)")
    
    # Sort files to ensure consistent ordering
    sorted_files = sorted(file_list)
    
    # Check for common paired-end naming patterns
    # Patterns: _R1/_R2, _1/_2, .R1./.R2., .1./.2.
    file1, file2 = sorted_files[0], sorted_files[1]
    
    # Extract base names without extensions
    base1 = file1.replace('.fq.gz', '').replace('.fastq.gz', '').replace('.fq', '').replace('.fastq', '')
    base2 = file2.replace('.fq.gz', '').replace('.fastq.gz', '').replace('.fq', '').replace('.fastq', '')
    
    # Check various paired-end patterns
    patterns_valid = False
    
    # Pattern 1: _R1 / _R2
    if (base1.endswith('_R1') or base1.endswith('_1')) and (base2.endswith('_R2') or base2.endswith('_2')):
        base1_prefix = base1.rsplit('_', 1)[0]
        base2_prefix = base2.rsplit('_', 1)[0]
        if base1_prefix == base2_prefix:
            patterns_valid = True
    
    # Pattern 2: .R1. / .R2.
    elif '_1.' in file1 and '_2.' in file2:
        base1_prefix = file1.split('_1.')[0]
        base2_prefix = file2.split('_2.')[0]
        if base1_prefix == base2_prefix:
            patterns_valid = True
    
    # Pattern 3: .1. / .2.
    elif '.1.' in file1 and '.2.' in file2:
        base1_prefix = file1.split('.1.')[0]
        base2_prefix = file2.split('.2.')[0]
        if base1_prefix == base2_prefix:
            patterns_valid = True
    
    if not patterns_valid:
        return (
            False,
            None,
            None,
            "Selected files do not appear to be paired reads. Expected naming: *_R1/*_R2 or *_1/*_2"
        )
    
    # Determine which is forward and which is reverse
    if '_R1' in file1 or '_1' in file1 or '.1.' in file1:
        forward_file = file1
        reverse_file = file2
    else:
        forward_file = file2
        reverse_file = file1
    
    return (True, forward_file, reverse_file, "")


def format_file_size(size_bytes: int) -> str:
    """
    Convert bytes to human readable format (e.g., "25.1 GB").
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Human-readable file size string
    """
    if size_bytes is None:
        return "Unknown"
    
    # Define size units
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    # Format with appropriate decimal places
    if unit_index == 0:  # Bytes
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"
