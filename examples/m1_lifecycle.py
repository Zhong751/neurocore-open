"""Run only a disposable, synthetic M1 lifecycle; no user instance is opened."""
from tempfile import TemporaryDirectory

from neurocore.memory import MemoryReader, MemoryStore


def main():
    with TemporaryDirectory() as directory:
        store = MemoryStore.create(directory, brain_id="synthetic-example")
        content = "Synthetic preference: category alpha."
        store.append_event(event_id="event-1", source_id="sample-1", source_type="synthetic",
            speaker_id="person-1", role="user", provenance="user_statement",
            conversation_id="session-1", content=content, occurred_at="2030-01-01T00:00:00Z")
        candidate = store.propose_fact(conversation_id="session-1", subject_id="person-1",
            predicate="category", value="alpha", evidence=[store.cite("event-1", 0, len(content))])["fact"]
        assert candidate["status"] == "pending"
        fact = store.confirm_fact(candidate["fact_id"], expected_revision=1,
                                  reason="Synthetic explicit review")["fact"]
        reopened = MemoryReader(directory, brain_id="synthetic-example")
        assert reopened.validate_references([fact["ref"]])["valid"]
        assert reopened.get_sources(fact["fact_id"])["sources"][0]["event"]["content"] == content
        print("Saved, confirmed, reopened and source-validated: passed")
        store.withdraw_event("event-1", reason="Synthetic withdrawal")
        epoch = store.authority()["epoch"]
        store.withdraw_event("event-1", reason="Synthetic retry")
        assert store.authority()["epoch"] == epoch
        assert not reopened.list_valid_facts()["facts"]
        assert not reopened.validate_references([fact["ref"]])["valid"]
        print("Source withdrawal, reference rejection and idempotency: passed")


if __name__ == "__main__":
    main()
