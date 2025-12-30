"""Monitor pipeline job status and progress on GCP."""
import time
import re
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from gcp.storage import StorageHandler
from gcp.launcher import VMLauncher
import config


class JobMonitor:
    """Monitor and track pipeline job progress."""
    
    def __init__(self):
        """Initialize the job monitor."""
        self.storage = StorageHandler()
        self.vm_launcher = VMLauncher()
    
    def get_job_status(self, job_id: str, instance_name: str) -> Dict:
        """
        Get the current status of a pipeline job.
        
        Args:
            job_id: Unique job identifier
            instance_name: Name of the VM instance
            
        Returns:
            Dictionary with job status information
        """
        status = {
            "job_id": job_id,
            "status": "unknown",
            "progress": 0,
            "current_step": None,
            "steps": {},
            "elapsed_time": 0,
            "estimated_cost": 0.0,
            "vm_status": "unknown",
            "error": None,
        }
        
        try:
            # Check VM status
            vm_status = self.vm_launcher.get_instance_status(instance_name)
            status["vm_status"] = vm_status or "not_found"
            
            # Check for completion marker
            completion_blob = f"jobs/{job_id}/status.txt"
            blobs = self.storage.list_blobs(prefix=completion_blob)
            
            if blobs:
                status["status"] = "complete"
                status["progress"] = 100
                return status
            
            # Parse logs for progress
            log_blob = f"jobs/{job_id}/pipeline.log"
            blobs = self.storage.list_blobs(prefix=log_blob)
            
            if blobs:
                # Download and parse log
                local_log = f"/tmp/{job_id}_pipeline.log"
                if self.storage.download_file(log_blob, local_log):
                    step_status = self._parse_pipeline_log(local_log)
                    status["steps"] = step_status
                    status["current_step"] = self._get_current_step(step_status)
                    status["progress"] = self._calculate_progress(step_status)
            
            # Determine overall status
            if vm_status == "RUNNING":
                status["status"] = "running"
            elif vm_status == "TERMINATED":
                if status["progress"] == 100:
                    status["status"] = "complete"
                else:
                    status["status"] = "failed"
            elif vm_status == "PROVISIONING" or vm_status == "STAGING":
                status["status"] = "starting"
            
        except Exception as e:
            status["error"] = str(e)
            status["status"] = "error"
        
        return status
    
    def _parse_pipeline_log(self, log_file: str) -> Dict[str, Dict]:
        """
        Parse the pipeline log file to extract step status.
        
        Args:
            log_file: Path to the log file
            
        Returns:
            Dictionary of step statuses
        """
        steps = {}
        
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Look for step markers in the log
            step_patterns = {
                "fastqc": r"Running FastQC",
                "trimmomatic": r"Running Trimmomatic",
                "megahit": r"Running MEGAHIT",
                "prodigal": r"Running Prodigal",
                "hmmscan": r"Running HMMscan",
                "binning": r"Running MetaBAT2",
                "checkm": r"Running CheckM",
            }
            
            completion_patterns = {
                "fastqc": r"FastQC completed",
                "trimmomatic": r"Trimmomatic completed",
                "megahit": r"MEGAHIT completed",
                "prodigal": r"Prodigal completed",
                "hmmscan": r"HMMscan completed",
                "binning": r"MetaBAT2 completed",
                "checkm": r"CheckM completed",
            }
            
            for step, pattern in step_patterns.items():
                if re.search(pattern, log_content):
                    completion_pattern = completion_patterns[step]
                    if re.search(completion_pattern, log_content):
                        steps[step] = {"status": "complete", "progress": 100}
                    else:
                        steps[step] = {"status": "running", "progress": 50}
                else:
                    steps[step] = {"status": "pending", "progress": 0}
        
        except Exception as e:
            print(f"Error parsing log file: {e}")
        
        return steps
    
    def _get_current_step(self, steps: Dict[str, Dict]) -> Optional[str]:
        """
        Determine the current running step.
        
        Args:
            steps: Dictionary of step statuses
            
        Returns:
            Name of the current step or None
        """
        for step, info in steps.items():
            if info.get("status") == "running":
                return step
        return None
    
    def _calculate_progress(self, steps: Dict[str, Dict]) -> int:
        """
        Calculate overall progress percentage.
        
        Args:
            steps: Dictionary of step statuses
            
        Returns:
            Progress percentage (0-100)
        """
        if not steps:
            return 0
        
        total_steps = len(steps)
        completed_steps = sum(1 for info in steps.values() if info.get("status") == "complete")
        
        return int((completed_steps / total_steps) * 100)
    
    def estimate_cost(
        self,
        machine_type: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> float:
        """
        Estimate the cost of running the pipeline.
        
        Args:
            machine_type: Type of VM instance
            start_time: Job start time
            end_time: Job end time (None for current time)
            
        Returns:
            Estimated cost in USD
        """
        if end_time is None:
            end_time = datetime.now()
        
        duration_hours = (end_time - start_time).total_seconds() / 3600
        hourly_rate = config.COST_PER_HOUR.get(machine_type, 0.5)
        
        return duration_hours * hourly_rate
    
    def get_results(self, job_id: str) -> Dict[str, str]:
        """
        Get download URLs for all result files.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Dictionary mapping result type to download URL
        """
        results = {}
        
        try:
            # List all result files
            result_prefix = f"results/{job_id}/"
            blobs = self.storage.list_blobs(prefix=result_prefix)
            
            # Categorize results
            for blob_name in blobs:
                filename = blob_name.split('/')[-1]
                
                # Generate signed URL
                url = self.storage.generate_signed_url(blob_name, expiration_minutes=120)
                
                if url:
                    # Categorize by file type
                    if 'multiqc' in filename.lower():
                        results['multiqc_report'] = url
                    elif 'contigs' in filename.lower() and filename.endswith('.fa'):
                        results['contigs'] = url
                    elif 'pfam' in filename.lower() or 'hmmscan' in filename.lower():
                        results['pfam_annotations'] = url
                    elif 'bins' in filename.lower() or 'metabat' in filename.lower():
                        results['bins'] = url
                    elif 'checkm' in filename.lower():
                        results['checkm_report'] = url
                    else:
                        # Generic result file
                        results[filename] = url
        
        except Exception as e:
            print(f"Error getting results: {e}")
        
        return results
    
    def cancel_job(self, job_id: str, instance_name: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Unique job identifier
            instance_name: Name of the VM instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete the VM instance
            return self.vm_launcher.delete_vm(instance_name)
        except Exception as e:
            print(f"Error cancelling job: {e}")
            return False
