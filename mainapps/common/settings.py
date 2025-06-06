
from currency_codes import get_all_currencies, Currency

def DEFAULT_CURRENCY_CODE():
    currencies: list[Currency] = get_all_currencies()
    for currency in currencies:
        if currency.code=="USD":


            return (currency.code,'USD')


def currency_code_mappings():
    currencies: list[Currency] = get_all_currencies()
    choices = [(currency.code, currency.name.upper()) for currency in currencies]
    return choices

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


