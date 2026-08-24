"""HTTP routes, grouped by what the request does to the graph.

    library      read the library: vocabulary and the example graphs on offer
    graph        read or rewrite the architecture graph itself
    assessment   validate, assess, mitigate, export

Each module is a Flask blueprint and holds nothing but request handling: parse
the payload, call into the library, shape the response. Anything that decides
something about the library belongs in `airiskkg.workbench` instead.
"""

from airiskkg.webapp.routes.assessment import assessment_routes
from airiskkg.webapp.routes.graph import graph_routes
from airiskkg.webapp.routes.library import library_routes

BLUEPRINTS = (library_routes, graph_routes, assessment_routes)

__all__ = ["BLUEPRINTS", "assessment_routes", "graph_routes", "library_routes"]
