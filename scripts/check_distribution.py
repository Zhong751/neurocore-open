"""Check imports and bundled license after installing the built wheel."""
import hashlib
import importlib
import importlib.metadata
from pathlib import Path
import tempfile


def main():
    for name in ("neurocore", "neurocore.core", "neurocore.perception", "neurocore.models", "neurocore.api", "neurocore.memory"):
        importlib.import_module(name)
    distribution = importlib.metadata.distribution("neurocore")
    if distribution.metadata["License-Expression"] != "Apache-2.0":
        raise SystemExit("Unexpected wheel license metadata")
    licenses = [f for f in distribution.files or () if str(f).endswith("/licenses/LICENSE")]
    if len(licenses) != 1:
        raise SystemExit("Built wheel must include exactly one LICENSE")
    digest = hashlib.sha256(Path(distribution.locate_file(licenses[0])).read_bytes()).hexdigest()
    if digest != "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30":
        raise SystemExit("Bundled LICENSE differs from official Apache-2.0 text")
    # Exercise the actual installed wheel, with no source-tree import fallback.
    from neurocore.memory import MemoryStore, MemoryReader
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore.create(directory, brain_id="synthetic-wheel")
        content = "Synthetic sample: category alpha."
        store.append_event(event_id="event-1", source_id="sample-1", source_type="synthetic",
            speaker_id="subject-1", role="user", provenance="user_statement",
            conversation_id="conversation-1", content=content, occurred_at="2030-01-01T00:00:00Z")
        proposed = store.propose_fact(conversation_id="conversation-1", subject_id="subject-1",
            predicate="category", value="alpha", evidence=[store.cite("event-1", 0, len(content))])["fact"]
        confirmed = store.confirm_fact(proposed["fact_id"], expected_revision=1,
                                       reason="Synthetic source review")["fact"]
        reader = MemoryReader(directory, brain_id="synthetic-wheel")
        assert reader.validate_references([confirmed["ref"]])["valid"]
        store.withdraw_event("event-1", reason="Synthetic withdrawal")
        assert not reader.list_valid_facts()["facts"]
        assert not reader.validate_references([confirmed["ref"]])["valid"]
    print("Built wheel imports, license and independent M1 lifecycle: passed")


if __name__ == "__main__":
    main()
