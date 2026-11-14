# Rule-based discovery engine; LLM only rephrases

The Discovery engine finds, scores and selects Candidate Discoveries with deterministic, rule-based statistics, and builds explanations from templates over the computed numbers. An optional LLM may rephrase those explanations but must not add claims beyond the computed results. We chose this over an LLM-driven design so the core works without an LLM, can be audited, and cannot invent information shown to students.

Status: accepted
