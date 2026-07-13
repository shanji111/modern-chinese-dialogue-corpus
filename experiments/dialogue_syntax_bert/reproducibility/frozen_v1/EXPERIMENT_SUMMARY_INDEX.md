# formal_300_v1 Experiment Summary Index

This index summarizes the dialogue-syntax BERT-assisted experiment chain up to the hybrid shadow integration design stage.

Current status:

- Frozen master gold: `formal_300_v1_gold_v1.csv` / `.xlsx`
- Binary gold: `formal_300_v1_gold_v1_binary.csv`
- Recommended hybrid strategy name: `rule_priority_with_bert_recall`
- Current recommendation: rules remain the graph/explanation system; MacBERT is an auxiliary pair-level confidence scorer, reranker, and recall supplement.

No production route is connected by this experiment chain. No formal database writes are part of the frozen artifacts.

## Core Metrics

| Item | Result |
| --- | --- |
| `gold_v1` distribution | yes=228, no=58, uncertain=14, total=300 |
| `gold_v1_binary` distribution | yes=228, no=58, total=286 |
| Majority / similarity baseline | macro-F1 approx 0.442, balanced accuracy=0.500 |
| Rule baseline, test split | macro-F1=0.642, balanced accuracy=0.753 |
| Rule baseline, full binary set | precision=0.873, recall=0.575, positive F1=0.693 |
| MacBERT v3 multi-seed mean | macro-F1=0.745 +/- 0.047, balanced accuracy=0.803 +/- 0.074 |
| Hybrid best | macro-F1=0.779, balanced accuracy=0.815 |
| Hybrid best confusion matrix | TP/FP/FN/TN=29/2/5/7 |
| Hybrid rule-FN recovered | 8 |

## Stage Index

| Stage | Inputs | Output Directory / Files | Trained Model | Formal DB Access | Core Result | Key Conclusion |
| --- | --- | --- | --- | --- | --- | --- |
| `pilot_50` | Formal corpus schema and adjacent-turn sampling script | `artifacts/pilot_50/` | No | SQLite read-only only | 50 pilot pairs with blind annotation/key split and integrity reports | Sampling, blind annotation, and validation workflow became safe enough for formal annotation. |
| Pilot AI-assisted annotation | `pilot_50_annotation_blind.csv`, `pilot_50_evaluation_key.csv` | `pilot_50_annotation_ai_draft.csv`, `rule_eval_ai_draft.md`, `review_queue_ai_draft.csv` | No | No | AI draft labels and first rule-baseline calibration | AI draft was useful for boundary review but not treated as gold. |
| Pilot boundary review | `rule_eval_ai_draft.md`, review queue, AI draft | `pilot_50_boundary_review.md`, `pilot_50_boundary_decisions_template.csv`, boundary summary | No | No | Boundary rules clarified ordinary Q/A, slot filling, reference, analogy, and noise | The label schema gained explicit boundary principles before formal annotation. |
| `formal_300_v1` sampling | Read-only corpus DB, `sample_pairs.py`, pilot lessons | `artifacts/formal_300_v1/formal_300_v1.csv`, `.jsonl`, blind CSV/XLSX, key, sampling report | No | SQLite read-only only; no writes | 300 stratified adjacent-turn pairs | Formal sample preserved rule strata, source coverage, hash/group keys, and blind/key split. |
| AI-assisted full annotation | User-provided labels and formal blind/key files | `formal_300_v1_annotation_ai_assisted_full.csv` / `.xlsx` | No | No | Full AI-assisted annotation draft, rows=300, issues=0 after evidence-span fixes | Draft became a candidate layer, not final gold. |
| Top30 review | Full review queue and AI-assisted full annotation | `formal_300_v1_top30_review_packet.*`, then `formal_300_v1_gold_candidate.*` | No | No | 30 high-priority items reviewed and applied to gold candidate | Highest-risk uncertain/conflict cases were checked before gold freezing. |
| Round2 review | `formal_300_v1_gold_candidate.csv`, round2 queue | `formal_300_v1_round2_review_packet.*`, then `gold_candidate_v2.*` | No | No | 20 targeted high-risk samples reviewed; changed rows=0 | Round2 supported the stability of the candidate labels. |
| Final sanity check | `gold_candidate_v2.csv`, final sanity packet | `formal_300_v1_final_sanity_packet.*`, then `gold_candidate_v3.*` | No | No | 12 sanity-check items reviewed; changed rows=0 | Modification count <= 2/12, so freeze criterion was met. |
| `gold_v1` freeze | `gold_candidate_v3.csv`, final sanity result | `formal_300_v1_gold_v1.csv` / `.xlsx`, `formal_300_v1_gold_v1_binary.csv`, freeze report | No | No | Master gold kept uncertain; binary file excluded uncertain | `gold_v1` is the master annotation file; `gold_v1_binary` is for binary modeling/evaluation. |
| Binary split | `formal_300_v1_gold_v1_binary.csv` | `baselines/gold_v1_binary_train.csv`, `dev.csv`, `test.csv`, split reports | No | No | train=200, dev=43, test=43; no group/hash leakage | Split is leak-safe by pair, hash, and conversation group. |
| Rule baseline | `gold_v1_binary`, evaluation key | `baselines/rule_baseline_gold_v1_binary.md` / `.json` | No | No | Test macro-F1=0.642, balanced accuracy=0.753; full positive F1=0.693 | Rules are interpretable and strong on no-class filtering, but recall is limited. |
| Majority / similarity baseline | Frozen split and existing similarity features | `baselines/majority_baseline_*`, `similarity_baseline_*`, `baseline_metrics_audit.*` | No | No | Majority/similarity degenerated to all-yes; macro-F1 approx 0.442 | Positive F1 alone is misleading under class imbalance. |
| BERT shadow v1 | Local multilingual MiniLM, frozen split | `bert_shadow_v1/` | Yes, offline shadow only | No | Test dev-threshold macro-F1=0.496, balanced accuracy=0.505 | v1 showed some no-class signal but did not beat rule baseline. |
| BERT shadow v2 model check | Local MacBERT path `D:\hf_models\hfl_chinese_macbert_base` | `bert_shadow_v2_model_check/model_availability_report_v2.*` | No | No | MacBERT tokenizer/model loaded offline; hidden_size=768, layers=12, vocab=21128 | Local Chinese MacBERT was usable as the v2 main model. |
| BERT shadow v2 | Local `hfl/chinese-macbert-base`, frozen split | `bert_shadow_v2/` | Yes, offline shadow only | No | Test dev-threshold macro-F1=0.703, balanced accuracy=0.797, no recall=0.889 | Chinese MacBERT clearly outperformed v1 and rule test split, but still had topic-related FP risk. |
| BERT shadow v2 post-hoc audit | v2 predictions, rule baseline, gold/test files | `bert_shadow_v2/audit/` | No | No | 1 FP (`F300V1-0221`), 10 FN; FN concentrated in demonstrative/reference and short answers | BERT helps hidden resonance but can confuse topic continuity with resonance. |
| BERT shadow v3 multi-seed | Local MacBERT, seeds 20260621/42/1234/2025/3407 | `bert_shadow_v3_multiseed/` | Yes, offline shadow only | No | Mean macro-F1=0.745 +/- 0.047, balanced accuracy=0.803 +/- 0.074; 0 all-yes seeds | Improvement is reasonably stable, though `seed=1234` shows threshold/no-class recall variance. |
| Hybrid shadow v1 | v3 multi-seed probabilities, rule flags, frozen dev/test | `hybrid_shadow_v1/` | No | No | Best hybrid macro-F1=0.779, balanced accuracy=0.815, TP/FP/FN/TN=29/2/5/7 | `rule_priority_with_bert_recall` is the preferred strategy name for explainable hybrid use. |
| Hybrid integration design | Hybrid results and safety constraints | `hybrid_shadow_integration_design/` | No | No | API contract, UI notes, safety/limitations, staged roadmap | Integration should remain staged and shadow-first; BERT is auxiliary, not a graph generator. |

## Current Recommended Architecture

Rules remain responsible for:

- Candidate recall.
- Surface pattern evidence.
- Cross-turn graph explanation.
- Interpretable rule flags.
- Human-readable rule evidence.

MacBERT is responsible for:

- Pair-level semantic confidence.
- Reranking.
- Recall supplementation for rule-negative but semantically resonant pairs.
- Flagging possible hidden resonance for review.

The hybrid layer is responsible for:

- Combining `rule_any_positive` and BERT probability.
- Applying `rule_priority_with_bert_recall`.
- Assigning confidence/warning metadata.
- Marking rule-negative/BERT-high pairs as review candidates.

BERT must not:

- Generate graph edges.
- Replace the rule graph.
- Automatically write to production database tables.
- Modify gold labels.
- Replace human judgment.
- Serve as the only explanation source.

## Recommended Next Route

Stage A: offline interface wrapper.

- Wrap the hybrid API contract in a local/offline callable interface.
- Exit condition: deterministic outputs on fixed samples; no DB writes; no website route changes.

Stage B: offline batch scoring.

- Run suitable existing samples offline.
- Prefer curated text dialogue, daily conversation, interview, and clean script/dialogue data.
- Be cautious with noisy network replies and contextless fragments.
- Exit condition: reviewable exports with warning flags and explanation summaries.

Stage C: website shadow logging.

- Log hybrid outputs without showing them to users.
- Exit condition: opt-in/admin-only logging, no ranking changes, no automatic DB mutation.

Stage D: admin-only display.

- Show rule graph first, BERT confidence second.
- Exit condition: reviewers can inspect rule-negative/BERT-high candidates without treating BERT as gold.

Stage E: human-reviewed user-visible confidence.

- Only after larger gold data and stable shadow logs.
- Exit condition: product copy avoids AI truth claims and keeps graph explanation available.

## Current Non-Recommendations

Do not immediately launch this as user-facing production behavior.

Do not let BERT automatically decide resonance results.

Do not automatically write BERT or hybrid outputs into production database tables.

Do not automatically modify `gold_v1` or any future gold label set.

Do not evaluate only positive F1.

Do not ignore topic-related false positives such as `F300V1-0221`.

Do not replace graph explanation with BERT probability.

## Safety Ledger

This formal chain includes some stages that read the formal corpus database in SQLite read-only mode for sampling/schema work. No stage should have written to `corpus.db`, migrated it, rebuilt it, or connected these experiments to production routes.

Current index generation did not train a model, run BERT, read/write `corpus.db`, modify gold files, modify split files, deploy, push, or connect website routes.

