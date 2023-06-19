import dataclasses

@dataclasses.dataclass
class ReplicaState:
    has_been_restarted_by_opt: bool
    is_now_deleted_by_opt: bool

@dataclasses.dataclass()
class CustomContext:
    replica_state_dict: dict[str, ReplicaState]
    current_standby_replicas: None
    def __copy__(self) -> "CustomContext":
        return self