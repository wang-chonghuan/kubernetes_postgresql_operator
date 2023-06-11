# Kopf minimal example

The minimum codebase needed for to make a runnable Kubernetes operator.

# Kopf example with children

This example creates a `Pod` for every created `KopfExample` object,
and attaches it as a child of that example object. The latter means that
when the parent object is deleted, the child pod is also terminated.

# Kopf example with exceptions in the handler

This example raises the exceptions in the handler,
so that it is retried a few times until it succeeds.

# Kopf example with the event reporting

The framework reports some basic events on the handling progress.
But the developers can report their own events conveniently.

# Kopf example with multiple handlers

Multiple handlers can be registered for the same event.
They are executed in the order of registration.

Beside the stardard create-update-delete events, a per-field diff can be registered.
It is called only in case of the specified field changes,
with `old` & `new` set to that field's values.

# Kopf example with multiple processes and development mode

When multiple operators start for the same cluster (in the cluster or outside),
they become aware about each other, and exchange the basic information about
their liveness and the priorities, and cooperate to avoid the undesired
side-effects (e.g., duplicated children creation, infinite cross-changes).

The main use-case for this is the development mode: when a developer starts
an operator on their workstation, all the deployed operators should pause
and stop processing of the objects, until the developer's operator exits.

# Kopf example with dynamic sub-handlers

It is convenient to re-use the framework's capabilities to track
the handler execution, to skip the finished or failed handlers,
and to retry to recoverable errors -- without the reimplemenation
of the same logic inside of the handlers.

In some cases, however, the required handlers can be identified
only at the handling time, mostly when they are based on the spec,
or on some external environment (databases, remote APIs, other objects).

For this case, the sub-handlers can be useful. The sub-handlers "extend"
the main handler, inside of which they are defined, but delegate
the progress tracking to the framework.

In all aspects, the sub-handler are the same as other handlers:
the same function signatures, the same execution environment,
the same error handling, etc.

# Kopf example with spy-handlers for the raw events

Kopf stores its handler status on the objects' status field.
This can be not desired when the objects do not belong to this operator,
but a probably served by some other operator, and are just watched
by the current operator, e.g. for their status fields.

Event-watching handlers can be used as the silent spies on the raw events:
they do not store anything on the object, and do not create the k8s-events.

If the event handler fails, the error is logged to the operator's log,
and then ignored.

Please note that the event handlers are invoked for *every* event received
from the watching stream. This also includes the first-time listing when
the operator starts or restarts. It is the developer's responsibility to make
the handlers idempotent (re-executable with do duplicated side-effects).

# Kopf example for testing the operator

Kopf provides some basic tools to test the Kopf-based operators.
With these tools, the testing frameworks (pytest in this case)
can run the operator-under-test in the background, while the test
performs the resource manipulation.

# Kopf example for built-in resources

Kopf can also handle the built-in resources, such as Pods, Jobs, etc.

In this example, we take control all over the pods (namespaced/cluster-wide),
and allow the pods to exist for no longer than 30 seconds --
either after creation or after the operator restart.

For no specific reason, just for fun. Maybe, as a way of Chaos Engineering
to force making the resilient applications (tolerant to pod killing).

However, the system namespaces (kube-system, etc) are explicitly protected --
to prevent killing the cluster itself.

# Kopf example for testing the filtering of handlers

Kopf has the ability to execute handlers only if the watched objects
match the filters passed to the handler. This includes matching on:
* labels of a resource
* annotations of a resource

# Kopf example for embedded operator

Kopf operators can be embedded into arbitrary applications, such as UI;
or they can be orchestrated explicitly by the developers instead of `kopf run`.

In this example, we start the operator in a side thread, while simulating
an application activity in the main thread. In this case, the "application"
just creates and deletes the example objects, but it can be any activity.

# Kopf example for startup/cleanup handlers

Kopf operators can have handlers invoked on startup and on cleanup.

The startup handlers are slightly different from the module-level code:
the actual tasks (e.g. API calls for watching) are not started until
all the startup handlers succeed.
If the handlers fail, the operator also fails.

The cleanup handlers are executed when the operator exits either by a signal
(e.g. SIGTERM), or by raising the stop-flag, or by cancelling
the operator's asyncio task.
They are not guaranteed to be fully executed if they take too long.

In this example, we start a background task for every pod we see,
and ask that task to finish when the operator exits. It takes some time
for the tasks to notice the request, so the exiting is not instant.