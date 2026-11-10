"""Small capability policy for the trusted local host; never model-editable."""
CAPABILITIES = frozenset({'read', 'propose', 'approve', 'export', 'ai'})


def require_capability(granted, capability):
    if capability not in granted:
        raise PermissionError(f'Workspace permission required: {capability}')
