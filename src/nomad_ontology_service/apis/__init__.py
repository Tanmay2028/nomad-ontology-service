from fastapi import FastAPI
from nomad.config import config

entry_point = config.get_plugin_entry_point("nomad_ontology_service:ontology_service")

app = FastAPI(
    root_path=f"{config.services.api_base_path}/{entry_point.prefix}",
    title="Ontology Service",
    description="Generic ontology querying service.",
)