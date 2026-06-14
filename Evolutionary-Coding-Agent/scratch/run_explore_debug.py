import os
import sys
import json

sys.path.append(os.path.abspath('.'))

from src.exploration.curriculum_proposer import curriculum_proposer
from src.exploration.oracle_synthesis import oracle_synthesizer
from src.exploration.skill_gap_analyzer import skill_gap_analyzer

print("Analyzing gaps...")
gap_info = skill_gap_analyzer.analyze()
gap_targets = skill_gap_analyzer.top_gaps(limit=3)
print("Gap Targets:", gap_targets)
print("Skills in Bank:", gap_info["skill_names"])

print("\nProposing task...")
proposed = curriculum_proposer.propose(
    success_rate=0.4,
    skill_summaries=gap_info["skill_names"],
    gap_targets=gap_targets,
    avoid_topics=[]
)
print("Proposed Task:")
print("ID:", proposed.id)
print("Title:", proposed.title)
print("Description:", proposed.description)

print("\nSynthesizing oracle...")
oracle = oracle_synthesizer.synthesize(proposed)
print("Oracle Validation Passed:", oracle.validation_passed)
print("Rejection Reason:", oracle.rejection_reason)
print("Test Code Length:", len(oracle.test_code))
print("Hidden Test Code Length:", len(oracle.hidden_test_code))
