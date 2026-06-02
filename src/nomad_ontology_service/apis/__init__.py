from nomad.config.models.plugins import APIEntryPoint


class OntologyServiceEntryPoint(APIEntryPoint):
    
    def load(self):
        from nomad_ontology_service.apis.app import app

        return app
    
ontology_service_entry_point = OntologyServiceEntryPoint(
    description="Ontology Service API",
    prefix="ontology",
)