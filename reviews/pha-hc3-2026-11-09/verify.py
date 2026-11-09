"""Recheck released PHA evaluation data; no LLM generation or historical GLMM replay."""
import argparse, hashlib, io, json, math, platform, re, zipfile
from pathlib import Path
import pandas as pd
import scipy
from scipy.stats import chi2, wilcoxon, binomtest

p=argparse.ArgumentParser()
p.add_argument('--data-zip',required=True,type=Path)
p.add_argument('--supplement-text',required=True,type=Path,help='pdftotext -layout output from the published supplement')
p.add_argument('--output',default='results.json',type=Path)
a=p.parse_args()
z=zipfile.ZipFile(a.data_zip)
def frame(name):
    hits=[n for n in z.namelist() if Path(n).name==name and not n.startswith('__MACOSX/')]
    if len(hits)!=1: raise ValueError((name,hits))
    return pd.read_csv(io.BytesIO(z.read(hits[0])))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
text=a.supplement_text.read_text()
match=re.search(r'Context Clarification \(Priorities, Constraints\) \(HC3\)[^\n]*?([\d.]+)\s+Z=([\d.]+)\s+<0.001',text)
if match is None: raise ValueError('HC3 source row not found; inspect PDF and extracted text')
beta,reported_z=map(float,match.groups())
x=frame('hc_task2_comparison.csv')
x=x[x.rubrics=='Context Clarification (Priorities, Constraints) (HC3)'].copy()
assert len(x)>0 and set(x.winner)=={'agent','base'}
assert not x.duplicated(['rater_id','user_script_id']).any()
n=len(x); wins=int(x.winner.eq('agent').sum()); failures=n-wins
script_counts=x.assign(win=x.winner.eq('agent').astype(int)).groupby('user_script_id').win.sum()
if not (x.groupby('user_script_id').size()==3).all():
    raise ValueError('Expected three ratings per script for this sensitivity check')
# Under a sharp system-label exchangeability null, swap all three outcomes within
# each script together. Convolution counts all 2^31 assignments without sampling.
distribution={0:1}
for k in script_counts:
    next_distribution={}
    for total,frequency in distribution.items():
        for choice in (int(k),3-int(k)):
            next_distribution[total+choice]=next_distribution.get(total+choice,0)+frequency
    distribution=next_distribution
permutation_n=2**len(script_counts)
permutation_extreme=sum(freq for total,freq in distribution.items()
                        if total>=wins or total<=n-wins)
mcq=frame('de_task1_mcq.csv'); b=int(((mcq.agent_accuracy==1)&(mcq.base_accuracy==0)).sum()); c=int(((mcq.agent_accuracy==0)&(mcq.base_accuracy==1)).sum()); stat=(abs(b-c)-1)**2/(b+c)
d=frame('de_task2_ddx_predictions.csv');assert not d.isna().any().any()
w=wilcoxon(d.agent_rank,d.base_rank,zero_method='wilcox',correction=False,alternative='two-sided',method='approx')
crude_beta=math.log(wins/failures); crude_se=math.sqrt(1/wins+1/failures)
out={
 'status':'NOT_ENOUGH_INFO / HOLD: published HC3 GLMM statistic unresolved; no confirmed error or corrected fit',
 'runtime':{'python':platform.python_version(),'pandas':pd.__version__,'scipy':scipy.__version__},
 'provenance':{'data_zip_sha256':sha(a.data_zip),'supplement_text_sha256':sha(a.supplement_text),'csv_sha256':{Path(k).name:hashlib.sha256(z.read(k)).hexdigest() for k in z.namelist() if Path(k).name in ['hc_task2_comparison.csv','de_task1_mcq.csv','de_task2_ddx_predictions.csv'] and not k.startswith('__MACOSX/')}},
 'HC3':{'n_ratings':n,'agent_wins':wins,'base_wins':failures,'agent_win_rate':wins/n,'n_raters':int(x.rater_id.nunique()),'n_scripts':int(x.user_script_id.nunique()),'ratings_per_rater':sorted(map(int,x.groupby('rater_id').size())),'ratings_per_script':sorted(set(map(int,x.groupby('user_script_id').size()))),'scripts_by_agent_win_count':{str(k):int(v) for k,v in script_counts.value_counts().sort_index().items()},'reported_beta':beta,'reported_Z':reported_z,'implied_SE_if_Wald_Z':beta/reported_z},
 'diagnostic_only_not_published_GLMM':{'model':'independent unweighted Bernoulli intercept-only logit; ignores script/rater dependence','log_odds':crude_beta,'SE':crude_se,'Wald_Z':crude_beta/crude_se,'two_sided_exact_binomial_p':float(binomtest(wins,n,0.5).pvalue),'interpretation':'Diagnostic scale comparison only; cannot replace the published GLMM or establish its multiplicity-adjusted inference.'},
 'script_block_label_swap_sensitivity':{'null':'Within each script, exchange agent/base labels for all three ratings together; scripts independent and exchangeable under the sharp null','allocations':permutation_n,'two_sided_extreme_allocations':permutation_extreme,'two_sided_p':permutation_extreme/permutation_n,'limitation':'Exact for stated exchangeability null, not a replay of the mixed model or a substitute for rater and script random effects.'},
 'matching_controls':{'MCQ':{'n':len(mcq),'agent_only':b,'base_only':c,'continuity_corrected_McNemar_chi2':stat,'p':float(chi2.sf(stat,1))},'DDx':{'n':len(d),'Wilcoxon_W':float(w.statistic),'p':float(w.pvalue)}},
 'not_performed':['historical HC3 GLMM replay','LLM output regeneration','independent human adjudication','proof of transcription or fitting error','assessment of changed substantive conclusions']}
a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
