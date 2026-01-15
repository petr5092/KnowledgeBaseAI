from app.core.context import set_tenant_id, get_tenant_id
from app.db.dao_base import DaoBase, TenantRequiredError

def test_dao_requires_tenant():
    set_tenant_id(None)
    try:
        DaoBase()
        assert False, "should raise"
    except TenantRequiredError:
        pass

def test_dao_uses_context_tenant():
    set_tenant_id("tenant-xyz")
    dao = DaoBase()
    assert dao.tenant_id == "tenant-xyz"
    params = dao.inject_tenant({"x": 1})
    assert params["tenant_id"] == "tenant-xyz"
    assert params["x"] == 1
