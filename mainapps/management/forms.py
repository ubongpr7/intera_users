from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from mainapps.accounts.models import User


class StaffUserRegistrationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username','email','user_permissions','groups']


class StaffUserLoginForm(AuthenticationForm):
    company_id = forms.CharField(max_length=15, required=True, label='Company ID')

    def confirm_login_allowed(self, user):
        company_id = self.cleaned_data.get('company_id')
        if user.company.unique_id != company_id:
            raise forms.ValidationError("Invalid company ID.", code='invalid_login')
        super().confirm_login_allowed(user)




class CustomLoginForm(forms.Form):
    company_id = forms.CharField(required=True)
    username = forms.CharField(max_length=254,required=True)
    password = forms.CharField(widget=forms.PasswordInput,required=True)
