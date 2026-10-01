"""Owner-scoped admission for future adapters; catalog entries cannot self-enable."""

from copy import deepcopy
from .model_ecology import deployment_errors, contract_errors


class DeploymentRegistry:
    def __init__(self, owner):
        self.owner = owner
        self._adapters = {}
        self._verifiers = {}
        self._deployments = {}

    def register_adapter(self, identifier, capabilities, *, verify):
        if identifier in self._adapters:
            raise ValueError("adapter already registered")
        if not callable(verify):
            raise ValueError("owner artifact and receipt verifier required")
        self._adapters[identifier] = frozenset(capabilities)
        self._verifiers[identifier] = verify

    def admit(self, manifest):
        errors = deployment_errors(
            manifest,
            adapters=self._adapters,
            capabilities=self._adapters.get(manifest.get("adapter"), ()),
        )
        if manifest.get("owner") != self.owner:
            errors.append("deployment belongs to a different owner")
        if errors:
            raise ValueError("; ".join(errors))
        # The owner must inspect local artifact hashes, runtime and review receipts.
        # A syntactically pinned manifest alone cannot admit a deployment.
        problems = self._verifiers[manifest["adapter"]](deepcopy(manifest))
        if problems != []:
            raise ValueError("owner verification failed: " + str(problems))
        if manifest["id"] in self._deployments:
            raise ValueError(
                "deployment already registered; use a new deployment identity"
            )
        self._deployments[manifest["id"]] = deepcopy(manifest)

    def require(self, identifier, capability, duration_seconds):
        manifest = self._deployments.get(identifier)
        if manifest is None or capability not in manifest["capabilities"]:
            raise ValueError("deployment/capability unavailable")
        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or not 0 < duration_seconds <= manifest["max_input_seconds"]
        ):
            raise ValueError("input exceeds tested deployment bounds")
        return deepcopy(manifest)

    def validate_result(self, identifier, evidence):
        errors = contract_errors("analysis-evidence", evidence)
        if errors:
            raise ValueError("; ".join(errors))
        if evidence["deployment_id"] != identifier:
            raise ValueError("evidence deployment mismatch")
        view = evidence["view"]
        manifest = self.require(
            identifier,
            evidence["capability"],
            view["end_seconds"] - view["start_seconds"],
        )
        if evidence["model_revision"] not in {
            c["revision"] for c in manifest["components"]
        }:
            raise ValueError("evidence model revision mismatch")
        return deepcopy(evidence)

    def catalog(self):
        return deepcopy(list(self._deployments.values()))
