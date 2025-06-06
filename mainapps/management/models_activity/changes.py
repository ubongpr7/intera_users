def get_field_changes(original, updated):
    """
    Identify changed fields between original and updated data
    """
    changes = {}
    for key in updated:
        if key in original and original[key] != updated[key]:
            changes[key] = {
                'old': original[key],
                'new': updated[key]
            }
    return changes