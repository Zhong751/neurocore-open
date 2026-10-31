"""Check imports and bundled license after installing the built wheel."""
import hashlib
import importlib
import importlib.metadata
from pathlib import Path


def main():
    for name in ("neurocore", "neurocore.core", "neurocore.perception", "neurocore.models", "neurocore.api"):
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
    print("Built wheel imports and bundled Apache-2.0 license: passed")


if __name__ == "__main__":
    main()
