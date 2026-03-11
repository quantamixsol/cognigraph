"""CogniGraph Ontology Module — Governance-Constrained Reasoning.

Provides OWL-like class hierarchy, SHACL validation gates, constraint
propagation, ontology-based message routing, and skill resolution.
Domain-agnostic: any domain registers via the DomainRegistry API.
"""

from cognigraph.ontology.upper import UpperOntology
from cognigraph.ontology.domain_registry import DomainRegistry, DomainOntology
from cognigraph.ontology.shacl_gate import SHACLGate, ValidationResult
from cognigraph.ontology.constraint_graph import ConstraintGraph
from cognigraph.ontology.router import OntologyRouter
from cognigraph.ontology.skill_resolver import SkillResolver, Skill
from cognigraph.ontology.semantic_shacl_gate import (
    SemanticSHACLGate,
    SemanticConstraint,
    SemanticValidationResult,
    SemanticViolation,
    build_semantic_constraints_from_kg,
)
from cognigraph.ontology.ontology_generator import OntologyGenerator

__all__ = [
    "UpperOntology",
    "DomainRegistry",
    "DomainOntology",
    "SHACLGate",
    "ValidationResult",
    "ConstraintGraph",
    "OntologyRouter",
    "SkillResolver",
    "Skill",
    # Semantic governance (v3)
    "SemanticSHACLGate",
    "SemanticConstraint",
    "SemanticValidationResult",
    "SemanticViolation",
    "build_semantic_constraints_from_kg",
    "OntologyGenerator",
]
