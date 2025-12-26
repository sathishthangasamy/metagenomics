
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

# Execution

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


