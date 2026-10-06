def test_migration_dataclass_has_expected_fields():
    from synlynk.migrations import Migration

    def up(conn):
        pass

    m = Migration(version=16, name="example", up=up)
    assert m.version == 16
    assert m.name == "example"
    assert m.up is up
