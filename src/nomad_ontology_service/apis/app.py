import importlib
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from nomad.config import config
from owlready2 import ThingClass

logger = logging.getLogger(__name__)

entry_point = config.get_plugin_entry_point("nomad_ontology_service:ontology_service")

app = FastAPI(
    root_path=f"{config.services.api_base_path}/{entry_point.prefix}",
    title="Ontology Service",
    description="Generic ontology querying service.",
)

_ontology = None  # loaded at startup, reused across requests


@app.on_event("startup")
def startup_event():
    global _ontology
    if not entry_point.ontology_loader:
        logger.warning("No ontology_loader configured — service will return empty results.")
        return
    try:
        module_path, func_name = entry_point.ontology_loader.rsplit(":", 1)
        loader = getattr(importlib.import_module(module_path), func_name)
        _ontology = loader(entry_point.imports)
    except Exception as e:
        logger.error(f"Failed to load ontology: {e}")


def _fetch_superclasses(class_name: str) -> list[str]:
    """Generic ancestor traversal, filtered by entry point config."""
    cls = _ontology.search_one(iri="*" + class_name)
    if cls is None:
        raise ValueError(f"Class '{class_name}' not found in the ontology.")

    # Build exclusion set: ancestors of each listed root class
    unwanted: set[str] = set()
    for root_iri in entry_point.excluded_root_class_iris:
        root_cls = _ontology.search_one(iri=root_iri)
        if root_cls is not None:
            unwanted |= {sc.iri for sc in root_cls.ancestors() if hasattr(sc, "iri")}
            unwanted.add(root_iri)

    return [
        sc
        for sc in cls.ancestors()
        if hasattr(sc, "iri")
        and sc.iri not in unwanted
        and any(pat in sc.iri for pat in entry_point.included_iri_patterns)
        and isinstance(sc, ThingClass)
    ]


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/superclasses/{class_name}")
def get_superclasses(class_name: str):
    if _ontology is None:
        raise HTTPException(status_code=503, detail="Ontology not loaded.")
    try:
        superclasses = _fetch_superclasses(class_name)
        return {"superclasses": superclasses}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An internal error occurred.")