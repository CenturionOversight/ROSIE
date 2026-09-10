s=open('wrapper/tools.py',encoding='utf-8').read()

old = '''    # For a runtime-scoped dispatch we bind the session's state over the
    # module-level globals for the duration of this call.  This is the
    # mechanism by which dispatch becomes runtime-aware without leaking
    # across concurrent sessions.
    session_state: tuple[Path | None, ApprovalPolicy | None, Any] = (
        _workspace_root, _policy, _shell_executor
    )
    if runtime is not None:
        _set_globals_from_runtime(runtime)

    try:
        result = func(**call_args)
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        return str(result)
    except PathTraversalError as exc:
        return f"ERROR (path violation): {exc}"
    except Exception as exc:
        return f"ERROR ({type(exc).__name__}): {exc}"
    finally:
        # Always restore the module-level state so nothing leaks across
        # calls.
        if runtime is not None:
            _restore_from_globals(session_state)'''

new = '''    # For a runtime-scoped dispatch we bind the session's state over the
    # module-level globals for the duration of this call.  This is the
    # mechanism by which dispatch becomes runtime-aware without leaking
    # across concurrent sessions.
    token = _runtime_context.set(runtime) if runtime is not None else None
    try:
        return _dispatch_in_session(name, call_args)
    finally:
        if runtime is not None:
            _runtime_context.reset(runtime)

def _dispatch_in_session(name: str, args: dict[str, Any]) -> str:
    """Inner dispatch: runs once the runtime scope is established for this call."""
    if name not in TOOL_REGISTRY:
        return f"ERROR: Unknown tool '{name}'."

    func = TOOL_REGISTRY[name]
    model_cls = TOOL_MODELS.get(name)

    # Validate arguments with pydantic.
    if model_cls is not None:
        try:
            validated = model_cls(**args)
            call_args = validated.model_dump()
        except Exception as exc:
            return f"ERROR: Argument validation failed for '{name}': {exc}"
    else:
        call_args = args if args else {}

    try:
        result = func(**call_args)
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        return str(result)
    except PathTraversalError as exc:
        return f"ERROR (path violation): {exc}"
    except Exception as exc:
        return f"ERROR ({type(exc).__name__}): {exc}"


@contextmanager
def _runtime_scope(runtime: RuntimeSession | None) -> Iterator[None]:
    """Bind *runtime* as the active session for the current dispatch call.

    When ``runtime`` is ``None`` the context manager is a no-op and the
    default session (backed by the legacy module globals) is used.
    """
    token = _runtime_context.set(runtime) if runtime is not None else None
    try:
        yield
    finally:
        if runtime is not None:
            _runtime_context.reset(runtime)