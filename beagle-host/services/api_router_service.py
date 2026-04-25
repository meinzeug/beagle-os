"""Generic HTTP API router for Beagle OS control plane.

Replaces the large if/elif chain in beagle-control-plane.py with a
declarative route registry. Surfaces register their handlers; the router
dispatches requests and extracts path parameters.

Pattern:
    router = ApiRouterService()
    router.register("GET",  "/api/v1/vms",          vm_surface.list_vms)
    router.register("GET",  "/api/v1/vms/:vmid",     vm_surface.get_vm)
    router.register("POST", "/api/v1/vms/:vmid/start", vm_surface.start_vm)

    response = router.dispatch("GET", "/api/v1/vms/101", request_body=None, headers={})
    # response is a dict: {"kind": "json", "status": HTTPStatus.OK, "payload": {...}}
    #                  or {"kind": "empty", "status": HTTPStatus.NOT_FOUND}
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Response = dict[str, Any]
Handler = Callable[..., Response]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

class _Route:
    """Compiled route with optional `:param` captures."""

    # Characters allowed in path segment param names
    _PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
    # Characters allowed in a path segment value (safe subset)
    _SEGMENT_VALUE = r"[A-Za-z0-9._@~%:+=/-]+"

    def __init__(self, method: str, pattern: str, handler: Handler) -> None:
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self._param_names: list[str] = []
        self._regex = self._compile(pattern)

    def _compile(self, pattern: str) -> re.Pattern[str]:
        """Convert `/api/v1/vms/:vmid/start` → compiled regex with named groups."""
        escaped = re.escape(pattern)
        # re.escape turns ":" into r"\:", convert back for our param parsing
        escaped = escaped.replace(r"\:", ":")

        def replace_param(m: re.Match[str]) -> str:
            name = m.group(1)
            self._param_names.append(name)
            return f"(?P<{name}>{self._SEGMENT_VALUE})"

        regex_str = self._PARAM_RE.sub(replace_param, escaped)
        return re.compile(f"^{regex_str}$")

    def match(self, method: str, path: str) -> dict[str, str] | None:
        """Return path params dict if this route matches, else None."""
        if method.upper() != self.method:
            return None
        m = self._regex.match(path)
        if m is None:
            return None
        return m.groupdict()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class ApiRouterService:
    """Declarative HTTP router for Beagle OS control plane surfaces.

    Routes are checked in registration order. More specific routes should be
    registered before more general ones (e.g. `/vms/_search` before `/vms/:vmid`).
    """

    def __init__(self) -> None:
        self._routes: list[_Route] = []

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register(self, method: str, pattern: str, handler: Handler) -> None:
        """Register a route handler.

        Args:
            method:  HTTP method (GET, POST, PUT, DELETE, PATCH).
            pattern: URL pattern, e.g. ``/api/v1/vms/:vmid``.
            handler: Callable that receives ``(path_params, body, headers)``
                     and returns a Response dict.
        """
        self._routes.append(_Route(method, pattern, handler))

    def register_surface(self, surface: Any) -> None:
        """Register all routes exposed by a surface via ``get_routes()``."""
        for method, pattern, handler in surface.get_routes():
            self.register(method, pattern, handler)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Dispatch a request and return a Response dict.

        Returns:
            - ``{"kind": "json", "status": HTTPStatus, "payload": dict}``
            - ``{"kind": "empty", "status": HTTPStatus}``
            - ``{"kind": "stream", "status": HTTPStatus, "generator": ...}``

        If no route matches, returns a 404 response.
        If the path matches but the method does not, returns 405.
        """
        if headers is None:
            headers = {}

        path_matched = False
        for route in self._routes:
            m = route._regex.match(path)
            if m is None:
                continue
            path_matched = True
            if route.method != method.upper():
                continue
            path_params = m.groupdict()
            return route.handler(
                path_params=path_params,
                body=body,
                headers=headers,
            )

        if path_matched:
            return _method_not_allowed()
        return _not_found()

    def handles(self, method: str, path: str) -> bool:
        """Return True if a route matches this method+path combination."""
        for route in self._routes:
            params = route.match(method, path)
            if params is not None:
                return True
        return False

    def handles_any_method(self, path: str) -> bool:
        """Return True if any route matches this path (any method)."""
        for route in self._routes:
            if route._regex.match(path):
                return True
        return False


# ---------------------------------------------------------------------------
# Helpers for standard responses
# ---------------------------------------------------------------------------

def _not_found() -> Response:
    return {
        "kind": "json",
        "status": HTTPStatus.NOT_FOUND,
        "payload": {"error": "Not Found"},
    }


def _method_not_allowed() -> Response:
    return {
        "kind": "json",
        "status": HTTPStatus.METHOD_NOT_ALLOWED,
        "payload": {"error": "Method Not Allowed"},
    }
