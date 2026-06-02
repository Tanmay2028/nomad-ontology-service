from nomad.config.models.plugins import APIEntryPoint
from pydantic import Field

class OntologyServiceEntryPoint(APIEntryPoint):
    ontology_loader: str | None = Field(
        default=None,
        description=(
            "Dotted import path to a callable with signature "
            "(imports: list[str]) -> Ontology. "
            "Example: 'pynxtools.nomad.apis.ontology:load_nexus_ontology'"
        ),
    )
    imports: list[str] = Field(
        default=[],
        description="List of additional OWL ontology URLs to import.",
    )
    excluded_root_class_iris: list[str] = Field(
        default=[],
        description="IRIs of classes whose full ancestor subtree is excluded from results.",
    )
    included_iri_patterns: list[str] = Field(
        default=[],
        description="Only ancestors whose IRI matches one of these substrings are returned.",
    )

    def load(self):
        from nomad_ontology_service.apis import app

        return app


ontology_service = OntologyServiceEntryPoint(
    name="ontology_service",
    description="Generic ontology querying service for NOMAD plugins.",
    prefix="/ontology_service",
)