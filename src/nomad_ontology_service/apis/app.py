from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from nomad.config import config
from owlready2 import ThingClass, get_ontology, Ontology
from nomad_ontology_service import OntologyConfig
from pathlib import Path
import logging

from nomad_ontology_service.apis import app

logger = logging.getLogger(__name__)
entry_point = config.get_plugin_entry_point("nomad_ontology_service:ontology_service")

app = FastAPI(
    root_path=f"{config.services.api_base_path}/{entry_point.prefix}",
    title="Ontology Service",
    description="Generic ontology querying service.",
)

def _resolve(owl_url: str) -> str:
    if owl_url.startswith("nomad_tmp://"):
        rel = owl_url.removeprefix("nomad_tmp://")
        return str(Path(config.fs.tmp) / rel)
    return owl_url  

def _fetch_superclasses(ontology: Ontology, class_name: str, cfg: OntologyConfig) -> list[str]:
    """Generic ancestor traversal, filtered by the provided ontology config."""
    cls = ontology.search_one(iri="*" + class_name)
    if cls is None:
        raise ValueError(f"Class '{class_name}' not found in the ontology.")

    unwanted: set[str] = set()
    for root_iri in cfg.excluded_root_class_iris:
        root_cls = ontology.search_one(iri=root_iri)
        if root_cls is not None:
            unwanted |= {sc.iri for sc in root_cls.ancestors() if hasattr(sc, "iri")}
            unwanted.add(root_iri)

    return [
        sc.label.first() if (hasattr(sc, 'label') and sc.label) else sc.name
        for sc in cls.ancestors()
        if hasattr(sc, "iri")
        and sc.iri not in unwanted
        and any(pat in sc.iri for pat in cfg.included_iri_patterns)
        and isinstance(sc, ThingClass)
    ]

def _safe_descendants(start_cls) -> set:
    """Safely traverse descendants, catching owlready2 metaclass conflicts."""
    seen = set()
    queue = [start_cls]
    while queue:
        current = queue.pop(0)
        if current not in seen:
            seen.add(current)
            try:
                subs = current.subclasses()
                for sub in subs:
                    if hasattr(sub, "iri") and sub not in seen:
                        queue.append(sub)
            except TypeError as e:
                logger.warning(f"Metaclass conflict while fetching subclasses for {current}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error fetching subclasses for {current}: {e}")
    return seen

def _fetch_descendants(ontology: Ontology, class_name: str, cfg: OntologyConfig) -> list[str]:
    """Generic descendant traversal, filtered by the provided ontology config."""
    cls = ontology.search_one(iri="*" + class_name)
    if cls is None:
        raise ValueError(f"Class '{class_name}' not found in the ontology.")

    return [
        sc.label.first() if (hasattr(sc, 'label') and sc.label) else sc.name
        for sc in _safe_descendants(cls)
        if hasattr(sc, "iri")
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
        resolved_url = _resolve(cfg.owl_url)
        logger.info(f"Loading ontology from: {resolved_url}")
        ontology = get_ontology(resolved_url).load()
        superclasses = _fetch_superclasses(ontology, class_name, cfg)
        return {"superclasses": superclasses}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching superclasses for {class_name}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
@app.get("/{name}/descendants/{class_name}")
def get_descendants(name: str, class_name: str):
    cfg = next((c for c in entry_point.ontologies if c.name == name), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"No ontology named '{name}' configured.")
    try:
        resolved_url = _resolve(cfg.owl_url)
        logger.info(f"Loading ontology from: {resolved_url}")
        ontology = get_ontology(resolved_url).load()
        descendants = _fetch_descendants(ontology, class_name, cfg)
        return {"descendants": descendants}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching descendants for {class_name}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")