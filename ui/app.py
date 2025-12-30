"""Gradio UI for Metagenomics Pipeline on GCP."""
import gradio as gr
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.theme import get_theme
from gcp.storage import StorageHandler, validate_paired_files, format_file_size
from gcp.launcher import VMLauncher
from gcp.monitor import JobMonitor
import config


class MetagenomicsUI:
    """Main UI class for the metagenomics pipeline."""
    
    def __init__(self):
        """Initialize the UI components."""
        self.storage = StorageHandler()
        self.launcher = VMLauncher()
        self.monitor = JobMonitor()
        self.current_job_id = None
        self.current_instance_name = None
        self.job_start_time = None
        self.gcs_file_mapping = {}  # Maps display names to GCS paths
    
    def create_ui(self):
        """Create and return the Gradio interface."""
        # Store theme and CSS for launch
        self.theme = get_theme()
        self.custom_css = self._get_custom_css()
        
        with gr.Blocks() as demo:
            # Header
            gr.Markdown(
                """
                # 🧬 Metagenomics Analysis Pipeline
                ### Powered by Google Cloud Platform
                
                Upload your metagenomic samples and run a complete analysis pipeline in the cloud.
                """,
                elem_classes="header"
            )
            
            # Connection status
            with gr.Row():
                gcp_status = gr.Markdown(self._check_gcp_connection(), elem_classes="status-box")
            
            with gr.Tabs() as tabs:
                # Tab 1: Upload & Configure
                with gr.Tab("📤 Upload & Configure"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### Sample Input")
                            
                            # Input method selection
                            input_method = gr.Radio(
                                choices=["Upload from computer", "Select from Google Cloud Storage"],
                                value="Upload from computer",
                                label="📂 Input Method"
                            )
                            
                            # Upload section (shown by default)
                            with gr.Group(visible=True) as upload_section:
                                gr.Markdown("Upload paired-end FASTQ files (.fq.gz or .fastq.gz)")
                                
                                file1 = gr.File(
                                    label="📁 Forward Reads (R1)",
                                    file_types=[".fq.gz", ".fastq.gz"],
                                    type="filepath"
                                )
                                file2 = gr.File(
                                    label="📁 Reverse Reads (R2)",
                                    file_types=[".fq.gz", ".fastq.gz"],
                                    type="filepath"
                                )
                                
                                upload_status = gr.Markdown("", elem_classes="upload-status")
                            
                            # GCS Browser section (hidden by default)
                            with gr.Group(visible=False) as gcs_section:
                                gr.Markdown("Select files from Google Cloud Storage")
                                
                                with gr.Row():
                                    gcs_bucket = gr.Textbox(
                                        label="🪣 Bucket Name",
                                        value=config.GCS_BROWSER_DEFAULT_BUCKET if config.GCS_BROWSER_DEFAULT_BUCKET else config.GCP_BUCKET_NAME,
                                        placeholder="my-metagenomics-bucket"
                                    )
                                
                                with gr.Row():
                                    gcs_prefix = gr.Textbox(
                                        label="📂 Path/Prefix",
                                        value=config.GCS_BROWSER_DEFAULT_PREFIX,
                                        placeholder="samples/"
                                    )
                                    gcs_refresh_btn = gr.Button("🔄 Refresh", size="sm", scale=0)
                                
                                gcs_files = gr.CheckboxGroup(
                                    label="Available Files",
                                    choices=[],
                                    value=[],
                                    interactive=True
                                )
                                
                                gcs_status = gr.Markdown("", elem_classes="upload-status")
                        
                        with gr.Column(scale=1):
                            gr.Markdown("### Pipeline Configuration")
                            
                            threads = gr.Slider(
                                minimum=1,
                                maximum=32,
                                value=config.DEFAULT_THREADS,
                                step=1,
                                label="🔧 Thread Count",
                                info="Number of CPU threads to use"
                            )
                            
                            min_contig_len = gr.Slider(
                                minimum=500,
                                maximum=5000,
                                value=config.DEFAULT_MIN_CONTIG_LEN,
                                step=100,
                                label="📏 Minimum Contig Length",
                                info="Minimum length for assembled contigs (bp)"
                            )
                            
                            gr.Markdown("### Pipeline Steps")
                            gr.Markdown("Select which analysis steps to run:")
                            
                            step_checkboxes = {}
                            for step_id, step_info in config.PIPELINE_STEPS.items():
                                step_checkboxes[step_id] = gr.Checkbox(
                                    label=f"{step_info['emoji']} {step_info['name']}",
                                    value=step_info['enabled']
                                )
                    
                    with gr.Row():
                        launch_btn = gr.Button(
                            "🚀 Launch Pipeline",
                            variant="primary",
                            size="lg",
                            scale=1
                        )
                        cancel_btn = gr.Button(
                            "🛑 Cancel Job",
                            variant="stop",
                            size="lg",
                            scale=1,
                            visible=False
                        )
                    
                    launch_output = gr.Markdown("")
                
                # Tab 2: Monitor Progress
                with gr.Tab("📊 Monitor Progress"):
                    with gr.Row():
                        refresh_btn = gr.Button("🔄 Refresh Status", size="sm")
                    
                    with gr.Row():
                        with gr.Column():
                            job_info = gr.Markdown("### Job Information\nNo active job")
                            
                            progress_bar = gr.Progress()
                            
                            pipeline_status = gr.Markdown(
                                self._render_pipeline_status({}),
                                elem_classes="pipeline-status"
                            )
                        
                        with gr.Column():
                            cost_info = gr.Markdown("### Cost Estimate\n$0.00")
                            vm_info = gr.Markdown("### VM Status\nNo VM running")
                
                # Tab 3: Results
                with gr.Tab("📥 Results"):
                    with gr.Row():
                        download_btn = gr.Button("📦 Get Results", size="sm")
                    
                    results_display = gr.Markdown("### Results\nNo results available yet.")
                    
                    with gr.Row():
                        result_files = gr.Files(label="Download Results", interactive=False)
            
            # Event handlers
            
            # Input method toggle
            input_method.change(
                fn=self._toggle_input_method,
                inputs=[input_method],
                outputs=[upload_section, gcs_section, upload_status, gcs_status]
            )
            
            # GCS refresh button
            gcs_refresh_btn.click(
                fn=self._refresh_gcs_files,
                inputs=[gcs_bucket, gcs_prefix],
                outputs=[gcs_files, gcs_status]
            )
            
            # File upload handlers
            file1.change(
                fn=self._validate_file,
                inputs=[file1],
                outputs=[upload_status]
            )
            
            file2.change(
                fn=self._validate_file,
                inputs=[file2],
                outputs=[upload_status]
            )
            
            # Launch pipeline
            launch_btn.click(
                fn=self._launch_pipeline,
                inputs=[
                    input_method, file1, file2, 
                    gcs_bucket, gcs_prefix, gcs_files,
                    threads, min_contig_len,
                    *step_checkboxes.values()
                ],
                outputs=[launch_output, launch_btn, cancel_btn]
            )
            
            # Cancel job
            cancel_btn.click(
                fn=self._cancel_job,
                outputs=[launch_output, launch_btn, cancel_btn]
            )
            
            # Refresh status
            refresh_btn.click(
                fn=self._refresh_status,
                outputs=[job_info, pipeline_status, cost_info, vm_info]
            )
            
            # Get results
            download_btn.click(
                fn=self._get_results,
                outputs=[results_display]
            )
        
        return demo
    
    def _check_gcp_connection(self) -> str:
        """Check GCP connection status."""
        if not config.GCP_PROJECT_ID:
            return "⚠️ **GCP not configured.** Please set up your `.env` file with GCP credentials."
        
        if self.storage.bucket is None:
            return f"⚠️ **GCP configured but bucket not accessible.** Project: `{config.GCP_PROJECT_ID}`"
        
        return f"✅ **Connected to GCP** - Project: `{config.GCP_PROJECT_ID}`, Bucket: `{config.GCP_BUCKET_NAME}`"
    
    def _validate_file(self, file) -> str:
        """Validate uploaded file."""
        if file is None:
            return ""
        
        file_path = Path(file)
        size_mb = file_path.stat().st_size / (1024 * 1024)
        size_gb = size_mb / 1024
        
        if size_gb > config.MAX_FILE_SIZE_GB:
            return f"❌ File too large: {size_gb:.2f} GB (max: {config.MAX_FILE_SIZE_GB} GB)"
        
        return f"✅ File uploaded: {file_path.name} ({size_mb:.1f} MB)"
    
    def _toggle_input_method(self, method: str) -> Tuple[gr.Group, gr.Group, str, str]:
        """Toggle between upload and GCS input methods."""
        if method == "Upload from computer":
            return (
                gr.Group(visible=True),   # upload_section
                gr.Group(visible=False),  # gcs_section
                "",  # upload_status
                ""   # gcs_status
            )
        else:
            return (
                gr.Group(visible=False),  # upload_section
                gr.Group(visible=True),   # gcs_section
                "",  # upload_status
                ""   # gcs_status
            )
    
    def _refresh_gcs_files(self, bucket: str, prefix: str) -> Tuple[gr.CheckboxGroup, str]:
        """Refresh the list of files from GCS."""
        if not bucket:
            return (
                gr.CheckboxGroup(choices=[], value=[]),
                "❌ Please enter a bucket name"
            )
        
        try:
            # List files from GCS
            files = self.storage.list_gcs_files(
                bucket_name=bucket,
                prefix=prefix,
                file_extensions=config.GCS_ALLOWED_EXTENSIONS
            )
            
            if not files:
                return (
                    gr.CheckboxGroup(choices=[], value=[]),
                    f"ℹ️ No FASTQ files found in gs://{bucket}/{prefix}"
                )
            
            # Create choices with file names and sizes
            choices = [f"{f['name']} ({f['size_human_readable']})" for f in files]
            
            # Store the mapping for later use
            self.gcs_file_mapping = {
                f"{f['name']} ({f['size_human_readable']})": f['path']
                for f in files
            }
            
            return (
                gr.CheckboxGroup(choices=choices, value=[]),
                f"✅ Found {len(files)} file(s) in gs://{bucket}/{prefix}"
            )
        
        except Exception as e:
            return (
                gr.CheckboxGroup(choices=[], value=[]),
                f"❌ Error listing files: {str(e)}"
            )
    
    def _launch_pipeline(
        self,
        input_method,
        file1,
        file2,
        gcs_bucket,
        gcs_prefix,
        gcs_files,
        threads,
        min_contig_len,
        *step_flags
    ) -> Tuple[str, gr.Button, gr.Button]:
        """Launch the pipeline on GCP."""
        # Validate inputs based on method
        gcs_uri1 = None
        gcs_uri2 = None
        
        if input_method == "Upload from computer":
            # Validate uploaded files
            if file1 is None or file2 is None:
                return (
                    "❌ Please upload both forward and reverse read files.",
                    gr.Button(visible=True),
                    gr.Button(visible=False)
                )
        else:
            # Validate GCS selections
            if not gcs_files or len(gcs_files) == 0:
                return (
                    "❌ Please select files from Google Cloud Storage.",
                    gr.Button(visible=True),
                    gr.Button(visible=False)
                )
            
            # Get actual file paths from mapping
            selected_paths = []
            for f in gcs_files:
                path = self.gcs_file_mapping.get(f)
                if path is None:
                    return (
                        f"❌ Error: Could not find file path for '{f}'. Please refresh the file list.",
                        gr.Button(visible=True),
                        gr.Button(visible=False)
                    )
                selected_paths.append(path)
            
            # Validate paired files
            is_valid, forward_file, reverse_file, error_msg = validate_paired_files(selected_paths)
            
            if not is_valid:
                return (
                    f"❌ {error_msg}",
                    gr.Button(visible=True),
                    gr.Button(visible=False)
                )
            
            # Build GCS URIs
            gcs_uri1 = f"gs://{gcs_bucket}/{forward_file}"
            gcs_uri2 = f"gs://{gcs_bucket}/{reverse_file}"
        
        if not config.GCP_PROJECT_ID or not config.GCP_BUCKET_NAME:
            return (
                "❌ GCP not configured. Please set up your `.env` file.",
                gr.Button(visible=True),
                gr.Button(visible=False)
            )
        
        try:
            # Generate job ID
            self.current_job_id = f"job_{uuid.uuid4().hex[:8]}_{int(time.time())}"
            self.current_instance_name = f"pipeline-{self.current_job_id}"
            self.job_start_time = datetime.now()
            
            # Handle file inputs based on method
            if input_method == "Upload from computer":
                # Upload files to GCS (existing flow)
                blob1 = f"inputs/{self.current_job_id}/CV_1.fq.gz"
                blob2 = f"inputs/{self.current_job_id}/CV_2.fq.gz"
                
                gcs_uri1 = self.storage.upload_file(file1, blob1)
                gcs_uri2 = self.storage.upload_file(file2, blob2)
                
                if not gcs_uri1 or not gcs_uri2:
                    return (
                        "❌ Failed to upload files to GCS.",
                        gr.Button(visible=True),
                        gr.Button(visible=False)
                    )
            # else: gcs_uri1 and gcs_uri2 are already set from GCS selection
            
            # Build enabled steps dictionary
            enabled_steps = {}
            step_ids = list(config.PIPELINE_STEPS.keys())
            for i, step_id in enumerate(step_ids):
                enabled_steps[step_id] = bool(step_flags[i])
            
            # Generate startup script
            startup_script = self.launcher.generate_startup_script(
                job_id=self.current_job_id,
                input_file_1=gcs_uri1,
                input_file_2=gcs_uri2,
                threads=int(threads),
                min_contig_len=int(min_contig_len),
                enabled_steps=enabled_steps
            )
            
            # Launch VM
            machine_type = "n1-standard-16"
            instance_name = self.launcher.create_vm(
                instance_name=self.current_instance_name,
                machine_type=machine_type,
                startup_script=startup_script
            )
            
            if not instance_name:
                return (
                    "❌ Failed to launch VM on GCP.",
                    gr.Button(visible=True),
                    gr.Button(visible=False)
                )
            
            input_source = "uploaded files" if input_method == "Upload from computer" else "GCS files"
            
            return (
                f"✅ **Pipeline launched successfully!**\n\n"
                f"- **Job ID:** `{self.current_job_id}`\n"
                f"- **VM Instance:** `{instance_name}`\n"
                f"- **Machine Type:** `{machine_type}`\n"
                f"- **Input Source:** {input_source}\n"
                f"- **Input Files:** `{gcs_uri1}`, `{gcs_uri2}`\n\n"
                f"Switch to the **Monitor Progress** tab to track the pipeline.",
                gr.Button(visible=False),
                gr.Button(visible=True)
            )
        
        except Exception as e:
            return (
                f"❌ Error launching pipeline: {str(e)}",
                gr.Button(visible=True),
                gr.Button(visible=False)
            )
    
    def _cancel_job(self) -> Tuple[str, gr.Button, gr.Button]:
        """Cancel the current job."""
        if not self.current_job_id or not self.current_instance_name:
            return (
                "❌ No active job to cancel.",
                gr.Button(visible=True),
                gr.Button(visible=False)
            )
        
        try:
            success = self.monitor.cancel_job(
                self.current_job_id,
                self.current_instance_name
            )
            
            if success:
                return (
                    f"✅ Job `{self.current_job_id}` cancelled successfully.",
                    gr.Button(visible=True),
                    gr.Button(visible=False)
                )
            else:
                return (
                    f"❌ Failed to cancel job `{self.current_job_id}`.",
                    gr.Button(visible=False),
                    gr.Button(visible=True)
                )
        
        except Exception as e:
            return (
                f"❌ Error cancelling job: {str(e)}",
                gr.Button(visible=False),
                gr.Button(visible=True)
            )
    
    def _refresh_status(self) -> Tuple[str, str, str, str]:
        """Refresh the job status."""
        if not self.current_job_id or not self.current_instance_name:
            return (
                "### Job Information\nNo active job",
                self._render_pipeline_status({}),
                "### Cost Estimate\n$0.00",
                "### VM Status\nNo VM running"
            )
        
        try:
            status = self.monitor.get_job_status(
                self.current_job_id,
                self.current_instance_name
            )
            
            # Job info
            job_info = f"""### Job Information
- **Job ID:** `{self.current_job_id}`
- **Status:** {config.STATUS_EMOJIS.get(status['status'], '❓')} {status['status'].upper()}
- **Progress:** {status['progress']}%
"""
            
            if status.get('current_step'):
                step_info = config.PIPELINE_STEPS.get(status['current_step'], {})
                job_info += f"- **Current Step:** {step_info.get('emoji', '')} {step_info.get('name', status['current_step'])}\n"
            
            # Pipeline status
            pipeline_status = self._render_pipeline_status(status.get('steps', {}))
            
            # Cost estimate
            if self.job_start_time:
                cost = self.monitor.estimate_cost(
                    "n1-standard-16",
                    self.job_start_time
                )
                elapsed = datetime.now() - self.job_start_time
                cost_info = f"""### Cost Estimate
- **Elapsed Time:** {str(elapsed).split('.')[0]}
- **Estimated Cost:** ${cost:.4f}
"""
            else:
                cost_info = "### Cost Estimate\n$0.00"
            
            # VM status
            vm_info = f"""### VM Status
- **Instance:** `{self.current_instance_name}`
- **Status:** {status.get('vm_status', 'unknown')}
"""
            
            return job_info, pipeline_status, cost_info, vm_info
        
        except Exception as e:
            return (
                f"### Job Information\nError: {str(e)}",
                self._render_pipeline_status({}),
                "### Cost Estimate\n$0.00",
                "### VM Status\nError"
            )
    
    def _render_pipeline_status(self, steps: Dict) -> str:
        """Render the pipeline status as a visual flowchart."""
        status_html = "### Pipeline Progress\n\n"
        
        if not steps:
            status_html += "_No pipeline steps to display_"
            return status_html
        
        for step_id, step_info in config.PIPELINE_STEPS.items():
            step_status = steps.get(step_id, {"status": "pending", "progress": 0})
            status = step_status.get("status", "pending")
            progress = step_status.get("progress", 0)
            
            emoji = config.STATUS_EMOJIS.get(status, "⏳")
            
            status_html += f"{emoji} **{step_info['name']}** - {status.upper()} ({progress}%)\n\n"
        
        return status_html
    
    def _get_results(self) -> str:
        """Get download links for results."""
        if not self.current_job_id:
            return "### Results\nNo job has been run yet."
        
        try:
            results = self.monitor.get_results(self.current_job_id)
            
            if not results:
                return "### Results\nNo results available yet. The pipeline may still be running."
            
            results_md = "### 📥 Results Available\n\n"
            
            # Categorize results
            if 'multiqc_report' in results:
                results_md += f"#### MultiQC Report\n[📊 View Report]({results['multiqc_report']})\n\n"
            
            if 'contigs' in results:
                results_md += f"#### Assembled Contigs\n[📄 Download FASTA]({results['contigs']})\n\n"
            
            if 'pfam_annotations' in results:
                results_md += f"#### Pfam Annotations\n[🎯 Download]({results['pfam_annotations']})\n\n"
            
            if 'bins' in results:
                results_md += f"#### MetaBAT2 Bins\n[📦 Download]({results['bins']})\n\n"
            
            if 'checkm_report' in results:
                results_md += f"#### CheckM Report\n[✓ View Report]({results['checkm_report']})\n\n"
            
            # Other files
            other_files = [k for k in results.keys() 
                          if k not in ['multiqc_report', 'contigs', 'pfam_annotations', 'bins', 'checkm_report']]
            
            if other_files:
                results_md += "#### Other Files\n"
                for filename in other_files:
                    results_md += f"- [{filename}]({results[filename]})\n"
            
            return results_md
        
        except Exception as e:
            return f"### Results\n❌ Error fetching results: {str(e)}"
    
    def _get_custom_css(self) -> str:
        """Get custom CSS for the UI."""
        return """
        .header {
            text-align: center;
            padding: 2rem 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            margin-bottom: 2rem;
        }
        
        .status-box {
            padding: 1rem;
            border-radius: 8px;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
        }
        
        .upload-status {
            margin-top: 1rem;
            padding: 0.5rem;
        }
        
        .pipeline-status {
            font-family: monospace;
            background: #F8FAFC;
            padding: 1rem;
            border-radius: 8px;
        }
        """


def main():
    """Main entry point for the application."""
    app = MetagenomicsUI()
    demo = app.create_ui()
    
    demo.launch(
        server_name=config.GRADIO_SERVER_NAME,
        server_port=config.GRADIO_SERVER_PORT,
        share=config.GRADIO_SHARE,
        theme=app.theme,
        css=app.custom_css
    )


if __name__ == "__main__":
    main()
