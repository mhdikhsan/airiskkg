from airiskkg.webapp.routes.assessment import assessment_routes
from airiskkg.webapp.routes.graph import graph_routes
from airiskkg.webapp.routes.library import library_routes

BLUEPRINTS = (library_routes, graph_routes, assessment_routes)

__all__ = ["BLUEPRINTS", "assessment_routes", "graph_routes", "library_routes"]
