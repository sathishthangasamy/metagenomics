# 🧬 Metagenomics Analysis Pipeline

A comprehensive metagenomics pipeline with a modern web UI for analyzing metagenomic samples on Google Cloud Platform.

## Required Tools


- [x] Fastqc & Multiqc
- [x] Trimmomatic
- [x] megahit
- [x] quast.py
- [x] prodigal
- [x] hmmscan
- [x] bowtie2
- [x] samtools
- [x] metabat2
- [x] checkM

All the above tools are present in dockerfile.

## Basic Plan

* Input paired fq.gz file
* preprocessing fastqc for quality check
* Trimmomatic for splicing unwanted sequence
* re-do the fastqc after splicing the unwanted.
* perform assembly using megahit2
	* Input will be output of trimmomatic 
* perform prodigal
	* Input will be contig file output of megahit2
	* Ouptut: .faa, .fna, .gff
* perform hmmscan with passing pfam two ids ending 36, 19
	* Input will .faa from prodigal output
	* Output will be in table
* Extract Unique IDs from the hmmscan output
* Extract same Ids from .faa file.
* Use .faa filter with pfam annotation.

# 🚀 Web UI (New!)

We now offer a modern, user-friendly web interface powered by Gradio that allows you to run the entire metagenomics pipeline on Google Cloud Platform without manual command-line operations.

## Features

- **🎨 Futuristic Light Theme** - Clean, modern interface
- **📤 Easy File Upload** - Drag & drop your FASTQ files
- **⚙️ Configurable Pipeline** - Enable/disable steps, adjust parameters
- **☁️ Cloud-Powered** - Runs on Google Cloud Platform VMs
- **📊 Real-time Monitoring** - Track pipeline progress live
- **💰 Cost Tracking** - See estimated costs in real-time
- **📥 Easy Results Download** - Download all results with one click

## Quick Start

### 1. Set Up GCP Credentials

1. Create a GCP project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the following APIs:
   - Compute Engine API
   - Cloud Storage API
3. Create a service account with the following roles:
   - Compute Admin
   - Storage Admin
4. Download the service account key JSON file
5. Create a Cloud Storage bucket for storing data

### 2. Configure Environment

Copy the example environment file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env` with your GCP credentials:

```
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=your-metagenomics-bucket
GCP_ZONE=us-central1-a
GCP_SERVICE_ACCOUNT_KEY=path/to/service-account-key.json
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Web UI

```bash
python ui/app.py
```

The web interface will be available at `http://localhost:7860`

## Using the Web UI

1. **Upload Samples**: Upload your paired-end FASTQ files (.fq.gz or .fastq.gz)
2. **Configure Pipeline**: Adjust thread count, minimum contig length, and select pipeline steps
3. **Launch**: Click "🚀 Launch Pipeline" to start the analysis on GCP
4. **Monitor**: Switch to the "Monitor Progress" tab to track the pipeline
5. **Download Results**: Once complete, download results from the "Results" tab

## Deploy to Hugging Face Spaces (Free Hosting)

You can deploy this UI to Hugging Face Spaces for free:

1. Create an account at [huggingface.co](https://huggingface.co)
2. Create a new Space with Gradio SDK
3. Upload all files from this repository
4. Add your GCP credentials as Space secrets:
   - `GCP_PROJECT_ID`
   - `GCP_BUCKET_NAME`
   - `GCP_ZONE`
   - `GCP_SERVICE_ACCOUNT_KEY` (paste the JSON content)
5. The app will automatically launch!

## Cost Estimates

Running the pipeline on GCP with preemptible VMs:

- **Small samples (< 5GB)**: $0.50 - $2.00 per run
- **Medium samples (5-15GB)**: $2.00 - $5.00 per run
- **Large samples (15-30GB)**: $5.00 - $15.00 per run

Costs include:
- Compute Engine (preemptible VMs)
- Cloud Storage (data storage and transfer)

## Supported File Formats

- Forward reads: `.fq.gz` or `.fastq.gz`
- Reverse reads: `.fq.gz` or `.fastq.gz`
- Maximum file size: 30GB per file

## Pipeline Steps

The web UI supports the following pipeline steps:

1. **FastQC** - Quality control on raw reads
2. **Trimmomatic** - Adapter trimming and quality filtering
3. **MEGAHIT** - Metagenomic assembly
4. **Prodigal** - Gene prediction
5. **HMMscan (Pfam)** - Protein domain annotation
6. **MetaBAT2** - Genome binning
7. **CheckM** - Bin quality assessment

## Results

After completion, you can download:

- MultiQC Report (HTML)
- Assembled Contigs (FASTA)
- Predicted Genes (FAA, FNA, GFF)
- Pfam Annotations
- Genome Bins
- CheckM Quality Report
- All results as a ZIP file

---

# Manual Execution (Docker)

If you prefer to run the pipeline manually using Docker:

- `git clone https://github.com/Sathish-30/metagenomics.git`
- `cd metagenomics`
- `docker build -t metagenomics .`
- `docker run --rm -it metagenomics:latest bash`
- `apt-get install -y seqkit parallel vim`
- And follow below step commands.

## FastQC

```
## Command
mkdir -p /data/fastqc_output/
time fastqc -t 8 -o /data/fastqc_output/ /data/CV_1.fq.gz /data/CV_2.fq.gz

## Time taken
34 Minutes

## File Size
CV_1.fq.gz -> 2.2GB
CV_2.fq.gz -> 2.3GB

## Output
CV_1_fastqc.html
CV_1_fastqc.zip
CV_2_fastqc.html
CV_2_fastqc.zip
```

## Trimmomatic

```
## Reference .fa file path
/usr/share/trimmomatic/TruSeq3-PE.fa

## Command
mkdir -p /data/trimmomatic_output/
time TrimmomaticPE -threads 8   /data/CV_1.fq.gz /data/CV_2.fq.gz   /data/trimmomatic_output/CV_1_paired.fq.gz /data/trimmomatic_
output/CV_1_unpaired.fq.gz   /data/trimmomatic_output/CV_2_paired.fq.gz /data/trimmomatic_output/CV_2_unpaired.fq.gz   ILLUMINACLIP:/usr/share/trimmomatic/TruSeq3-PE.fa:2:30:10   LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15 MINLEN:36

## Time Taken
21 Minutes

## Output
CV_1_paired.fq.gz  
CV_1_unpaired.fq.gz  
CV_2_paired.fq.gz  
CV_2_unpaired.fq.gz

## LOG
Input Read Pairs: 29642040 Both Surviving: 28957449 (97.69%) Forward Only Surviving: 478160 (1.61%) Reverse Only Surviving: 156063 (0.53%) Dropped: 50368 (0.17%)

```

## Post Process FastQC

```
## Command
mkdir -p /data/post_fastqc_output/
time fastqc -t 8 -o /data/post_fastqc_output/ /data/trimmomatic_output/CV_1_paired.fq.gz /data/trimmomatic_output/CV_2_paired.fq.
gz

## Output
CV_1_paired_fastqc.html  
CV_1_paired_fastqc.zip  
CV_2_paired_fastqc.html  
CV_2_paired_fastqc.zip

## Time taken
5 Minutes
```

## Megahit

```
## Command
mkdir -p /tmp/megahit_output/
time megahit -1 /data/trimmomatic_output/CV_1_paired.fq.gz -2 /data/trimmomatic_output/CV_2_paired.fq.gz -t 16 --min-contig-len 1000 -o /tmp/megahit_output/

## Output
checkpoints.txt  
final.contigs.fa      
log
done             
intermediate_contigs  
options.json

## Output Size 
12.5GB

## Note
- Remove /tmp/intermediate_contigs folder to free up space

## Time taken
6 Hours
```


## Prodigal

```
## Command
mkdir -p /data/prodigal_output /data/splits

seqkit split -p 8 /tmp/megahit_output/final.contigs.fa -O /data/splits

time parallel -j 8 'prodigal -i {} -a /data/prodigal_output/{/.}.faa -d /data/prodigal_output/{/.}.fna -f gff -o /data/prodigal_output/{/.}.gff -p meta' ::: splits/*.fa

mkdir -p /data/merged_prodigal_output

cat /data/prodigal_output/*.faa > /data/merged_prodigal_output/proteins.faa
cat /data/prodigal_output/*.fna >  /data/merged_prodigal_output/genes.fna
cat /data/prodigal_output/*.gff >  /data/merged_prodigal_output/prodigal.gff

## Output
genes.fna  
prodigal.gff  
proteins.faa

## Output Size 
500MB

## Time Taken
12 Minutes
```


