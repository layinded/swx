from swx_core.bootstrap import _extract_route_paths
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_router(path: str, module_name: str):
    spec = spec_from_file_location(module_name, Path(path))
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.router


def test_webhook_routes_registered_in_core_router():
    admin_webhook_router = _load_router("swx_core/routes/admin/webhook_route.py", "test_admin_webhook_route")
    user_webhook_router = _load_router("swx_core/routes/user/webhook_route.py", "test_user_webhook_route")
    admin_paths = _extract_route_paths(admin_webhook_router)
    user_paths = _extract_route_paths(user_webhook_router)
    assert "/admin/webhooks/endpoints" in admin_paths
    assert "/admin/webhooks/endpoints/{endpoint_id}" in admin_paths
    assert "/user/webhooks/endpoints" in user_paths
    assert "/user/webhooks/deliveries/{delivery_id}/retry" in user_paths
