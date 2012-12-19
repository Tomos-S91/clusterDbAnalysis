#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script plots regions around proteins using a newick tree of the proteins and the results of iTEP's db_getGeneNeighborhoods.py

Created on Wed Oct 17 12:40:42 2012

@author: jamesrh
"""

import sys, os
#TODO: remove this when put in /src
sys.path.append("/data/Cluster_Files/src") 
from locateDatabase import *

#only non-standard library dependences are ETE and BioPython (which includes reportlab with latest fonts if installed with easyinstall)
import os, sys, math, itertools, colorsys
#from tempfile import NamedTemporaryFile
import numpy as np
from reportlab.lib import colors as rcolors
from Bio.Graphics import GenomeDiagram
#from Bio import SeqIO
from Bio.SeqFeature import SeqFeature, FeatureLocation
from ete2 import Tree, faces, TreeStyle, TextFace, PhyloTree
from ete2 import Phyloxml, phyloxml
import sqlite3


#first some convienence functions
def splitrast(geneid, removefigpeg = False):
    '''takes a geneid and splits off the organiosm and gene, optionally removing the "fig" and "peg" parts'''
    fig, peg = geneid.split('.peg.')
    if removefigpeg:
        fig=fig.lstrip('fig|')
    else:
        peg = 'peg.'+peg  
    return fig, peg

def RGB_to_hex(RGBlist):
    n = lambda x: int(x*255)
    RGB256 = [(n(r),n(g),n(b)) for r,g,b in RGBlist]
    colors = ['#%02x%02x%02x' % (r, g, b) for r, g, b in RGB256]
    return colors

def colormap(valuelist):
    #generate list of divergent colors
    clusters = np.unique(valuelist)
    N = len(clusters)
    #we will vary in 2 dimensions, so this is how many steps in each
    perm = int(math.ceil(math.sqrt(N)))
    #need offset, as human's can't tell colors that are unsaturated apart
    H = [(x*1.0/perm) for x in range(perm)]
    S = [(x*1.0/perm)+0.2 for x in range(perm)]
    #we will use this to truncate at correct length
    V = [0.7]*N
    #all combanations
    HS = itertools.product(H, S)
    H, S = zip(*HS)
    HSV = zip(H,S,V)
    RGB = [colorsys.hsv_to_rgb(h,s,v) for h, s, v in HSV]
    #n = lambda x: int(x*255)
    #RGB256 = [(n(r),n(g),n(b)) for r,g,b in RGB]
    #colors = ['#%02x%02x%02x' % (r, g, b) for r, g, b in RGB256]
    colorlookup = dict(zip(clusters, RGB[:N]))
    return colorlookup

def get_region_info(genename, clusterrunid):
    outdata = getGeneNeighborhoods(genename, clusterrunid)    
    genelocs = []
    for neargene in outdata: 
        neargeneid = neargene[1]
        strandsign = neargene[5]
        if strandsign =='-': strand = -1
        if strandsign =='+': strand = +1
        start = neargene[7]
        stop  = neargene[8]
        feature = SeqFeature(FeatureLocation(start, stop), strand=strand, id = neargeneid)
        feature.type = neargene[9]
        genelocs.append(feature)
    return genelocs

def getDataFromList(geneids):
    """returns a dictionary of data from the processed table)"""
    con = sqlite3.connect(locateDatabase())
    cur = con.cursor()
    sql = "SELECT geneid, organism, annotation FROM processed WHERE geneid IN ({seq}) AND runid = ?;".format(seq=','.join(['?']*len(geneids)))
    cur.execute(sql, geneids)    
    lookupcluster = dict(cur.fetchall())
    con.close()
    return lookupcluster

def getdata(geneid):
    con = sqlite3.connect(locateDatabase())
    cur = con.cursor()
    sql = "SELECT geneid, organism, annotation FROM processed WHERE geneid == ?;"
    cur.execute(sql, (geneid,))
    data  = dict(cur.fetchall()[0])
    con.close()
    return data

def OrgnameToOrgID(orgid):
    #drop begining
    orgid = orgid.lstrip("fig|")
    con = sqlite3.connect(locateDatabase())
    cur = con.cursor()
    sql = "SELECT organism FROM organisms WHERE organismid == ?;"
    cur.execute(sql, (orgid,))
    data,  = cur.fetchall()[0]
    con.close()
    return data

def GetGeneToAlias():
    geneToAlias ={}
    rootpath = os.path.split(os.path.split(locateDatabase())[0])[0]
    for line in open(os.path.join(rootpath,'aliases','aliases'), "r"):
        spl = line.strip('\r\n').split("\t")
        geneToAlias[spl[0]] = spl[1]
    return geneToAlias


def removeleadingdashes(t):
    tblastnadded = []
    for genename in t.get_leaf_names():
        #if it is from tblastn, we want to change it in the tree and have a record to indecate this in the plot
        if genename.startswith('-'): 
            tblastn_leaf = t&genename
            genename = genename.lstrip('-')
            tblastnadded.append(genename)
            tblastn_leaf.name = genename
    return t, tblastnadded


def getGeneNeighborhoods(geneid, clusterrunid):
    """from Matt's file of the same name"""
    con = sqlite3.connect(locateDatabase())
    cur = con.cursor()
    cur.execute("""SELECT neighborhoods.*, processed.annotation, processed.genestart, processed.geneend FROM neighborhoods
                   INNER JOIN processed ON processed.geneid = neighborhoods.neighborgene
                   WHERE neighborhoods.centergene=?;""", (geneid,))
    results = cur.fetchall()
    geneids = [l[1] for l in results]
    #want to do an IN query, but need to format w. correct number of ?s, so generate this string
    sql = "SELECT geneid, clusterid FROM clusters WHERE geneid IN ({seq}) AND runid = ?;".format(seq=','.join(['?']*len(geneids)))
    geneids.append(clusterrunid)
    cur.execute(sql, geneids)    
    lookupcluster = dict(cur.fetchall())
    con.close()
    outdata = [l + (lookupcluster[l[1]],) for l in results]
    return outdata

def info_from_regions(regionindex, characteristic, restrict_region=False):
    charictaristics = []
    if restrict_region:
        regionindex = {restrict_region:regionindex[restrict_region]}
    for region in regionindex.values():
        for gene in region:
            charictaristics.append(gene.__dict__[characteristic])
    return charictaristics

def regionlength(genelocs):
    location = [(int(loc.location.start), int(loc.location.end)) for loc in genelocs]
    starts, ends = zip(*location)
    #have to compare both, as some are reversed
    start = max(max(starts),max(ends))
    end = min(min(starts),min(ends))
    return start, end

def make_region_drawing(genelocs, getcolor, centergenename, maxwidth):
    #TODO make auto-del tempfiles, or pass svg as string
    geneToAlias = GetGeneToAlias()
    org, peg = splitrast(centergenename, removefigpeg = True)
    gd_diagram = GenomeDiagram.Diagram("Genome Region")#TODOis title req?
    gd_track_for_features = gd_diagram.new_track(1, name="Annotated Features")
    gd_feature_set = gd_track_for_features.new_set()
    for feature in genelocs:
        bordercol=rcolors.white
        if feature.id == centergenename:
            bordercol=rcolors.red
            centerdstart, centerend = int(feature.location.start), int(feature.location.end)
            centerdstrand = feature.strand
        color = getcolor[feature.type]
        #make labels bigger if they are gennames
        size = 20
        thisorg, thispeg = splitrast(feature.id, removefigpeg = True)
        try: 
            thispeg = geneToAlias[feature.id]
        except KeyError: 
            pass
        else: 
            size = 25
        gd_feature_set.add_feature(feature, name = thispeg, 
                                   color=color, border = bordercol, 
                                   sigil="ARROW", arrowshaft_height=1.0,
                                   label=True,  label_angle=20, label_size = size
                                   )    
    start, end = regionlength(genelocs)
    scale = 20 #BP per px
    pagew_px = maxwidth / scale
    #offset so start of gene of interest lines up
    midcentergene = abs(centerend - centerdstart)/2 + min(centerdstart, centerend)
    l2mid = abs(midcentergene - start)
    r2mid = abs(midcentergene - end)
    roffset = float((pagew_px/2) - (l2mid/scale)) #one px = 20 BP
    loffset = float((pagew_px/2) - (r2mid/scale))

    gd_diagram.draw(format="linear", start=start, end=end, fragments=1, pagesize=(225, pagew_px), xl=(loffset/pagew_px), xr=(roffset/pagew_px) )
    imgfileloc = "/tmp/" + str(org) + str(peg) + imgfilename
    gd_diagram.write(imgfileloc, "PNG")
    #flip for reversed genes
    if centerdstrand == -1:
        os.system("convert -rotate 180 %s %s" % (imgfileloc, imgfileloc))

def draw_tree_regions(clusterrunid, t, ts):
    # first, get all genes around these genes (id is gene name, cluster number is type
    regionindex={}
    t, tblastnadded = removeleadingdashes(t)
    for genename in t.get_leaf_names():
        #this does a nested SQL lookup, so is slow
        regionindex[genename]= get_region_info(genename, clusterrunid)
    # set up the colormap from all of the unique clusters found in all genes in the tree
    #clusters = list(set(info_from_regions(regionindex, 'type')))
    #only have color for those that appere more than one time (to do all, rever to previous line)
    allclusters = info_from_regions(regionindex, 'type')
    uniqueclusters = list(set(allclusters))
    greyout = 3 #will be grey if they appere less than this many times
    multipleclusters = [c for c in uniqueclusters if allclusters.count(c) > greyout]
    getcolor = colormap(multipleclusters)
    #also add in grey for all others
    singleclusters = [c for c in uniqueclusters if allclusters.count(c) <= greyout]
    getcolor.update([(sc, (0.5,0.5,0.5)) for sc in singleclusters])
    #generate the region images for any leaf that has them, and map onto the tree
    #we will want to know the max width to make the figures
    widths = []
    for genelocs in regionindex.values():
        start, end = regionlength(genelocs)
        widths.append(abs(end - start))
    maxwidth = max(widths)
    for leaf in t.iter_leaves():
        try: genelocs = regionindex[leaf.name]
        except KeyError: continue #this is needed for when we want to put this on a gene tree
        make_region_drawing(genelocs, getcolor, leaf.name, maxwidth)
        org, peg = splitrast(leaf.name, removefigpeg = True)
        imageFace = faces.ImgFace(str(org) + str(peg) + imgfilename)
        leaf.add_face(imageFace, column=2, position = 'aligned')
        if leaf.name in tblastnadded:
            leaf.add_face(TextFace("TBlastN added", fsize=30), column=3, position = 'aligned')
    #add legend for clusters
    ts = treelegend(ts, getcolor, greyout)
    return t, ts

def treelegendtext(cluster, color):
    text = TextFace(" %s " % cluster)
    text.hz_align = False
    text.fsize = 30
    text.fstyle = 'Bold'
    text.background.color = color
    return text

def treelegend(ts, getcolor, greyout):
    #needs hex, not 0 to 1 RGB, this function wants a list so unpack and pack  back up
    clusters, colors = zip(*getcolor.items())
    colors = RGB_to_hex(colors)
    colorlist = zip(clusters, colors)
    colorlist.sort()
    greynum = len([uc for uc, color in colorlist if color == '#7f7f7f'])
    greycols =  int(math.ceil(math.sqrt(greynum)))#to make close to a box
    colornum = len(colorlist) - greynum
    colorcols =  int(math.ceil(math.sqrt(colornum)))#because the color palate varies in 2 dimensions this will make a box with the H and S indexed
    #put legend with colors at bottom to display cluster IDs.
    ts.legend_position=1
    gnum = 0
    cnum = 0
    for cluster, color in colorlist:
        #drop grey ones
        if color == '#7f7f7f': 
            #offset the greys
            col = (gnum%greycols) + colorcols + 1 + 1 #offset from colors and grey def
            gnum += 1
        else:             
            col = cnum%colorcols
            cnum += 1
        text = treelegendtext(cluster, color)
        #placement of this legend
        ts.legend.add_face(text, column=col)
    ts.legend.add_face(treelegendtext("> %s occurrences        < or = %s occurrences " % (greyout, greyout),'#FFFFFF'), column=colorcols + 1)
    return ts

def prettytree(t, ts, title=None):
    #from Matt's iTol db_displayTree.py
    for node in t.traverse():
        if node.is_leaf():
            if node.species == 'fig|190192.1':
                t.set_outgroup(node)
            # Add an annotation text with larger font to replace the crappy size-10 ish font that comes by default...
            #newname = "_".join( [ node.name, geneToOrganism[node.name], geneToAnnote[node.name] ] )
            orgname = node.species
            F = faces.TextFace(node.name, ftype="Times", fsize=30)
            node.add_face(F, 0, position="aligned")
            try: 
                F = faces.TextFace(OrgnameToOrgID(orgname), ftype="Times", fsize=30)
            except IndexError: 
                pass
            node.add_face(F, 1, position="aligned")
        else:
            # Make the branch support bigger
            F = faces.TextFace(node._support, ftype="Times", fsize=20, fgcolor = 'red')
            node.add_face(F, 0, position="branch-top")

    t.ladderize(direction=0)
    
    # Ladderize doesn't always break ties the same way. Lets fix that, shall we?
    # I break ties according to the names of leaves descended from a given node.
    # Essentially this amounts to sorting first by number of branches and then by alphabetical order
    for node in t.traverse(strategy="levelorder"):
        if not node.is_leaf():
            children = node.get_children()
            #print children
            if not len(children) == 2:
                sys.stderr.write("WARNING: Node found with more than two children... Should always have 2 children per node?\n")
                continue
            nl0 = len(children[0].get_leaves())
            nl1 = len(children[1].get_leaves())
            if nl0 == nl1:
                names0 = "".join(sorted(children[0].get_leaf_names()))
                names1 = "".join(sorted(children[1].get_leaf_names()))
                if names0 > names1:
                    node.swap_children()
    #correct the long root node bug (fixed in next release)
    t.dist=0
    ts.show_branch_support = False
    ts.show_leaf_name = False
    #ts.draw_guiding_line = True
    #overall title
    #remove previous
    ts.title.clear()
    title = TextFace(title)
    title.hz_align = True
    title.fsize = 52
    ts.title.add_face(title, 0)
    return t, ts

# parsing function to extract species names for all nodes in a given tree.
def parse_sp_name(node_name):
    if node_name=='NoName':
        pass
    if node_name.count("peg") == 0:# then it is an organism tree?
        orgname = node_name
    else: 
        orgname = splitrast(node_name, removefigpeg=False)[0]
    return orgname

if __name__=="__main__":
    usage="%prog -p protein_tree [options]"
    description="""Generates a tree with gene regions"""
    parser = optparse.OptionParser(usage=usage, description=description)
    parser.add_option("-r", "--runid", help="Only print results for the specified run ID (D: Prints the table for all of them)", action="store", type="str", dest="clusterrunid", default=None)
    parser.add_option("-p", "--prottree", help="Protein tree", action="store", type="str", dest="treeinfile", default=None)
    parser.add_option("-o", "--orgtree", help="Organism tree", action="store", type="str", dest="cattreeinfile", default=None)
    parser.add_option("-t", "--treetitle", help="Tree title", action="store", type="str", dest="gene", default=None)
    (options,args) = parser.parse_args()

    if options.treeinfile is None:
        sys.stderr.write("ERROR: -p (protein input tree) is required\n")
        exit(2)

    #global variables
    clusterrunid = options.clusterrunid
    treeinfile = options.treeinfile 
    cattreeinfile = options.cattreeinfile 
    #cat VhtA_genes_3.fasta.tblastn.fas.aln|sed "s/\(>-*[^ ]*\).*/\1/g">VhtA_genes_3.fasta.tblastn.fas.fig.aln
    #cat VhtA_genes_3.fasta.tblastn.fas.aln|sed "s/>-*\([^ ]*\).*/>\1/g">VhtA_genes_3.fasta.tblastn.fas.fig.aln 
    gene = options.gene 
    
    imgfilename = "_temp.png"
    t = PhyloTree(treeinfile, sp_naming_function=parse_sp_name)
    ts = TreeStyle()
    ts.show_leaf_name = False
    t, ts = draw_tree_regions(clusterrunid, t, ts)
    t, ts = prettytree(t, ts, title = gene + " cluster regions")
    #t.show(tree_style=ts)
    os.system("rm test.svg 2> /dev/null")
    t.render("%s_region_tree.svg" % gene, tree_style=ts)
    os.system("convert -trim -depth 32 -background transparent %s_region_tree.svg %s_cluster_tree.png" %(gene, gene))

