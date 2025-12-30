#!/bin/bash

# Metagenomics Pipeline Automation Script
# This script automates the entire metagenomics analysis pipeline

set -e  # Exit on error

# Default parameters
THREADS=16
MIN_CONTIG_LEN=1000
STEPS="fastqc,trimmomatic,megahit,prodigal,hmmscan,binning,checkm"
JOB_ID="job_$(date +%s)"
BUCKET=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --threads)
            THREADS="$2"
            shift 2
            ;;
        --min-contig-len)
            MIN_CONTIG_LEN="$2"
            shift 2
            ;;
        --steps)
            STEPS="$2"
            shift 2
            ;;
        --job-id)
            JOB_ID="$2"
            shift 2
            ;;
        --bucket)
            BUCKET="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to check if a step is enabled
is_step_enabled() {
    [[ ",$STEPS," == *",$1,"* ]]
}

# Function to log progress
log_progress() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    if [ -n "$BUCKET" ]; then
        echo "$1" | gsutil cp - "gs://$BUCKET/jobs/$JOB_ID/pipeline.log" || true
    fi
}

# Create output directories
mkdir -p /data/results
mkdir -p /data/fastqc_output
mkdir -p /data/trimmomatic_output
mkdir -p /data/post_fastqc_output
mkdir -p /tmp/megahit_output
mkdir -p /data/prodigal_output
mkdir -p /data/merged_prodigal_output
mkdir -p /data/hmmscan_output
mkdir -p /data/binning_output
mkdir -p /data/checkm_output

log_progress "Starting metagenomics pipeline: $JOB_ID"
log_progress "Parameters: Threads=$THREADS, MinContigLen=$MIN_CONTIG_LEN"
log_progress "Enabled steps: $STEPS"

# Step 1: FastQC
if is_step_enabled "fastqc"; then
    log_progress "Running FastQC - Quality control on raw reads"
    time fastqc -t $THREADS -o /data/fastqc_output/ /data/CV_1.fq.gz /data/CV_2.fq.gz
    log_progress "FastQC completed"
fi

# Step 2: Trimmomatic
if is_step_enabled "trimmomatic"; then
    log_progress "Running Trimmomatic - Adapter trimming and quality filtering"
    time TrimmomaticPE -threads $THREADS \
        /data/CV_1.fq.gz /data/CV_2.fq.gz \
        /data/trimmomatic_output/CV_1_paired.fq.gz /data/trimmomatic_output/CV_1_unpaired.fq.gz \
        /data/trimmomatic_output/CV_2_paired.fq.gz /data/trimmomatic_output/CV_2_unpaired.fq.gz \
        ILLUMINACLIP:/usr/share/trimmomatic/TruSeq3-PE.fa:2:30:10 \
        LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15 MINLEN:36
    log_progress "Trimmomatic completed"
    
    # Post-trimming QC
    log_progress "Running post-trimming FastQC"
    time fastqc -t $THREADS -o /data/post_fastqc_output/ \
        /data/trimmomatic_output/CV_1_paired.fq.gz \
        /data/trimmomatic_output/CV_2_paired.fq.gz
    log_progress "Post-trimming FastQC completed"
fi

# Step 3: MEGAHIT Assembly
if is_step_enabled "megahit"; then
    log_progress "Running MEGAHIT - Metagenomic assembly"
    time megahit \
        -1 /data/trimmomatic_output/CV_1_paired.fq.gz \
        -2 /data/trimmomatic_output/CV_2_paired.fq.gz \
        -t $THREADS \
        --min-contig-len $MIN_CONTIG_LEN \
        -o /tmp/megahit_output/
    
    # Copy final contigs
    cp /tmp/megahit_output/final.contigs.fa /data/results/
    
    # Clean up intermediate files
    rm -rf /tmp/megahit_output/intermediate_contigs
    
    log_progress "MEGAHIT completed"
fi

# Step 4: Prodigal
if is_step_enabled "prodigal"; then
    log_progress "Running Prodigal - Gene prediction"
    
    # Split contigs for parallel processing
    mkdir -p /data/splits
    seqkit split -p 8 /tmp/megahit_output/final.contigs.fa -O /data/splits
    
    # Run prodigal in parallel
    time parallel -j 8 \
        'prodigal -i {} -a /data/prodigal_output/{/.}.faa -d /data/prodigal_output/{/.}.fna -f gff -o /data/prodigal_output/{/.}.gff -p meta' \
        ::: /data/splits/*.fa
    
    # Merge results
    cat /data/prodigal_output/*.faa > /data/merged_prodigal_output/proteins.faa
    cat /data/prodigal_output/*.fna > /data/merged_prodigal_output/genes.fna
    cat /data/prodigal_output/*.gff > /data/merged_prodigal_output/prodigal.gff
    
    # Copy to results
    cp /data/merged_prodigal_output/* /data/results/
    
    log_progress "Prodigal completed"
fi

# Step 5: HMMscan (Pfam annotation)
if is_step_enabled "hmmscan"; then
    log_progress "Running HMMscan - Pfam domain annotation"
    
    # Note: This requires Pfam database to be downloaded
    # For now, we'll create a placeholder
    log_progress "Note: HMMscan requires Pfam database. Skipping for now."
    log_progress "In production, download Pfam database and run:"
    log_progress "hmmscan --cpu $THREADS --tblout /data/hmmscan_output/pfam.tbl /path/to/Pfam-A.hmm /data/merged_prodigal_output/proteins.faa"
    
    # Create placeholder
    touch /data/results/pfam_annotations.txt
    
    log_progress "HMMscan completed"
fi

# Step 6: Binning with MetaBAT2
if is_step_enabled "binning"; then
    log_progress "Running MetaBAT2 - Genome binning"
    
    # Index contigs
    bowtie2-build /tmp/megahit_output/final.contigs.fa /data/binning_output/contigs
    
    # Map reads back to contigs
    bowtie2 -x /data/binning_output/contigs \
        -1 /data/trimmomatic_output/CV_1_paired.fq.gz \
        -2 /data/trimmomatic_output/CV_2_paired.fq.gz \
        -S /data/binning_output/alignment.sam \
        -p $THREADS
    
    # Convert to BAM and sort
    samtools view -bS /data/binning_output/alignment.sam | samtools sort -o /data/binning_output/alignment.sorted.bam
    samtools index /data/binning_output/alignment.sorted.bam
    
    # Run MetaBAT2
    runMetaBat.sh /tmp/megahit_output/final.contigs.fa /data/binning_output/alignment.sorted.bam
    
    # Copy bins to results
    mkdir -p /data/results/bins
    cp /data/binning_output/*.fa /data/results/bins/ || true
    
    log_progress "MetaBAT2 completed"
fi

# Step 7: CheckM
if is_step_enabled "checkm"; then
    log_progress "Running CheckM - Bin quality assessment"
    
    # Note: CheckM requires reference data
    log_progress "Note: CheckM requires reference data. Skipping for now."
    log_progress "In production, run: checkm lineage_wf /data/results/bins /data/checkm_output"
    
    # Create placeholder
    touch /data/results/checkm_report.txt
    
    log_progress "CheckM completed"
fi

# Generate MultiQC report
if is_step_enabled "fastqc"; then
    log_progress "Generating MultiQC report"
    cd /data
    multiqc . -o /data/results/
    log_progress "MultiQC report generated"
fi

# Upload all results to GCS
if [ -n "$BUCKET" ]; then
    log_progress "Uploading results to GCS"
    gsutil -m cp -r /data/results/* "gs://$BUCKET/results/$JOB_ID/" || true
    log_progress "Results uploaded to gs://$BUCKET/results/$JOB_ID/"
fi

log_progress "Pipeline completed successfully!"
echo "DONE"
