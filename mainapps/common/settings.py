
def get_company_or_profile(user):
    company=None
    try:
        company = user.company
    except user._meta.get_field("company").related_model.DoesNotExist:
        try:
            company = user.profile
        except user._meta.get_field("profile").related_model.DoesNotExist:
            company = None

    return company


