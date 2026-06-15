from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from nomad.config import config
from owlready2 import ThingClass, get_ontology, Ontology
from nomad_ontology_service import OntologyConfig
from pathlib import Path
import logging

from nomad_ontology_service.apis import app

logger = logging.getLogger(__name__)
entry_point = config.get_plugin_entry_point("nomad_ontology_service:ontology_service")

def _resolve(owl_url: str) -> str:
    if owl_url.startswith("nomad_tmp://"):
        rel = owl_url.removeprefix("nomad_tmp://")
        return str(Path(config.fs.tmp) / rel)
    return owl_url  # https:// or file:// passed through as-is

def _fetch_superclasses(ontology: Ontology, class_name: str, cfg: OntologyConfig) -> list[str]:
    """Generic ancestor traversal, filtered by the provided ontology config."""
    cls = ontology.search_one(iri="*" + class_name)
    if cls is None:
        raise ValueError(f"Class '{class_name}' not found in the ontology.")

    # Build exclusion set from the specific ontology's config
    unwanted: set[str] = set()
    for root_iri in cfg.excluded_root_class_iris:
        root_cls = ontology.search_one(iri=root_iri)
        if root_cls is not None:
            unwanted |= {sc.iri for sc in root_cls.ancestors() if hasattr(sc, "iri")}
            unwanted.add(root_iri)

    return [
        sc
        for sc in cls.ancestors()
        if hasattr(sc, "iri")
        and sc.iri not in unwanted
        and any(pat in sc.iri for pat in cfg.included_iri_patterns)
        and isinstance(sc, ThingClass)
    ]


@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/{name}/superclasses/{class_name}")
def get_superclasses(name: str, class_name: str):
    cfg = next((c for c in entry_point.ontologies if c.name == name), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"No ontology named '{name}' configured.")
    try:
        ontology = get_ontology(_resolve(cfg.owl_url)).load()
        superclasses = _fetch_superclasses(ontology, class_name, cfg)
        return {"superclasses": superclasses}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An internal error occurred.")