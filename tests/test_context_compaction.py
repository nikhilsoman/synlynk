def test_context_compaction_module_importable():
    import synlynk.context_compaction as cc_module

    assert hasattr(cc_module, "CONTEXT_COMPACTION_SETTINGS_SCHEMA")
    assert "auto_checkpoint_on_pack" in cc_module.CONTEXT_COMPACTION_SETTINGS_SCHEMA["fields"]
