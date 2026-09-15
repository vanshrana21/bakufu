"""Memoised SHAP TreeExplainers, one per loaded model bundle.

Building a TreeExplainer walks every tree in the ensemble, so the shortfall and
scenario endpoints reuse one per bundle instead of rebuilding it per request.
"""

from __future__ import annotations

import threading
from typing import Any

_LOCK = threading.Lock()
#: id(bundle) -> (bundle, explainer). The bundle itself is held so its id cannot
#: be recycled by a different object while the entry exists; the identity check
#: below is a second guard against serving one model's explainer for another.
_EXPLAINERS: dict[int, tuple[dict[str, Any], Any]] = {}


def tree_explainer(bundle: dict[str, Any]) -> Any:
    """The TreeExplainer for `bundle["model"]`, built once per bundle object."""
    entry = _EXPLAINERS.get(id(bundle))
    if entry is not None and entry[0] is bundle:
        return entry[1]
    with _LOCK:
        entry = _EXPLAINERS.get(id(bundle))
        if entry is None or entry[0] is not bundle:
            import shap

            entry = (bundle, shap.TreeExplainer(bundle["model"]))
            _EXPLAINERS[id(bundle)] = entry
    return entry[1]


def clear_explainers() -> None:
    """Drop every cached explainer; called when artifacts are reloaded."""
    with _LOCK:
        _EXPLAINERS.clear()
