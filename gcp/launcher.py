"""Google Compute Engine VM launcher for running the pipeline."""
import time
from typing import Dict, Optional
from google.cloud import compute_v1
from google.oauth2 import service_account
import config


class VMLauncher:
    """Handle VM provisioning and management on GCP."""
    
    def __init__(self):
        """Initialize the Compute Engine client."""
        self.project_id = config.GCP_PROJECT_ID
        self.zone = config.GCP_ZONE
        self.client = None
        
        if config.GCP_SERVICE_ACCOUNT_KEY:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    config.GCP_SERVICE_ACCOUNT_KEY
                )
                self.client = compute_v1.InstancesClient(credentials=credentials)
            except Exception as e:
                print(f"Warning: Could not initialize Compute Engine client: {e}")
        elif config.GCP_PROJECT_ID:
            # Try default credentials
            try:
                self.client = compute_v1.InstancesClient()
            except Exception as e:
                print(f"Warning: Could not initialize Compute Engine client: {e}")
    
    def create_vm(
        self,
        instance_name: str,
        machine_type: str,
        startup_script: str,
        vm_config: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Create and start a VM instance.
        
        Args:
            instance_name: Name for the VM instance
            machine_type: Machine type (e.g., 'n1-standard-16')
            startup_script: Startup script to run on the VM
            vm_config: Optional additional VM configuration
            
        Returns:
            Instance name if successful, None otherwise
        """
        if not self.client:
            print("Error: Compute Engine client not initialized")
            return None
        
        try:
            # Use default config if not provided
            if vm_config is None:
                vm_config = config.VM_CONFIGS.get("standard", {})
            
            # Define the instance configuration
            disk_config = compute_v1.AttachedDisk()
            disk_config.boot = True
            disk_config.auto_delete = True
            
            initialize_params = compute_v1.AttachedDiskInitializeParams()
            initialize_params.source_image = (
                "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
            )
            initialize_params.disk_size_gb = vm_config.get("boot_disk_size_gb", 100)
            disk_config.initialize_params = initialize_params
            
            # Network configuration
            network_interface = compute_v1.NetworkInterface()
            network_interface.name = "global/networks/default"
            
            # Access config for external IP
            access_config = compute_v1.AccessConfig()
            access_config.name = "External NAT"
            access_config.type_ = "ONE_TO_ONE_NAT"
            network_interface.access_configs = [access_config]
            
            # Metadata for startup script
            metadata = compute_v1.Metadata()
            metadata.items = [
                compute_v1.Items(key="startup-script", value=startup_script)
            ]
            
            # Scheduling configuration (for preemptible VMs)
            scheduling = compute_v1.Scheduling()
            scheduling.preemptible = vm_config.get("preemptible", True)
            scheduling.automatic_restart = False
            scheduling.on_host_maintenance = "TERMINATE"
            
            # Service account with necessary scopes
            service_account = compute_v1.ServiceAccount()
            service_account.email = "default"
            service_account.scopes = [
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/devstorage.full_control",
            ]
            
            # Build the instance
            instance = compute_v1.Instance()
            instance.name = instance_name
            instance.machine_type = f"zones/{self.zone}/machineTypes/{machine_type}"
            instance.disks = [disk_config]
            instance.network_interfaces = [network_interface]
            instance.metadata = metadata
            instance.scheduling = scheduling
            instance.service_accounts = [service_account]
            
            # Labels for tracking
            instance.labels = {
                "purpose": "metagenomics-pipeline",
                "auto-delete": "true"
            }
            
            # Create the instance
            operation = self.client.insert(
                project=self.project_id,
                zone=self.zone,
                instance_resource=instance
            )
            
            print(f"Creating VM instance: {instance_name}")
            print(f"Machine type: {machine_type}")
            print(f"Preemptible: {vm_config.get('preemptible', True)}")
            
            # Wait for the operation to complete
            self._wait_for_operation(operation)
            
            print(f"VM instance {instance_name} created successfully")
            return instance_name
            
        except Exception as e:
            print(f"Error creating VM: {e}")
            return None
    
    def delete_vm(self, instance_name: str) -> bool:
        """
        Delete a VM instance.
        
        Args:
            instance_name: Name of the instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            print("Error: Compute Engine client not initialized")
            return False
        
        try:
            operation = self.client.delete(
                project=self.project_id,
                zone=self.zone,
                instance=instance_name
            )
            
            print(f"Deleting VM instance: {instance_name}")
            self._wait_for_operation(operation)
            print(f"VM instance {instance_name} deleted successfully")
            return True
            
        except Exception as e:
            print(f"Error deleting VM: {e}")
            return False
    
    def get_instance_status(self, instance_name: str) -> Optional[str]:
        """
        Get the status of a VM instance.
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Instance status or None if not found
        """
        if not self.client:
            return None
        
        try:
            instance = self.client.get(
                project=self.project_id,
                zone=self.zone,
                instance=instance_name
            )
            return instance.status
        except Exception as e:
            print(f"Error getting instance status: {e}")
            return None
    
    def _wait_for_operation(self, operation, timeout: int = 300):
        """
        Wait for a Compute Engine operation to complete.
        
        Args:
            operation: The operation to wait for
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if operation.status == compute_v1.Operation.Status.DONE:
                if operation.error:
                    raise Exception(f"Operation failed: {operation.error}")
                return
            time.sleep(5)
        
        raise TimeoutError(f"Operation timed out after {timeout} seconds")
    
    def generate_startup_script(
        self,
        job_id: str,
        input_file_1: str,
        input_file_2: str,
        threads: int,
        min_contig_len: int,
        enabled_steps: Dict[str, bool]
    ) -> str:
        """
        Generate a startup script for the VM.
        
        Args:
            job_id: Unique job identifier
            input_file_1: GCS URI of first input file
            input_file_2: GCS URI of second input file
            threads: Number of threads to use
            min_contig_len: Minimum contig length
            enabled_steps: Dictionary of enabled pipeline steps
            
        Returns:
            Startup script as a string
        """
        bucket_name = config.GCP_BUCKET_NAME
        
        # Convert enabled steps to comma-separated list
        steps_list = [step for step, enabled in enabled_steps.items() if enabled]
        steps_str = ",".join(steps_list)
        
        script = f"""#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/startup-script.log)
exec 2>&1

echo "Starting metagenomics pipeline for job: {job_id}"
echo "Timestamp: $(date)"

# Update and install dependencies
apt-get update
apt-get install -y docker.io git

# Start Docker
systemctl start docker
systemctl enable docker

# Clone the repository
cd /home
git clone https://github.com/sathishthangasamy/metagenomics.git
cd metagenomics

# Build Docker image
docker build -t metagenomics:latest .

# Install additional tools in container
docker run --name pipeline -d metagenomics:latest sleep infinity
docker exec pipeline apt-get update
docker exec pipeline apt-get install -y seqkit parallel vim google-cloud-sdk

# Create data directory
docker exec pipeline mkdir -p /data

# Download input files from GCS
echo "Downloading input files..."
docker exec pipeline gsutil cp {input_file_1} /data/CV_1.fq.gz
docker exec pipeline gsutil cp {input_file_2} /data/CV_2.fq.gz

# Run the pipeline
echo "Running pipeline with parameters:"
echo "  Threads: {threads}"
echo "  Min contig length: {min_contig_len}"
echo "  Enabled steps: {steps_str}"

# Copy pipeline script
docker cp pipeline/run.sh pipeline:/pipeline/run.sh
docker exec pipeline chmod +x /pipeline/run.sh

# Execute the pipeline
docker exec pipeline /pipeline/run.sh \\
    --threads {threads} \\
    --min-contig-len {min_contig_len} \\
    --steps "{steps_str}" \\
    --job-id {job_id} \\
    --bucket {bucket_name}

# Upload results to GCS
echo "Uploading results to GCS..."
docker exec pipeline gsutil -m cp -r /data/results/* gs://{bucket_name}/results/{job_id}/

# Cleanup
echo "Pipeline completed successfully"
echo "Timestamp: $(date)"

# Create completion marker
echo "DONE" | docker exec -i pipeline gsutil cp - gs://{bucket_name}/jobs/{job_id}/status.txt

# Shutdown the VM
shutdown -h now
"""
        return script
