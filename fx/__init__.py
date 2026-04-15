"""
FX Recovery System package.
"""

from flask import Blueprint


def create_fx_blueprint() -> Blueprint:
    """Create and configure the FX Recovery Blueprint."""
    bp = Blueprint(
        "fx",
        __name__,
        template_folder="../fx_templates",
        static_folder="../static/fx",
        static_url_path="/fx/static",
    )

    from fx.routes.dashboard import dashboard_bp
    from fx.routes.contracts import contracts_bp
    from fx.routes.alerts import alerts_bp
    from fx.routes.api import api_bp

    bp.register_blueprint(dashboard_bp)
    bp.register_blueprint(contracts_bp)
    bp.register_blueprint(alerts_bp)
    bp.register_blueprint(api_bp)

    return bp
