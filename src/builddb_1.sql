
/* Contains the RAW tables */

CREATE TABLE rawdata(
       "contig" VARCHAR(32),
       "geneid" VARCHAR(32) PRIMARY KEY,
       "ftype" VARCHAR(8),
       "location" VARCHAR(32),
       "genestart" INT,
       "geneend" INT,
       "strand" VARCHAR(4),
       "annotation" VARCHAR(2048),
       "aliases" VARCHAR(2048),
       "figfam" VARCHAR(128),
       "evidence" VARCHAR(128),
       "nucseq" VARCHAR(90000),
       "aaseq" VARCHAR(30000)
       );

/* BLASTP results */
CREATE TABLE blastresults(
       "querygene" VARCHAR(128),
       "targetgene" VARCHAR(128),
       "pctid" FLOAT,
       "alnlen" INT,
       "mismatches" INT,
       "gapopens" INT,
       "querystart" INT,
       "queryend" INT,
       "substart" INT,
       "subend" INT,
       "evalue" FLOAT,
       "bitscore" FLOAT,
       FOREIGN KEY(querygene) REFERENCES rawdata(geneid),
       FOREIGN KEY(targetgene) REFERENCES rawdata(geneid)
       );

CREATE TABLE blastn_results(
       "querygene" VARCHAR(128),
       "targetgene" VARCHAR(128),
       "pctid" FLOAT,
       "alnlen" INT,
       "mismatches" INT,
       "gapopens" INT,
       "querystart" INT,
       "queryend" INT,
       "substart" INT,
       "subend" INT,
       "evalue" FLOAT,
       "bitscore" FLOAT,
       FOREIGN KEY(querygene) REFERENCES rawdata(geneid),
       FOREIGN KEY(targetgene) REFERENCES rawdata(geneid)
       );

/* abbreviation must be less than 6 characters for PHYLIP format to work correctly... */
CREATE TABLE organisms(
       "organism" varchar(128) PRIMARY KEY,
       "organismabbrev" varchar(6) UNIQUE,
       "organismid" varchar(128) UNIQUE
       );

/* I decided to reduce our memory footprint by just creating a view for
   the organism - gene links */
CREATE TABLE geneinfo(
       "geneid" VARCHAR(32),
       "organismid" VARCHAR(128),
       "organism" VARCHAR(128),
       "organismabbrev" varchar(6),
       "contig_mod" VARCHAR(256),
       "strandsign" INT,
       "aalen" INT,
       "nuclen" INT,
       FOREIGN KEY(geneid) REFERENCES rawdata(geneid),
       FOREIGN KEY(organismid) REFERENCES organisms(organismid),
       FOREIGN KEY(organism) REFERENCES organisms(organism),
       FOREIGN KEY(organismabbrev) REFERENCES organisms(organismabbrev),
       CHECK (aalen < 30000)
       );

/* Note - distance is number of genes */
CREATE TABLE neighborhoods(
       "centergene" VARCHAR(32),
       "neighborgene" VARCHAR(32),
       "distance" VARCHAR(32),
       "contig_mod" VARCHAR(256),
       "startloc" INT,
       "strand" VARCHAR(4),
       FOREIGN KEY(centergene) REFERENCES rawdata(geneid),
       FOREIGN KEY(neighborgene) REFERENCES rawdata(geneid)
       );
       

.separator "\t"
.import organisms organisms
.import db/raw_cat rawdata
.import db/mod_cat geneinfo
.import db/blastres_cat blastresults
.import db/blastnres_cat blastn_results
.import db/neighborhoods neighborhoods

CREATE INDEX blastqueryidx ON blastresults (querygene);
CREATE INDEX blasttargetidx ON blastresults (targetgene);

CREATE INDEX blastnqueryidx ON blastn_results (querygene);
CREATE INDEX blastntargetidx ON blastn_results (targetgene);

/* Add self-bit score to blastp results table */
/*CREATE TABLE blast_self AS
       SELECT * FROM blastresults 
       WHERE blastresults.querygene = blastresults.targetgene; */

CREATE TABLE blast_self AS 
       SELECT * FROM blastresults 
       INNER JOIN (
       	     SELECT querygene, targetgene, max(bitscore) AS bitscore FROM blastresults
	     WHERE querygene = targetgene
	     GROUP BY querygene
	     ) AS s
	     ON s.querygene = blastresults.querygene AND s.bitscore = blastresults.bitscore
	     WHERE blastresults.querygene = s.querygene
	     AND blastresults.targetgene = s.targetgene
	     AND blastresults.querygene = blastresults.targetgene;

/*CREATE TABLE blastn_self AS
       SELECT * FROM blastn_results 
       WHERE blastn_results.querygene = blastn_results.targetgene; */

CREATE TABLE blastn_self AS 
       SELECT * FROM blastn_results 
       INNER JOIN (
       	     SELECT querygene, targetgene, max(bitscore) AS bitscore FROM blastn_results 
	     WHERE querygene = targetgene
	     GROUP BY querygene
	     ) AS s
	     ON s.querygene = blastn_results.querygene
	     WHERE blastn_results.querygene = s.querygene
	     AND blastn_results.targetgene = s.targetgene
	     AND blastn_results.querygene = blastn_results.targetgene
	     AND s.bitscore = blastn_results.bitscore;

CREATE INDEX selfqueryidx ON blast_self(querygene);
CREATE INDEX blastnselfqueryidx ON blastn_self(querygene);

CREATE VIEW s AS
       SELECT blastresults.*, blast_self.bitscore AS queryselfbit
       FROM blastresults
       INNER JOIN blast_self ON blast_self.querygene = blastresults.querygene;

CREATE VIEW sn AS
       SELECT blastn_results.*, blastn_self.bitscore AS queryselfbit
       FROM blastn_results
       INNER JOIN blastn_self ON blastn_self.querygene = blastn_results.querygene;

CREATE TABLE blastres_selfbit AS
       SELECT s.*, blast_self.bitscore AS targetselfbit FROM s
       INNER JOIN blast_self ON blast_self.querygene = s.targetgene;


CREATE TABLE blastnres_selfbit AS
       SELECT sn.*, blastn_self.bitscore AS targetselfbit FROM sn
       INNER JOIN blastn_self ON blastn_self.querygene = sn.targetgene;

CREATE INDEX selfbitqueryidx ON blastres_selfbit(querygene);
CREATE INDEX selfbittargetidx ON blastres_selfbit(targetgene);

CREATE INDEX blastn_selfbitqueryidx ON blastnres_selfbit(querygene);
CREATE INDEX blastn_selfbittargetidx ON blastnres_selfbit(targetgene);

DROP VIEW s;
DROP VIEW sn;

/* Processed table (this is the table you should generally query against - it results in the 'geneinfo' tables):
   Gene ID | organism | organismID | organism abbreviation | contig ID | gene start | gene end | strand | annotation | nucleotide sequence | amino acid sequence 
 */

CREATE TABLE processed AS
       SELECT geneinfo.geneid, organisms.organism, organisms.organismid, organisms.organismabbrev, geneinfo.contig_mod,  
       	      rawdata.genestart, rawdata.geneend, rawdata.strand, geneinfo.strandsign, 
              rawdata.annotation, rawdata.nucseq, rawdata.aaseq
       FROM organisms
       INNER JOIN geneinfo ON geneinfo.organismid = organisms.organismid
       INNER JOIN rawdata ON geneinfo.geneid = rawdata.geneid;

CREATE INDEX processedgeneids ON processed(geneid);
CREATE INDEX processedcontigs ON processed(contig_mod);
CREATE INDEX processedorganismids ON processed(organismid);

/* These tables are no longer needed. Drop them to reduce the memory footprint and reduce confusion. */
/*DROP TABLE blastresults;
DROP TABLE blastn_results;
DROP TABLE geneinfo; */