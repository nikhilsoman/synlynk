from synlynk import uxcore


def test_local_actor_default_role_is_owner():
    actor = uxcore.LocalActor()
    assert actor.role == uxcore.Role.OWNER


def test_default_actor_singleton_is_local_owner():
    assert uxcore.DEFAULT_ACTOR.role == uxcore.Role.OWNER
