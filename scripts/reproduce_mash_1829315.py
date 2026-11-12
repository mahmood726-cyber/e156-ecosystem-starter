#!/usr/bin/env python3
"""Reproduce bounded arithmetic from one public source-transcribed case file."""
import json, math, sys
from decimal import Decimal
from pathlib import Path

def main(path):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    c,f=d["ci"],d["flow"]
    rr,lo,hi=(Decimal(str(c[k])) for k in ("reported_rr","reported_lower","reported_upper"))
    half=Decimal(5).scaleb(-c["printed_decimals"]-1)
    rr_interval=[rr-half,rr+half]
    midpoint_interval=[((lo-half)*(hi-half)).sqrt(),((lo+half)*(hi+half)).sqrt()]
    disjoint=midpoint_interval[0]>rr_interval[1] or midpoint_interval[1]<rr_interval[0]
    out={
      "case_id":d["case_id"],
      "ci_geometric_midpoint":math.sqrt(float(lo*hi)),
      "ci_log_halfwidths":[math.log(float(rr/lo)),math.log(float(hi/rr))],
      "printed_rounding_cannot_restore_log_symmetry":disjoint,
      "log_symmetry_diagnostic_is_conditional_on_interval_method":True,
      "reported_bounds_outside_corresponding_figure_visual_ranges":
        not(c["figure_lower_visual_range"][0]<=float(lo)<=c["figure_lower_visual_range"][1]) and
        not(c["figure_upper_visual_range"][0]<=float(hi)<=c["figure_upper_visual_range"][1]),
      "database_sum":sum(f["database_counts"]),
      "reported_identified_minus_duplicates":f["reported_identified"]-f["duplicates"],
      "database_sum_minus_duplicates":sum(f["database_counts"])-f["duplicates"],
      "screened_minus_exclusions":f["screened"]-sum(f["screen_exclusions"]),
      "next_stage_minus_fulltext_exclusions":f["next_stage"]-sum(f["fulltext_exclusions"]),
      "reported_fulltext":f["reported_fulltext"],
      "included_study_count_difference":f["diagram_included_studies"]-f["text_included_studies"],
      "new_independent_expert_adjudications":0,
      "emails_sent_by_this_script":0
    }
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    main(sys.argv[1])
