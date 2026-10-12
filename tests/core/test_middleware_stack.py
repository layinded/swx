from swx_core.middleware.stack import (
    MiddlewareSpec,
    CANONICAL_ORDER,
    apply_middleware_stack,
    _apply_cors,
    _apply_security_headers,
    _apply_audit,
    _apply_logging,
    _apply_rate_limit,
    _apply_auth_rate_limit,
    _apply_rate_limit_headers,
    _apply_tenant,
    _apply_csrf,
    _apply_container,
    _apply_session,
    _apply_metrics,
    _apply_region_routing,
)


class TestCanonicalOrder:
    def test_all_specs_have_unique_names(self):
        names = [spec.name for spec in CANONICAL_ORDER]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_all_specs_have_unique_orders(self):
        orders = [spec.order for spec in CANONICAL_ORDER]
        assert len(orders) == len(set(orders)), f"Duplicate orders: {orders}"

    def test_orders_are_ascending(self):
        orders = [spec.order for spec in CANONICAL_ORDER]
        assert orders == sorted(orders), "CANONICAL_ORDER must be sorted by order"

    def test_cors_is_first(self):
        assert CANONICAL_ORDER[0].name == "cors"
        assert CANONICAL_ORDER[0].order == 10

    def test_required_layers_are_enabled(self):
        for spec in CANONICAL_ORDER:
            if spec.required:
                assert spec.enabled, f"Required layer {spec.name} must be enabled"

    def test_optional_layers_can_be_disabled(self):
        optional = [s for s in CANONICAL_ORDER if not s.required]
        assert len(optional) >= 1, "Should have at least one optional layer"

    def test_apply_functions_exist(self):
        fns = [
            _apply_cors, _apply_security_headers, _apply_audit, _apply_logging,
            _apply_rate_limit, _apply_auth_rate_limit, _apply_rate_limit_headers,
            _apply_tenant, _apply_csrf, _apply_container, _apply_session,
            _apply_metrics, _apply_region_routing,
        ]
        assert len(fns) == len(CANONICAL_ORDER)
        for fn in fns:
            assert callable(fn)

    def test_security_ordering_cors_before_auth(self):
        cors_idx = next(i for i, s in enumerate(CANONICAL_ORDER) if s.name == "cors")
        auth_idx = next(i for i, s in enumerate(CANONICAL_ORDER) if s.name == "auth_rate_limit")
        assert cors_idx < auth_idx, "CORS must execute before auth rate limiting"

    def test_audit_before_logging(self):
        audit_order = next(s.order for s in CANONICAL_ORDER if s.name == "audit")
        logging_order = next(s.order for s in CANONICAL_ORDER if s.name == "logging")
        assert audit_order < logging_order, "Audit must come before logging"


class TestMiddlewareSpec:
    def test_defaults(self):
        spec = MiddlewareSpec(name="test", apply_fn=None)
        assert spec.enabled is True
        assert spec.required is True
        assert spec.order == 100

    def test_disabled_optional(self):
        spec = MiddlewareSpec(name="metrics", apply_fn=None, enabled=False, required=False, order=120)
        assert spec.enabled is False
        assert spec.required is False