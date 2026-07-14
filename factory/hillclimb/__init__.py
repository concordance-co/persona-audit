"""Demo dataset build: personas, seeds, generation rounds, QA, and separation metrics.

This package implements the machinery behind docs/demo-dataset-build-plan.md
and the hill-climb loop in docs/demo-hillclimb.md:

- personas.py       versioned Sol/Marrow/control system prompts
- seeds.py          seed conversations (fixed user turns) by stage and tier
- rounds.py         turn-by-turn round construction and result ingestion
- transcript_qa.py  lexicon/length/hedge QA that generations stayed distinct
- normalize.py      generated tracks -> normalized AuditTrace rows
- separation.py     activation-score separation metrics and stage gates
- state.py          persistent hill-climb iteration state

The driver CLI is factory/scripts/demo_hillclimb.py.
"""
